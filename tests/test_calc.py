import datetime

import pytest

from app.calc import desglose_iva, parse_fecha, parse_money


def test_desglose_iva_factura_individual():
    # Factura real 1353: total 2.502.497,8 -> neto 2.068.180,0 ; IVA 434.317,8
    # (verificable a mano: 2068180 * 1.21 = 2502497.8)
    neto, iva = desglose_iva(2502497.8)
    assert neto == 2068180.0
    assert iva == 434317.8


def test_desglose_iva_periodo_coincide_con_afipsdk():
    # Fuente de verdad INDEPENDIENTE (AfipSDK, ver HALLAZGOS.md):
    # total del período 12.221.968 -> neto 10.100.800 ; IVA 2.121.168
    neto, iva = desglose_iva(12221968.0)
    assert neto == 10100800.0
    assert iva == 2121168.0


def test_parse_fecha():
    assert parse_fecha("02/11/2026") == datetime.date(2026, 11, 2)
    assert parse_fecha("23/10/2026") == datetime.date(2026, 10, 23)


@pytest.mark.parametrize("texto, esperado", [
    ("2502497.8", 2502497.8),       # formato plano (como viene de RCEL)
    ("2.502.497,80", 2502497.8),    # es-AR con miles y decimales
    ("2502497,80", 2502497.8),      # es-AR solo con coma decimal
    ("$ 1.210,00", 1210.0),         # con símbolo y espacio
    ("337590", 337590.0),           # entero sin separadores
])
def test_parse_money(texto, esperado):
    assert parse_money(texto) == esperado
