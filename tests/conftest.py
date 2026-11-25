"""Infra de tests: Postgres REAL (Docker), esquema creado con las migraciones de Alembic.

Requiere el contenedor de la base:  docker compose up -d db

Los tests corren en una base APARTE (`arca_test`), nunca en la de desarrollo
(`arca`, con los datos reales de ARCA): DATABASE_URL se fuerza ANTES de importar
`app`, y antes de cada test se vacían las tablas verificando que el nombre de la
base sea el de test.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1:5440"          # 127.0.0.1, no 'localhost' (IPv6 lento en Windows)
TEST_DB = "arca_test"
ADMIN_URL = f"postgresql+psycopg://arca:arca@{HOST}/postgres"
TEST_URL = f"postgresql+psycopg://arca:arca@{HOST}/{TEST_DB}"

# Se FUERZA (no setdefault) y antes de importar `app`: `app.config` lee esta
# variable al importarse y `migrations/env.py` la usa para migrar. Así ningún test
# puede tocar la base de desarrollo, aunque el entorno apunte a ella.
os.environ["DATABASE_URL"] = TEST_URL


def _crear_base_de_test_si_falta() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            existe = c.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}
            ).scalar()
            if not existe:
                c.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    except OperationalError as e:
        pytest.exit(
            f"Postgres de test no disponible en {HOST}. "
            f"Levantalo con: docker compose up -d db\n{e}",
            returncode=2,
        )
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


@pytest.fixture(scope="session")
def engine(alembic_cfg):
    """Engine de la base de test con el esquema al día (alembic upgrade head)."""
    from app.db import make_engine

    _crear_base_de_test_si_falta()
    command.upgrade(alembic_cfg, "head")
    eng = make_engine(TEST_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db_engine(engine):
    """Engine con las tablas vacías antes de cada test."""
    assert engine.url.database == TEST_DB, "¡Nunca vaciar una base que no sea la de test!"
    with engine.begin() as c:
        c.execute(text("TRUNCATE TABLE ventas, compras, sync_estado, sync_trabajo"))
    return engine
