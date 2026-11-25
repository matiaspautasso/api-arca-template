"""API ARCA (FastAPI):
sincroniza ARCA (Mis Comprobantes + RCEL) -> Postgres y sirve desde la DB.

- POST /sync?tipo=ventas|compras&desde&hasta -> scrapea con el worker (Emitidos
  para ventas, Recibidos para compras) y hace upsert en la DB.
- POST /sync/todo?desde&hasta -> 202: lanza en segundo plano ventas, compras y pdfs
  (en ese orden; si uno falla, sigue con el resto). 409 si ya hay una en curso.
- GET  /sync/estado -> última sync exitosa y avance de la última consulta completa.
- POST /sync?tipo=pdfs&desde&hasta[&limite=N] -> baja de RCEL el PDF ('Ver') de las
  ventas que aún no lo tienen y lo guarda en `ventas_pdf`.
- GET  /ventas?...  / GET /compras?...  -> leen SOLO de la DB (rápido, no tocan ARCA).
- GET  /ventas/pdf?tipo&punto_venta&numero -> PDF guardado (404 si no está).

El worker es dueño de UNA sesión ARCA (clave fiscal) y la reusa para ambas
secciones. Autenticación de /sync por header X-Sync-Token (si hay SYNC_TOKEN).
"""

import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.calc import parse_fecha
from app.compras_parsing import parse_compras
from app.config import settings
from app.db import make_engine
from app.models import Compra, SyncEstado, Venta
from app.playwright_session import PlaywrightRcelSession
from app.rcel_client import RcelClient
from app.rcel_parsing import clave_venta
from app.repo import (CompraRepo, SyncEstadoRepo, SyncTrabajoRepo,
                      VentaPdfRepo, VentaRepo)
from app.ventas_parsing import parse_ventas
from app.worker import RcelWorker

_worker: RcelWorker | None = None
_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker, _engine
    _engine = make_engine(settings.database_url)   # el esquema lo crea Alembic
    with Session(_engine) as s:
        SyncTrabajoRepo(s).marcar_interrumpida()     # cortada por un reinicio
    _worker = RcelWorker(PlaywrightRcelSession(settings))
    _worker.start()
    try:
        yield
    finally:
        _worker.stop()
        _worker = None
        _engine.dispose()
        _engine = None


app = FastAPI(title="API ARCA", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_rcel_client() -> RcelClient:
    if _worker is None:
        raise RuntimeError("Worker no inicializado (lifespan no corrió).")
    return _worker


def get_venta_repo():
    with Session(_engine) as s:
        yield VentaRepo(s)


def get_compra_repo():
    with Session(_engine) as s:
        yield CompraRepo(s)


def get_sync_estado_repo():
    with Session(_engine) as s:
        yield SyncEstadoRepo(s)


def get_venta_pdf_repo():
    with Session(_engine) as s:
        yield VentaPdfRepo(s)


def get_engine():
    return _engine


def _en_hilo(trabajo) -> None:
    threading.Thread(target=trabajo, daemon=True).start()


def get_lanzador():
    """Cómo se corre la consulta completa: en un hilo (en los tests, en el acto)."""
    return _en_hilo


def _verificar_token(token: str | None) -> None:
    """Si hay SYNC_TOKEN configurado, POST /sync lo exige (cron / 'Actualizar')."""
    if settings.sync_token and token != settings.sync_token:
        raise HTTPException(status_code=401, detail="Token de sincronización inválido.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/sync")
def sincronizar(
    desde: str,
    hasta: str,
    tipo: str = "ventas",
    limite: int | None = None,
    origen: Literal["manual", "automatica"] = "manual",
    client: RcelClient = Depends(get_rcel_client),
    venta_repo: VentaRepo = Depends(get_venta_repo),
    compra_repo: CompraRepo = Depends(get_compra_repo),
    pdf_repo: VentaPdfRepo = Depends(get_venta_pdf_repo),
    estado_repo: SyncEstadoRepo = Depends(get_sync_estado_repo),
    x_sync_token: str | None = Header(default=None),
) -> dict:
    _verificar_token(x_sync_token)
    if tipo not in TIPOS_SYNC:
        raise HTTPException(status_code=400,
                            detail="tipo debe ser 'ventas', 'compras' o 'pdfs'.")
    n = _sincronizar_tipo(tipo, desde, hasta, limite, client,
                          venta_repo, compra_repo, pdf_repo)
    estado_repo.registrar_exito(origen)   # si algo falló antes, se conserva la anterior
    return {"sincronizados": n, "tipo": tipo}


# Mismo orden que el cron: los PDF al final, sobre las ventas ya guardadas.
TIPOS_SYNC = ("ventas", "compras", "pdfs")
# Tope de PDFs por consulta. Son incrementales: la próxima sigue con los que falten.
PDFS_POR_CONSULTA = 30
# La consulta completa (los tres tipos juntos) dura como mucho esto.
PLAZO_CONSULTA_S = 240
SIN_TIEMPO = "Sin tiempo: la consulta completa tiene un límite de 4 minutos."
# Rango máximo por consulta. Medido en producción: 55 días tardaron 55 s
# (2026-11-24); 92 días deja margen dentro de los 4 minutos.
MAX_DIAS_CONSULTA = 92
RANGO_DEMASIADO_LARGO = ("El rango a consultar en ARCA es de hasta 92 días (3 meses), "
                         "para que la consulta entre en 4 minutos.")


def _sincronizar_tipo(tipo: str, desde: str, hasta: str, limite: int | None,
                      client: RcelClient, venta_repo: VentaRepo, compra_repo: CompraRepo,
                      pdf_repo: VentaPdfRepo, plazo: float | None = None) -> int:
    """`plazo` (time.monotonic) solo lo usa la consulta completa."""
    con_plazo = {} if plazo is None else {"plazo": plazo}
    if tipo == "ventas":
        paginas = client.consultar_ventas(desde, hasta, **con_plazo)
        return venta_repo.guardar_muchos([v for html in paginas for v in parse_ventas(html)])
    if tipo == "compras":
        paginas = client.consultar_compras(desde, hasta, **con_plazo)
        return compra_repo.guardar_muchos([c for html in paginas for c in parse_compras(html)])
    bajados = client.descargar_pdfs_ventas(desde, hasta, pdf_repo.claves(), limite, **con_plazo)
    for ref, pdf in bajados:
        pdf_repo.guardar(ref.clave, pdf)
    return len(bajados)


def _consulta_completa(engine, client: RcelClient, desde: str, hasta: str,
                       origen: str) -> None:
    """Corre los tres tipos en orden, con UN plazo para todos, y deja en la DB el
    avance de cada uno. Un tipo que ya no tiene tiempo no se consulta."""
    plazo = time.monotonic() + PLAZO_CONSULTA_S
    # Una sesión de ARCA por consulta: ARCA vence las sesiones sin avisar y una
    # pestaña vieja no muestra los botones (incidente del 23/11/2026).
    _cerrar_sesion(client)
    try:
        _correr_tipos(engine, client, desde, hasta, origen, plazo)
    finally:
        _cerrar_sesion(client)
        # Pase lo que pase, la consulta termina: si quedara 'en curso', todas las
        # siguientes responderían 409.
        with Session(engine) as s:
            SyncTrabajoRepo(s).terminar()


def _cerrar_sesion(client: RcelClient) -> None:
    """Best-effort: una falla al cerrar no debe frenar ni dejar colgada la consulta."""
    try:
        client.cerrar_sesion()
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] no se pudo cerrar la sesión de ARCA: {type(exc).__name__}: {exc}",
              flush=True)


