import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import (app, get_compra_repo, get_engine, get_lanzador,
                      get_rcel_client, get_sync_estado_repo, get_venta_repo)
from app.repo import CompraRepo, SyncEstadoRepo, VentaRepo

FIX = Path(__file__).parent / "fixtures"
FIXTURE_VENTAS = (FIX / "ventas_mcmp.html").read_text(encoding="utf-8")
FIXTURE_COMPRAS = (FIX / "compras_mcmp.html").read_text(encoding="utf-8")
RANGO = {"desde": "01/11/2026", "hasta": "30/11/2026"}


class FakeClient:
    """Worker falso: devuelve los fixtures (una página) sin tocar ARCA."""

    def consultar_ventas(self, desde: str, hasta: str, plazo=None) -> list[str]:
        return [FIXTURE_VENTAS]

    def consultar_compras(self, desde: str, hasta: str, plazo=None) -> list[str]:
        return [FIXTURE_COMPRAS]

    def descargar_pdfs_ventas(self, desde, hasta, excluir, limite, plazo=None) -> list[tuple]:
        return []

    def cerrar_sesion(self) -> None:
        pass


@pytest.fixture
def client(db_engine):
    def _get_venta_repo():
        with Session(db_engine) as s:
            yield VentaRepo(s)

    def _get_compra_repo():
        with Session(db_engine) as s:
            yield CompraRepo(s)

    def _get_sync_estado_repo():
        with Session(db_engine) as s:
            yield SyncEstadoRepo(s)

    app.dependency_overrides[get_rcel_client] = lambda: FakeClient()
    app.dependency_overrides[get_venta_repo] = _get_venta_repo
    app.dependency_overrides[get_compra_repo] = _get_compra_repo
    app.dependency_overrides[get_sync_estado_repo] = _get_sync_estado_repo
    app.dependency_overrides[get_engine] = lambda: db_engine
    # La consulta completa corre en segundo plano; en los tests, en el acto.
    app.dependency_overrides[get_lanzador] = lambda: (lambda trabajo: trabajo())
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


# --------------------------------------------------------------------- VENTAS
def test_ventas_vacio_sin_sync(client):
    assert client.get("/ventas", params=RANGO).json() == []


def test_sync_ventas_persiste(client):
    r = client.post("/sync", params=RANGO)  # tipo=ventas por default
    assert r.status_code == 200
    assert r.json() == {"sincronizados": 2, "tipo": "ventas"}


def test_get_ventas_lee_de_db_tras_sync(client):
    client.post("/sync", params=RANGO)
    data = client.get("/ventas", params=RANGO).json()
    assert len(data) == 2
    assert data[0]["cuit_receptor"] == "20111111112"
    assert data[0]["iva_total"] == 210.0   # IVA débito fiscal de la 1ra


# --------------------------------------------------------------------- COMPRAS
def test_sync_compras_persiste(client):
    r = client.post("/sync", params={**RANGO, "tipo": "compras"})
    assert r.status_code == 200
    assert r.json() == {"sincronizados": 3, "tipo": "compras"}


def test_get_compras_lee_de_db_tras_sync(client):
    client.post("/sync", params={**RANGO, "tipo": "compras"})
    data = client.get("/compras", params=RANGO).json()
    assert len(data) == 3
    assert data[0]["cuit_emisor"] == "30111111111"
    assert data[0]["iva_total"] == 9840.50


# ------------------------------------------------------------------ VALIDACIÓN
def test_sync_tipo_invalido_es_400(client):
    assert client.post("/sync", params={**RANGO, "tipo": "otro"}).status_code == 400


def test_sync_exige_token_si_esta_configurado(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "sync_token", "secreto")
    assert client.post("/sync", params=RANGO).status_code == 401
    r = client.post("/sync", params=RANGO, headers={"X-Sync-Token": "secreto"})
    assert r.status_code == 200


# ----------------------------------------------------------------- SYNC ESTADO
class FakeClientCaido:
    """Worker falso que falla como si ARCA no respondiera."""

    def consultar_ventas(self, desde: str, hasta: str) -> list[str]:
        raise RuntimeError("ARCA no responde")


