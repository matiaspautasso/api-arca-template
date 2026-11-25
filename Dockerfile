# Imagen oficial de Playwright (trae Chromium + dependencias del sistema).
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini ./
COPY migrations ./migrations

ENV HEADLESS=true \
    PLAYWRIGHT_NO_SANDBOX=true

EXPOSE 8000
# Primero se aplican las migraciones (idempotente: si ya está en `head` no hace
# nada) y recién después arranca la API. En Postgres la app NO crea tablas sola.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