def _correr_tipos(engine, client: RcelClient, desde: str, hasta: str, origen: str,
                  plazo: float) -> None:
    for tipo in TIPOS_SYNC:
        with Session(engine) as s:
            trabajos = SyncTrabajoRepo(s)
            if time.monotonic() >= plazo:
                trabajos.actualizar_tipo(tipo, "fallo", mensaje=SIN_TIEMPO)
                continue
            trabajos.actualizar_tipo(tipo, "en_curso")
            try:
                limite = PDFS_POR_CONSULTA if tipo == "pdfs" else None
                n = _sincronizar_tipo(tipo, desde, hasta, limite, client, VentaRepo(s),
                                      CompraRepo(s), VentaPdfRepo(s), plazo)
            except Exception as exc:  # noqa: BLE001 - se informa y se sigue con el resto
                s.rollback()
                trabajos.actualizar_tipo(tipo, "fallo", mensaje=f"{type(exc).__name__}: {exc}"[:300])
                continue
            trabajos.actualizar_tipo(tipo, "ok", sincronizados=n)
            SyncEstadoRepo(s).registrar_exito(origen)


@app.post("/sync/todo", status_code=202)
def sincronizar_todo(
    desde: str,
    hasta: str,
    origen: Literal["manual", "automatica"] = "manual",
    client: RcelClient = Depends(get_rcel_client),
    engine=Depends(get_engine),
    lanzar=Depends(get_lanzador),
    x_sync_token: str | None = Header(default=None),
) -> dict:
    _verificar_token(x_sync_token)
    if (parse_fecha(hasta) - parse_fecha(desde)).days + 1 > MAX_DIAS_CONSULTA:
        raise HTTPException(status_code=400, detail=RANGO_DEMASIADO_LARGO)
    with Session(engine) as s:
        if not SyncTrabajoRepo(s).iniciar(origen, list(TIPOS_SYNC)):
            raise HTTPException(status_code=409, detail="Ya hay una consulta a ARCA en curso.")
    lanzar(lambda: _consulta_completa(engine, client, desde, hasta, origen))
    return {"estado": "en_curso"}


@app.get("/sync/estado", response_model=SyncEstado)
def estado_sync(estado_repo: SyncEstadoRepo = Depends(get_sync_estado_repo)) -> SyncEstado:
    return estado_repo.obtener()


@app.get("/ventas", response_model=list[Venta])
def listar_ventas(
    desde: str,
    hasta: str,
    venta_repo: VentaRepo = Depends(get_venta_repo),
) -> list[Venta]:
    return venta_repo.listar(desde, hasta)


@app.get("/compras", response_model=list[Compra])
def listar_compras(
    desde: str,
    hasta: str,
    compra_repo: CompraRepo = Depends(get_compra_repo),
) -> list[Compra]:
    return compra_repo.listar(desde, hasta)


@app.get("/ventas/pdf")
def pdf_venta(
    tipo: str,
    punto_venta: str,
    numero: str,
    pdf_repo: VentaPdfRepo = Depends(get_venta_pdf_repo),
) -> Response:
    """Acepta el tipo como lo devuelve GET /ventas ('1 - Factura A') o sin código."""
    pdf = pdf_repo.obtener(clave_venta(tipo, punto_venta, numero))
    if pdf is None:
        raise HTTPException(status_code=404, detail="PDF no descargado todavía.")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'inline; filename="{punto_venta}-{numero}.pdf"'})
