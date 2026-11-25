"""Configuración leída de .env (sin valores sensibles en código)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _con_driver_psycopg(url: str) -> str:
    """Railway entrega DATABASE_URL como 'postgresql://' (o 'postgres://'), sin
    driver; SQLAlchemy asumiría psycopg2, que NO está instalado (usamos psycopg 3)."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


class Settings:
    def __init__(self) -> None:
        self.cuit = os.getenv("ARCA_CUIT", "")
        self.password = os.getenv("ARCA_PASSWORD", "")
        self.empresa = os.getenv("ARCA_EMPRESA", "")
        self.login_url = os.getenv(
            "ARCA_LOGIN_URL",
            "https://auth.afip.gob.ar/contribuyente_/login.xhtml",
        )
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.database_url = _con_driver_psycopg(
            os.getenv("DATABASE_URL", "postgresql+psycopg://arca:arca@127.0.0.1:5440/arca"))
        # Token para autenticar POST /sync (cron y botón 'Actualizar'). Si queda
        # vacío, /sync no exige token (modo dev/local).
        self.sync_token = os.getenv("SYNC_TOKEN", "")
        # Orígenes permitidos para un frontend (separados por coma).
        self.cors_origins = [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ]
        # Chromium bajo Docker necesita --no-sandbox.
        self.no_sandbox = os.getenv("PLAYWRIGHT_NO_SANDBOX", "false").lower() == "true"


settings = Settings()
