"""Parseo puro del HTML de 'Mis Comprobantes > Recibidos' -> [Compra].

A diferencia de RCEL (ventas), esta grilla es una DataTable SIN atributos `title`
y con columnas que aparecen/desaparecen según el toggle de visibilidad. Por eso
se mapea cada celda por el TEXTO de su encabezado (no por posición): resiliente
a que el usuario muestre u oculte columnas.
"""

import re
import unicodedata

from bs4 import BeautifulSoup

from app.calc import parse_money
from app.models import Compra

# Encabezado normalizado -> campo del modelo.
_COLS = {
    "fecha": "fecha_emision",
    "tipo": "tipo",
    "numero": "numero",
    "cuit emisor": "cuit_emisor",
    "denominacion emisor": "denominacion_emisor",
    "iva 10 5": "iva_105",
    "iva 21": "iva_21",
    "iva 27": "iva_27",
    "neto grav iva 21": "neto_21",
    "neto grav iva 27": "neto_27",
    "imp total": "imp_total",
}
_MONTOS = {"iva_105", "iva_21", "iva_27", "neto_21", "neto_27", "imp_total"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _monto(texto: str) -> float:
    """ARCA muestra '-' cuando la alícuota no aplica -> 0.0."""
    t = texto.strip()
    return 0.0 if t in ("", "-") else parse_money(t)


def parse_compras(html: str) -> list[Compra]:
    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.select_one("table#tablaDataTables")
    if tabla is None:
        return []

    headers = [_norm(th.get_text()) for th in tabla.select("thead th")]
    campos = [_COLS.get(h) for h in headers]   # None para columnas que no usamos

    compras: list[Compra] = []
    for tr in tabla.select("tbody tr"):
        celdas = tr.find_all("td")
        if len(celdas) != len(campos):
            continue
        datos: dict = {}
        for campo, td in zip(campos, celdas):
            if campo is None:
                continue
            texto = td.get_text(strip=True)
            if campo == "numero":
                pv, _, num = texto.partition("-")
                datos["punto_venta"], datos["numero"] = pv, num
            elif campo == "cuit_emisor":
                datos["cuit_emisor"] = re.sub(r"\D", "", texto)
            elif campo in _MONTOS:
                datos[campo] = _monto(texto)
            else:
                datos[campo] = texto
        compras.append(Compra(**datos))

    return compras