def test_estado_sin_syncs_no_informa_fecha(client):
    assert client.get("/sync/estado").json() == {"fecha": None, "origen": None,
                                                  "trabajo": None}


def test_estado_conserva_la_ultima_sync_exitosa_si_otra_falla(client):
    client.post("/sync", params={**RANGO, "origen": "automatica"})
    exitosa = client.get("/sync/estado").json()
    assert exitosa["origen"] == "automatica"
    assert datetime.datetime.fromisoformat(exitosa["fecha"]).tzinfo is not None

    app.dependency_overrides[get_rcel_client] = lambda: FakeClientCaido()
    caido = TestClient(app, raise_server_exceptions=False)
    assert caido.post("/sync", params={**RANGO, "origen": "manual"}).status_code == 500

    assert client.get("/sync/estado").json() == exitosa


# ------------------------------------------------- CONSULTA COMPLETA (2do plano)
def test_consulta_completa_responde_202_y_el_estado_informa_cada_tipo(client):
    r = client.post("/sync/todo", params=RANGO)
    assert r.status_code == 202

    trabajo = client.get("/sync/estado").json()["trabajo"]
    assert trabajo["estado"] == "terminado"
    assert trabajo["tipos"] == {
        "ventas": {"estado": "ok", "sincronizados": 2, "mensaje": None},
        "compras": {"estado": "ok", "sincronizados": 3, "mensaje": None},
        "pdfs": {"estado": "ok", "sincronizados": 0, "mensaje": None},
    }


class FakeClientSinCompras(FakeClient):
    def consultar_compras(self, desde: str, hasta: str, plazo=None) -> list[str]:
        raise TimeoutError("Locator.click: Timeout 30000ms exceeded.")


def test_consulta_completa_sigue_con_los_demas_si_un_tipo_falla(client):
    app.dependency_overrides[get_rcel_client] = lambda: FakeClientSinCompras()
    client.post("/sync/todo", params=RANGO)

    tipos = client.get("/sync/estado").json()["trabajo"]["tipos"]
    assert tipos["ventas"]["estado"] == "ok"
    assert tipos["compras"] == {"estado": "fallo", "sincronizados": None,
                                "mensaje": "TimeoutError: Locator.click: Timeout 30000ms exceeded."}
    assert tipos["pdfs"]["estado"] == "ok"
    # Lo que sí se trajo queda guardado.
    assert len(client.get("/ventas", params=RANGO).json()) == 2


def test_consulta_completa_rechaza_otra_mientras_hay_una_en_curso(client):
    app.dependency_overrides[get_lanzador] = lambda: (lambda trabajo: None)  # queda en curso
    assert client.post("/sync/todo", params=RANGO).status_code == 202
    assert client.post("/sync/todo", params=RANGO).status_code == 409


def test_consulta_completa_exige_token_si_esta_configurado(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "sync_token", "secreto")
    assert client.post("/sync/todo", params=RANGO).status_code == 401


def test_consulta_completa_baja_pdfs_con_tope_por_consulta(client):
    limites = []

    class FakeClientPdfs(FakeClient):
        def descargar_pdfs_ventas(self, desde, hasta, excluir, limite, plazo=None):
            limites.append(limite)
            return []

    app.dependency_overrides[get_rcel_client] = lambda: FakeClientPdfs()
    client.post("/sync/todo", params=RANGO)
    assert limites == [30]


def test_la_consulta_completa_tiene_un_solo_plazo_de_4_minutos_para_todo(client):
    import time
    plazos = {}

    class FakeClientConPlazo(FakeClient):
        def consultar_ventas(self, desde, hasta, plazo=None):
            plazos["ventas"] = plazo
            return [FIXTURE_VENTAS]

        def consultar_compras(self, desde, hasta, plazo=None):
            plazos["compras"] = plazo
            return [FIXTURE_COMPRAS]

        def descargar_pdfs_ventas(self, desde, hasta, excluir, limite, plazo=None):
            plazos["pdfs"] = plazo
            return []

    app.dependency_overrides[get_rcel_client] = lambda: FakeClientConPlazo()
    antes = time.monotonic()
    client.post("/sync/todo", params=RANGO)

    assert set(plazos) == {"ventas", "compras", "pdfs"}
    assert len(set(plazos.values())) == 1          # el mismo plazo para los tres
    assert 239 <= plazos["ventas"] - antes <= 241


