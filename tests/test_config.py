import pytest

from app.config import Settings


@pytest.mark.parametrize("entrada, esperada", [
    # Railway/Heroku entregan sin driver; el proyecto usa psycopg 3.
    ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    # Ya correcta: no se toca.
    ("postgresql+psycopg://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
])
def test_database_url_se_normaliza_a_psycopg(monkeypatch, entrada, esperada):
    monkeypatch.setenv("DATABASE_URL", entrada)
    assert Settings().database_url == esperada


def test_sin_database_url_el_default_es_el_postgres_de_docker(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().database_url == "postgresql+psycopg://arca:arca@127.0.0.1:5440/arca"
