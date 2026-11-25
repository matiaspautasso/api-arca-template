import pytest
from alembic import command
from sqlalchemy import inspect

from app.db import make_engine


def test_las_migraciones_crean_las_tablas(engine):
    tablas = set(inspect(engine).get_table_names())
    assert {"ventas", "compras", "alembic_version"} <= tablas


def test_modelos_y_migraciones_no_difieren(engine, alembic_cfg):
    # Si alguien cambia un modelo sin generar migración, esto falla: evita que
    # Railway (que solo aplica migraciones) quede con un esquema distinto al código.
    command.check(alembic_cfg)


def test_el_esquema_no_tiene_tablas_ajenas(engine):
    # El esquema debe contener solo lo del proyecto (nada de restos del RCEL viejo).
    assert set(inspect(engine).get_table_names()) == {
        "ventas", "compras", "ventas_pdf", "sync_estado", "sync_trabajo",
        "alembic_version"}


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "sqlite:///./e2e.db", "mysql://u:p@h/db"])
def test_solo_se_permite_postgres(url):
    # SQLite se eliminó del proyecto: que no vuelva a colarse por una variable de entorno.
    with pytest.raises(ValueError, match="Postgres"):
        make_engine(url)