def test_si_se_acaba_el_tiempo_los_tipos_restantes_no_se_consultan(client, monkeypatch):
    import time
    from app import main
    monkeypatch.setattr(main, "PLAZO_CONSULTA_S", 0.05)
    llamados = []

    class FakeClientLento(FakeClient):
        def consultar_ventas(self, desde, hasta, plazo=None):
            llamados.append("ventas")
            time.sleep(0.1)                       # se come todo el plazo
            return [FIXTURE_VENTAS]

        def consultar_compras(self, desde, hasta, plazo=None):
            llamados.append("compras")
            return [FIXTURE_COMPRAS]

        def descargar_pdfs_ventas(self, desde, hasta, excluir, limite, plazo=None):
            llamados.append("pdfs")
            return []

    app.dependency_overrides[get_rcel_client] = lambda: FakeClientLento()
    client.post("/sync/todo", params=RANGO)

    assert llamados == ["ventas"]
    tipos = client.get("/sync/estado").json()["trabajo"]["tipos"]
    assert tipos["ventas"]["estado"] == "ok"
    sin_tiempo = {"estado": "fallo", "sincronizados": None,
                  "mensaje": "Sin tiempo: la consulta completa tiene un límite de 4 minutos."}
    assert tipos["compras"] == sin_tiempo
    assert tipos["pdfs"] == sin_tiempo


class FakeClientConSesion(FakeClient):
    """Registra cuándo se cierra la sesión de ARCA respecto de las consultas."""

    def __init__(self, falla_compras: bool = False):
        self.eventos = []
        self.falla_compras = falla_compras

    def consultar_ventas(self, desde, hasta, plazo=None):
        self.eventos.append("ventas")
        return [FIXTURE_VENTAS]

    def consultar_compras(self, desde, hasta, plazo=None):
        self.eventos.append("compras")
        if self.falla_compras:
            raise TimeoutError("Recibidos no aparece")
        return [FIXTURE_COMPRAS]

    def descargar_pdfs_ventas(self, desde, hasta, excluir, limite, plazo=None):
        self.eventos.append("pdfs")
        return []

    def cerrar_sesion(self):
        self.eventos.append("cerrar_sesion")


def test_cada_consulta_completa_usa_una_sesion_nueva_y_la_cierra_al_terminar(client):
    fake = FakeClientConSesion()
    app.dependency_overrides[get_rcel_client] = lambda: fake
    client.post("/sync/todo", params=RANGO)
    # Nunca reusa una sesión vieja (ARCA la vence sin avisar) ni la deja abierta.
    assert fake.eventos == ["cerrar_sesion", "ventas", "compras", "pdfs", "cerrar_sesion"]


def test_la_sesion_se_cierra_aunque_un_tipo_falle(client):
    fake = FakeClientConSesion(falla_compras=True)
    app.dependency_overrides[get_rcel_client] = lambda: fake
    client.post("/sync/todo", params=RANGO)
    assert fake.eventos[-1] == "cerrar_sesion"


def test_la_consulta_termina_aunque_falle_el_cierre_de_la_sesion(client):
    class FakeClientCierreRoto(FakeClient):
        def cerrar_sesion(self):
            raise RuntimeError("el navegador no responde")

    app.dependency_overrides[get_rcel_client] = lambda: FakeClientCierreRoto()
    client.post("/sync/todo", params=RANGO)
    assert client.get("/sync/estado").json()["trabajo"]["estado"] == "terminado"


def test_consulta_completa_rechaza_un_rango_de_mas_de_3_meses(client):
    r = client.post("/sync/todo", params={"desde": "01/01/2026", "hasta": "30/06/2026"})
    assert r.status_code == 400
    assert r.json()["detail"] == (
        "El rango a consultar en ARCA es de hasta 92 días (3 meses), para que la "
        "consulta entre en 4 minutos.")
    assert client.get("/sync/estado").json()["trabajo"] is None   # no se lanzó


def test_consulta_completa_acepta_un_rango_de_3_meses(client):
    r = client.post("/sync/todo", params={"desde": "01/07/2026", "hasta": "30/09/2026"})
    assert r.status_code == 202
