import pytest
from sqlalchemy.orm import Session

from app.models import Venta
from app.repo import VentaRepo


def _venta(numero: str = "00000001", **kw) -> Venta:
    base = dict(
        fecha_emision="02/11/2026",
        tipo="1 - Factura A",
        punto_venta="00005",
        numero=numero,
        cuit_receptor="20111111112",
        denominacion_receptor="CLIENTE UNO SA",
        neto_21=100.0,
        neto_gravado_total=100.0,
        iva_21=21.0,
        imp_total=121.0,
    )
    base.update(kw)
    return Venta(**base)


@pytest.fixture
def repo(db_engine):
    with Session(db_engine) as s:
        yield VentaRepo(s)


def test_guardar_y_listar(repo):
    assert repo.guardar_muchos([_venta()]) == 1
    out = repo.listar("01/11/2026", "30/11/2026")
    assert len(out) == 1
    assert out[0].cuit_receptor == "20111111112"
    assert out[0].iva_total == 21.0   # IVA débito fiscal


def test_upsert_por_tipo_pv_numero(repo):
    # Misma (tipo, punto_venta, numero) -> pisa, no duplica.
    repo.guardar_muchos([_venta(), _venta(imp_total=999.0)])
    out = repo.listar("01/11/2026", "30/11/2026")
    assert len(out) == 1
    assert out[0].imp_total == 999.0


def test_distinto_numero_no_colisiona(repo):
    repo.guardar_muchos([_venta(numero="00000001"), _venta(numero="00000002")])
    assert len(repo.listar("01/11/2026", "30/11/2026")) == 2


def test_distinto_tipo_mismo_numero_no_colisiona(repo):
    # Una Factura A y una Nota de Crédito A pueden compartir pv+numero.
    repo.guardar_muchos([
        _venta(tipo="1 - Factura A"),
        _venta(tipo="3 - Nota de Crédito A"),
    ])
    assert len(repo.listar("01/11/2026", "30/11/2026")) == 2


def test_iva_total_suma_alicuotas(repo):
    repo.guardar_muchos([_venta(iva_105=10.5, iva_21=21.0, iva_27=27.0)])
    assert repo.listar("01/11/2026", "30/11/2026")[0].iva_total == 58.5
