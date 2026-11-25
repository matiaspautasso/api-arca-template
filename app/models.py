"""Modelos del dominio."""

import datetime

from pydantic import BaseModel, computed_field


class Venta(BaseModel):
    """Comprobante EMITIDO por el contribuyente (Mis Comprobantes > Emitidos).
    El IVA lo informa ARCA por alícuota (no se calcula): su suma es el IVA
    débito fiscal. El emisor es siempre el contribuyente; la contraparte es el
    receptor (cliente)."""

    fecha_emision: str                 # dd/mm/yyyy
    tipo: str                          # '1 - Factura A', 'Nota de Crédito A', ...
    punto_venta: str                   # '00005'
    numero: str                        # '00007440'
    cuit_receptor: str                 # Doc. Receptor (CUIT del cliente)
    denominacion_receptor: str
    neto_21: float = 0.0
    neto_27: float = 0.0
    neto_gravado_total: float = 0.0
    iva_105: float = 0.0
    iva_21: float = 0.0
    iva_27: float = 0.0
    imp_total: float

    @computed_field
    @property
    def iva_total(self) -> float:
        """IVA débito fiscal = suma de las alícuotas informadas por ARCA. ARCA
        informa montos positivos; una Nota de Crédito RESTA del débito fiscal."""
        suma = self.iva_105 + self.iva_21 + self.iva_27
        signo = -1 if es_nota_de_credito(self.tipo) else 1
        return round(signo * suma, 2)


class Compra(BaseModel):
    """Factura de un proveedor (comprobante RECIBIDO). El IVA viene informado por
    ARCA por alícuota (no se calcula): su suma es el IVA crédito fiscal."""

    fecha_emision: str                 # dd/mm/yyyy
    tipo: str                          # '1 - Factura A'
    punto_venta: str                   # '00005'  (parte izq. del número)
    numero: str                        # '00007440' (parte der. del número)
    cuit_emisor: str                   # CUIT del proveedor (emisor)
    denominacion_emisor: str
    neto_21: float = 0.0
    neto_27: float = 0.0
    iva_105: float = 0.0
    iva_21: float = 0.0
    iva_27: float = 0.0
    imp_total: float

    @computed_field
    @property
    def iva_total(self) -> float:
        """IVA crédito fiscal. ARCA informa montos positivos; una Nota de Crédito
        RESTA del crédito fiscal, así que el signo se aplica acá."""
        suma = self.iva_105 + self.iva_21 + self.iva_27
        signo = -1 if es_nota_de_credito(self.tipo) else 1
        return round(signo * suma, 2)


class ResultadoTipo(BaseModel):
    estado: str                        # pendiente | en_curso | ok | fallo
    sincronizados: int | None = None
    mensaje: str | None = None


class TrabajoSync(BaseModel):
    """Última consulta completa (ventas, compras, pdfs) lanzada en segundo plano."""

    estado: str                        # en_curso | terminado | interrumpido
    origen: str
    inicio: datetime.datetime
    fin: datetime.datetime | None = None
    tipos: dict[str, ResultadoTipo]


class SyncEstado(BaseModel):
    """Última sincronización EXITOSA con ARCA (None si nunca hubo una) y la
    última consulta completa, con el avance de cada tipo."""

    fecha: datetime.datetime | None = None
    origen: str | None = None          # 'manual' | 'automatica'
    trabajo: TrabajoSync | None = None


def _sin_acentos(tipo: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", tipo).encode("ascii", "ignore").decode().lower()


def es_nota_de_credito(tipo: str) -> bool:
    """'3 - Nota de Crédito A' -> True. Compara sin acentos ni mayúsculas."""
    return "nota de credito" in _sin_acentos(tipo)

