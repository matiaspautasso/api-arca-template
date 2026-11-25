"""Infra de base de datos (SQLAlchemy). SOLO Postgres; el esquema lo gestiona Alembic.

Las tablas NO se crean desde la app: se aplican con `alembic upgrade head` (la
imagen de Docker/Railway lo corre antes de levantar la API).
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if not url.startswith("postgresql"):
        # Solo el esquema en el mensaje: la URL puede traer usuario y clave.
        raise ValueError(
            f"Solo se admite Postgres (postgresql+psycopg://...), no '{url.split(':')[0]}'."
        )
    return create_engine(url, pool_pre_ping=True)
