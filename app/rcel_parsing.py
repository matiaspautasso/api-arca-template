"""Parseo puro de la grilla de RCEL > Consultas -> referencias a PDF de ventas.

Cada fila trae un botón "Ver" con `imprimirComprobante.do?c=<id interno>`. La
clave se normaliza al formato de la tabla `ventas` (Mis Comprobantes):
tipo sin código ('1 - Factura A' -> 'Factura A'), punto de venta 5 dígitos,
número 8 dígitos.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

_VER = re.compile(r"(imprimirComprobante\.do\?c=\d+)")


@dataclass(frozen=True)
class PdfRef:
    tipo: str          # 'Factura A'
    punto_venta: str   # '00002'
    numero: str        # '00001353'
    ver_path: str      # 'imprimirComprobante.do?c=5080046559'

    @property
    def clave(self) -> tuple[str, str, str]:
        return (self.tipo, self.punto_venta, self.numero)


def normalizar_tipo(tipo: str) -> str:
    """'1 - Factura A' (Mis Comprobantes) o 'Factura A' (RCEL) -> 'Factura A'."""
    return re.sub(r"^\s*\d+\s*-\s*", "", tipo).strip()


def clave_venta(tipo: str, punto_venta: str, numero: str) -> tuple[str, str, str]:
    return (normalizar_tipo(tipo), punto_venta.strip().zfill(5), numero.strip().zfill(8))


def parse_rcel_pdf_refs(html: str) -> list[PdfRef]:
    soup = BeautifulSoup(html, "html.parser")
    refs: list[PdfRef] = []
    for tr in soup.select("tr"):
        tipo = tr.find("td", attrs={"title": "Tipo Comprobante"})
        nro = tr.find("td", attrs={"title": "Nro. Comprobante"})
        ver = tr.find("input", attrs={"value": "Ver"})
        if not (tipo and nro and ver):
            continue
        m = _VER.search(ver.get("onclick") or "")
        if not m:
            continue
        pv, _, num = nro.get_text(strip=True).partition("-")
        t, p, n = clave_venta(tipo.get_text(strip=True), pv, num)
        refs.append(PdfRef(tipo=t, punto_venta=p, numero=n, ver_path=m.group(1)))
    return refs
