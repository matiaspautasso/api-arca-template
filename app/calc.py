"""Cálculos puros del dominio (sin I/O). Núcleo testeable."""

import datetime


def parse_fecha(texto: str) -> datetime.date:
    """'dd/mm/yyyy' (formato de ARCA) -> date."""
    return datetime.datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def parse_money(texto: str) -> float:
    """Convierte un importe a float. Tolera formato es-AR (1.234,56),
    plano (1234.56), símbolo `$` y espacios."""
    s = texto.strip().replace("$", "").replace(" ", "")
    if "," in s and "." in s:          # 2.502.497,80 -> 2502497.80
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                     # 2502497,80 -> 2502497.80
        s = s.replace(",", ".")
    return float(s)                    # solo '.' o sin separador: ya es decimal


def desglose_iva(total: float, alicuota: float = 0.21) -> tuple[float, float]:
    """Devuelve (neto, iva) a partir del Importe Total, para ventas al 21%.

    CLAVE: `Total = Neto * (1 + alícuota)`, por lo tanto
      - Neto = Total / (1 + alícuota)          <- NO es el IVA
      - IVA  = Total - Neto
    """
    neto = total / (1 + alicuota)
    iva = total - neto
    return round(neto, 2), round(iva, 2)
