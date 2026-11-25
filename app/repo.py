"""Persistencia de ventas y compras (SQLAlchemy). Upsert por clave de negocio."""

import datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, LargeBinary, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.calc import parse_fecha
from app.db import Base
from app.models import Compra, SyncEstado, TrabajoSync, Venta


class VentaRow(Base):
    __tablename__ = "ventas"

    # El emisor es siempre el contribuyente, así que una venta se identifica por
    # tipo + punto de venta + número (la misma numeración se reinicia por tipo).
    tipo: Mapped[str] = mapped_column(String, primary_key=True)
    punto_venta: Mapped[str] = mapped_column(String, primary_key=True)
    numero: Mapped[str] = mapped_column(String, primary_key=True)
    fecha_emision: Mapped[datetime.date] = mapped_column(Date, index=True)
    cuit_receptor: Mapped[str] = mapped_column(String)
    denominacion_receptor: Mapped[str] = mapped_column(String)
    neto_21: Mapped[float] = mapped_column(Float)
    neto_27: Mapped[float] = mapped_column(Float)
    neto_gravado_total: Mapped[float] = mapped_column(Float)
    iva_105: Mapped[float] = mapped_column(Float)
    iva_21: Mapped[float] = mapped_column(Float)
    iva_27: Mapped[float] = mapped_column(Float)
    imp_total: Mapped[float] = mapped_column(Float)


class VentaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def guardar_muchos(self, ventas: list[Venta]) -> int:
        for v in ventas:
            clave = (v.tipo, v.punto_venta, v.numero)
            row = self.s.get(VentaRow, clave)
            if row is None:
                row = VentaRow(tipo=v.tipo, punto_venta=v.punto_venta, numero=v.numero)
                self.s.add(row)
            row.fecha_emision = parse_fecha(v.fecha_emision)
            row.cuit_receptor = v.cuit_receptor
            row.denominacion_receptor = v.denominacion_receptor
            row.neto_21 = v.neto_21
            row.neto_27 = v.neto_27
            row.neto_gravado_total = v.neto_gravado_total
            row.iva_105 = v.iva_105
            row.iva_21 = v.iva_21
            row.iva_27 = v.iva_27
            row.imp_total = v.imp_total
        self.s.commit()
        return len(ventas)

    def listar(self, desde: str, hasta: str) -> list[Venta]:
        d, h = parse_fecha(desde), parse_fecha(hasta)
        rows = self.s.scalars(
            select(VentaRow)
            .where(VentaRow.fecha_emision.between(d, h))
            .order_by(VentaRow.fecha_emision, VentaRow.punto_venta, VentaRow.numero)
        ).all()
        return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(r: VentaRow) -> Venta:
        return Venta(
            fecha_emision=r.fecha_emision.strftime("%d/%m/%Y"),
            tipo=r.tipo,
            punto_venta=r.punto_venta,
            numero=r.numero,
            cuit_receptor=r.cuit_receptor,
            denominacion_receptor=r.denominacion_receptor,
            neto_21=r.neto_21,
            neto_27=r.neto_27,
            neto_gravado_total=r.neto_gravado_total,
            iva_105=r.iva_105,
            iva_21=r.iva_21,
            iva_27=r.iva_27,
            imp_total=r.imp_total,
        )


class CompraRow(Base):
    __tablename__ = "compras"

    # Clave compuesta: una factura de proveedor se identifica por emisor + tipo +
    # punto de venta + número (el mismo número existe para distintos emisores).
    cuit_emisor: Mapped[str] = mapped_column(String, primary_key=True)
    tipo: Mapped[str] = mapped_column(String, primary_key=True)
    punto_venta: Mapped[str] = mapped_column(String, primary_key=True)
    numero: Mapped[str] = mapped_column(String, primary_key=True)
    fecha_emision: Mapped[datetime.date] = mapped_column(Date, index=True)
    denominacion_emisor: Mapped[str] = mapped_column(String)
    neto_21: Mapped[float] = mapped_column(Float)
    neto_27: Mapped[float] = mapped_column(Float)
    iva_105: Mapped[float] = mapped_column(Float)
    iva_21: Mapped[float] = mapped_column(Float)
    iva_27: Mapped[float] = mapped_column(Float)
    imp_total: Mapped[float] = mapped_column(Float)


class CompraRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def guardar_muchos(self, compras: list[Compra]) -> int:
        for c in compras:
            clave = (c.cuit_emisor, c.tipo, c.punto_venta, c.numero)
            row = self.s.get(CompraRow, clave)
            if row is None:
                row = CompraRow(
                    cuit_emisor=c.cuit_emisor, tipo=c.tipo,
                    punto_venta=c.punto_venta, numero=c.numero,
                )
                self.s.add(row)
            row.fecha_emision = parse_fecha(c.fecha_emision)
            row.denominacion_emisor = c.denominacion_emisor
            row.neto_21 = c.neto_21
            row.neto_27 = c.neto_27
            row.iva_105 = c.iva_105
            row.iva_21 = c.iva_21
            row.iva_27 = c.iva_27
            row.imp_total = c.imp_total
        self.s.commit()
        return len(compras)

    def listar(self, desde: str, hasta: str) -> list[Compra]:
        d, h = parse_fecha(desde), parse_fecha(hasta)
        rows = self.s.scalars(
            select(CompraRow)
            .where(CompraRow.fecha_emision.between(d, h))
            .order_by(CompraRow.fecha_emision, CompraRow.cuit_emisor,
                      CompraRow.punto_venta, CompraRow.numero)
        ).all()
        return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(r: CompraRow) -> Compra:
        return Compra(
            fecha_emision=r.fecha_emision.strftime("%d/%m/%Y"),
            tipo=r.tipo,
            punto_venta=r.punto_venta,
            numero=r.numero,
            cuit_emisor=r.cuit_emisor,
            denominacion_emisor=r.denominacion_emisor,
            neto_21=r.neto_21,
            neto_27=r.neto_27,
            iva_105=r.iva_105,
            iva_21=r.iva_21,
            iva_27=r.iva_27,
            imp_total=r.imp_total,
        )


