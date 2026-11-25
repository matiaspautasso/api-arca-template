import pytest
from sqlalchemy.orm import Session

from app.models import Compra
from app.repo import CompraRepo


def _compra(numero: str = "00007440", **kw) -> Compra:
    base = dict(
        fecha_emision="02/11/2026",
        tipo="1 - Factura A",
        punto_venta="00005",
        numero=numero,
        cuit_emisor="30000000007",
        denominacion_emisor="PROVEEDOR DE PRUEBA SRL",
        neto_21=100.0,
        iva_21=21.0,
        imp_total=121.0,
    )
    base.update(kw)
    return Compra(**base)


@pytest.fixture
def repo(db_engine):
    with Session(db_engine) as s:
        yield CompraRepo(s)


def test_guardar_y_listar(repo):
    n = repo.guardar_muchos([_compra()])
    assert n == 1
    out = repo.listar("01/11/2026", "30/11/2026")
    assert len(out) == 1
    assert out[0].cuit_emisor == "30000000007"
    assert out[0].iva_total == 21.0  # suma de alícuotas (crédito fiscal)


def test_upsert_por_clave_compuesta(repo):
    # Misma (cuit, tipo, punto_venta, numero) -> un solo registro, no dos.
    repo.guardar_muchos([_compra(), _compra(imp_total=999.0)])
    out = repo.listar("01/11/2026", "30/11/2026")
    assert len(out) == 1
    assert out[0].imp_total == 999.0  # la 2da pisa a la 1ra


def test_sincronizar_dos_veces_no_duplica(repo):
    repo.guardar_muchos([_compra()])
    repo.guardar_muchos([_compra()])  # mismo rango, de nuevo
    assert len(repo.listar("01/11/2026", "30/11/2026")) == 1


def test_distinto_numero_no_colisiona(repo):
    repo.guardar_muchos([_compra(numero="00007440"), _compra(numero="00007441")])
    assert len(repo.listar("01/11/2026", "30/11/2026")) == 2


def test_iva_total_suma_tres_alicuotas(repo):
    repo.guardar_muchos([_compra(iva_105=10.5, iva_21=21.0, iva_27=27.0)])
    out = repo.listar("01/11/2026", "30/11/2026")
    assert out[0].iva_total == 58.5


def test_listar_filtra_por_rango(repo):
    repo.guardar_muchos([
        _compra(numero="00000001", fecha_emision="05/11/2026"),
        _compra(numero="00000002", fecha_emision="20/11/2026"),
    ])
    out = repo.listar("01/11/2026", "10/11/2026")
    assert [c.numero for c in out] == ["00000001"]
