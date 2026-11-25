"""Parseo puro del HTML de 'Mis Comprobantes > Emitidos' -> [Venta].

Misma grilla DataTable que compras (sin atributos `title`), pero con columnas de
RECEPTOR (cliente). Se mapea por TEXTO de encabezado: resiliente a mostrar u
ocultar columnas.
"""

import re
import unicodedata

from bs4 import BeautifulSoup

from app.calc import parse_money
from app.models import Venta

# Encabezado normalizado -> campo del modelo.
_COLS = {
    "fecha": "fecha_emision",
    "tipo": "tipo",
    "numero": "numero",
    "doc receptor": "cuit_receptor",
    "denominacion receptor": "denominacion_receptor",
    "iva 10 5": "iva_105",
    "iva 21": "iva_21",
    "iva 27": "iva_27",
    "neto grav iva 21": "neto_21",
    "neto grav iva 27": "neto_27",
    "neto gravado total": "neto_gravado_total",
    "imp total": "imp_total",
}
_MONTOS = {"iva_105", "iva_21", "iva_27", "neto_21", "neto_27",
           "neto_gravado_total", "imp_total"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _monto(texto: str) -> float:
    t = texto.strip()
    return 0.0 if t in ("", "-") else parse_money(t)


def parse_ventas(html: str) -> list[Venta]:
    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.select_one("table#tablaDataTables")
    if tabla is None:
        return []

    headers = [_norm(th.get_text()) for th in tabla.select("thead th")]
    campos = [_COLS.get(h) for h in headers]

    ventas: list[Venta] = []
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
            elif campo == "cuit_receptor":
                datos["cuit_receptor"] = re.sub(r"\D", "", texto)
            elif campo in _MONTOS:
                datos[campo] = _monto(texto)
            else:
                datos[campo] = texto
        ventas.append(Venta(**datos))

    return ventas