class VentaPdfRow(Base):
    __tablename__ = "ventas_pdf"

    # Misma clave de negocio que `ventas`, con el tipo SIN código ('Factura A'):
    # así se cruza con RCEL (que no informa el código) y con Mis Comprobantes.
    tipo: Mapped[str] = mapped_column(String, primary_key=True)
    punto_venta: Mapped[str] = mapped_column(String, primary_key=True)
    numero: Mapped[str] = mapped_column(String, primary_key=True)
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    descargado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))


class VentaPdfRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def claves(self) -> set[tuple[str, str, str]]:
        rows = self.s.execute(
            select(VentaPdfRow.tipo, VentaPdfRow.punto_venta, VentaPdfRow.numero)).all()
        return {tuple(r) for r in rows}

    def guardar(self, clave: tuple[str, str, str], pdf: bytes) -> None:
        row = self.s.get(VentaPdfRow, clave)
        if row is None:
            tipo, pv, nro = clave
            row = VentaPdfRow(tipo=tipo, punto_venta=pv, numero=nro)
            self.s.add(row)
        row.pdf = pdf
        row.descargado_en = datetime.datetime.now(datetime.UTC)
        self.s.commit()

    def obtener(self, clave: tuple[str, str, str]) -> bytes | None:
        row = self.s.get(VentaPdfRow, clave)
        return row.pdf if row else None


class SyncEstadoRow(Base):
    __tablename__ = "sync_estado"

    # Una sola fila (id=1): la última sync EXITOSA. Una sync que falla no la toca.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    origen: Mapped[str] = mapped_column(String)                   # manual | automatica


class SyncEstadoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def registrar_exito(self, origen: str) -> None:
        row = self.s.get(SyncEstadoRow, 1)
        if row is None:
            row = SyncEstadoRow(id=1)
            self.s.add(row)
        row.fecha = datetime.datetime.now(datetime.UTC)
        row.origen = origen
        self.s.commit()

    def obtener(self) -> SyncEstado:
        row = self.s.get(SyncEstadoRow, 1)
        trabajo = SyncTrabajoRepo(self.s).obtener()
        if row is None:
            return SyncEstado(trabajo=trabajo)
        return SyncEstado(fecha=row.fecha, origen=row.origen, trabajo=trabajo)


class SyncTrabajoRow(Base):
    __tablename__ = "sync_trabajo"

    # Una sola fila (id=1): la última consulta completa. Hay una sola a la vez.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estado: Mapped[str] = mapped_column(String)                   # en_curso | terminado | interrumpido
    origen: Mapped[str] = mapped_column(String)
    inicio: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tipos: Mapped[dict] = mapped_column(JSON)


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class SyncTrabajoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def iniciar(self, origen: str, tipos: list[str]) -> bool:
        """Arranca una consulta nueva; False si ya hay una en curso."""
        row = self.s.get(SyncTrabajoRow, 1, with_for_update=True)
        if row is not None and row.estado == "en_curso":
            self.s.rollback()
            return False
        if row is None:
            row = SyncTrabajoRow(id=1)
            self.s.add(row)
        row.estado, row.origen, row.inicio, row.fin = "en_curso", origen, _ahora(), None
        row.tipos = {t: {"estado": "pendiente", "sincronizados": None, "mensaje": None}
                     for t in tipos}
        self.s.commit()
        return True

    def actualizar_tipo(self, tipo: str, estado: str, sincronizados: int | None = None,
                        mensaje: str | None = None) -> None:
        row = self.s.get(SyncTrabajoRow, 1)
        # Se reasigna el dict entero: SQLAlchemy no detecta cambios internos del JSON.
        row.tipos = {**row.tipos, tipo: {"estado": estado, "sincronizados": sincronizados,
                                         "mensaje": mensaje}}
        self.s.commit()

    def terminar(self, estado: str = "terminado") -> None:
        row = self.s.get(SyncTrabajoRow, 1)
        row.estado, row.fin = estado, _ahora()
        self.s.commit()

    def marcar_interrumpida(self) -> None:
        """Al arrancar el backend: una consulta 'en curso' quedó cortada por el reinicio."""
        row = self.s.get(SyncTrabajoRow, 1)
        if row is None or row.estado != "en_curso":
            return
        row.tipos = {
            t: r if r["estado"] == "ok" else
            {"estado": "fallo", "sincronizados": None,
             "mensaje": "Interrumpida: el backend se reinició."}
            for t, r in row.tipos.items()}
        row.estado, row.fin = "interrumpido", _ahora()
        self.s.commit()

    def obtener(self) -> TrabajoSync | None:
        row = self.s.get(SyncTrabajoRow, 1)
        if row is None:
            return None
        return TrabajoSync(estado=row.estado, origen=row.origen, inicio=row.inicio,
                           fin=row.fin, tipos=row.tipos)
