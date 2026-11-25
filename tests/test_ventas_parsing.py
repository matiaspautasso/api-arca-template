from pathlib import Path

from app.ventas_parsing import parse_ventas

FIXTURE = (Path(__file__).parent / "fixtures" / "ventas_mcmp.html").read_text(
    encoding="utf-8"
)


def test_parsea_todas_las_filas():
    assert len(parse_ventas(FIXTURE)) == 2


def test_separa_punto_venta_y_numero():
    v = parse_ventas(FIXTURE)[0]
    assert v.punto_venta == "00005"
    assert v.numero == "00000123"


def test_limpia_doc_receptor_y_denominacion():
    v = parse_ventas(FIXTURE)[0]
    assert v.cuit_receptor == "20111111112"
    assert v.denominacion_receptor == "CLIENTE UNO SA"


def test_guiones_son_cero_y_montos_ok():
    v = parse_ventas(FIXTURE)[0]
    assert v.iva_105 == 0.0
    assert v.iva_27 == 0.0
    assert v.iva_21 == 210.0
    assert v.neto_21 == 1000.0
    assert v.neto_gravado_total == 1000.0
    assert v.imp_total == 1210.0


def test_captura_todas_las_alicuotas():
    v = parse_ventas(FIXTURE)[1]   # Nota de Crédito con 10,5% y 27%
    assert v.iva_105 == 10.5
    assert v.iva_27 == 27.0
    assert v.neto_27 == 100.0
    assert v.neto_gravado_total == 200.0
    assert v.iva_total == -37.5   # Nota de Crédito: resta del débito fiscal


def test_tipo_y_fecha():
    v = parse_ventas(FIXTURE)[1]
    assert v.fecha_emision == "05/11/2026"
    assert v.tipo == "3 - Nota de Crédito A"
