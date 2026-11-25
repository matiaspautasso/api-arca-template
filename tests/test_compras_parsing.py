from pathlib import Path

from app.compras_parsing import parse_compras

FIXTURE = (Path(__file__).parent / "fixtures" / "compras_mcmp.html").read_text(
    encoding="utf-8"
)


def test_parsea_todas_las_filas():
    compras = parse_compras(FIXTURE)
    assert len(compras) == 3


def test_nota_de_credito_resta_el_iva():
    nc = parse_compras(FIXTURE)[2]   # '3 - Nota de Crédito A'
    assert nc.tipo == "3 - Nota de Crédito A"
    assert nc.iva_21 == 21.0          # el monto de ARCA es positivo
    assert nc.iva_total == -21.0      # pero en el crédito fiscal RESTA


def test_factura_no_resta_el_iva():
    assert parse_compras(FIXTURE)[0].iva_total > 0


def test_separa_punto_venta_y_numero():
    c = parse_compras(FIXTURE)[0]
    assert c.punto_venta == "00017"
    assert c.numero == "00020379"


def test_limpia_cuit_emisor():
    c = parse_compras(FIXTURE)[0]
    assert c.cuit_emisor == "30111111111"   # sin el prefijo 'CUIT '
    assert c.denominacion_emisor == "PROVEEDOR UNO S R L"


def test_guiones_son_cero():
    c = parse_compras(FIXTURE)[0]
    assert c.iva_105 == 0.0     # la celda es '-'
    assert c.iva_27 == 0.0
    assert c.iva_21 == 9840.50
    assert c.neto_21 == 46859.52
    assert c.imp_total == 56981.18


def test_iva_total_suma_alicuotas():
    c = parse_compras(FIXTURE)[1]   # IVA 10,5% y 27%
    assert c.iva_105 == 10.50
    assert c.iva_27 == 27.00
    assert c.iva_total == 37.50


def test_fecha_y_tipo():
    c = parse_compras(FIXTURE)[0]
    assert c.fecha_emision == "02/11/2026"
    assert c.tipo == "1 - Factura A"
