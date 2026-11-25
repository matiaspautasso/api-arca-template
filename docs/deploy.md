# Despliegue en Railway

Un proyecto con tres recursos: **Postgres**, el servicio **api** (FastAPI + worker, **1 réplica**) y el servicio **cron**. Los dos servicios salen del mismo repo y del mismo Dockerfile.

> Cualquier plataforma que corra un contenedor Docker con Postgres sirve. Respetá lo mismo: una réplica, reinicio ante fallas y `shm` amplio para Chromium.

## 1. Postgres

**New → Database → PostgreSQL.** Railway expone `DATABASE_URL`. La app la normaliza a `postgresql+psycopg://` sola.

## 2. Servicio `api`

1. **New → GitHub Repo** con tu fork de este repo. Usa `railway.json` (Dockerfile, healthcheck `/health`, reinicio `ON_FAILURE`).
2. Variables:
   - `ARCA_CUIT`, `ARCA_PASSWORD`, `ARCA_EMPRESA`
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `SYNC_TOKEN` = un secreto fuerte
   - `CORS_ORIGINS` (si tenés frontend)
3. Deploy. El contenedor corre `alembic upgrade head` y levanta Uvicorn en `$PORT`.

> **No subas réplicas ni actives autoscaling.** Dos réplicas son dos logins simultáneos con la misma clave fiscal, y eso arriesga el bloqueo.
> **Dejá activo el reinicio ante fallas**: si Playwright se cuelga, el proceso se termina a propósito ([ADR-0002](adr/0002-playwright-colgado-reinicia-el-proceso.md)).

## 3. Servicio `cron`

1. **New → GitHub Repo**, el mismo repo. En Settings, **Config-as-code file path:** `railway.cron.json`.
2. Variables: `SYNC_API_URL` (la URL pública del servicio `api`) y el mismo `SYNC_TOKEN`. **No** necesita las variables `ARCA_*`: no abre Playwright.

Cada miércoles a las 23:00 UTC lanza `POST /sync/todo` sobre "mes anterior hasta hoy", espera hasta 6 minutos consultando `/sync/estado` y termina con error si algún tipo falló.

## 4. Verificación

```bash
curl https://<tu-api>.up.railway.app/health
curl -X POST "https://<tu-api>.up.railway.app/sync/todo?desde=01/11/2026&hasta=07/11/2026" \
  -H "X-Sync-Token: $SYNC_TOKEN"
curl https://<tu-api>.up.railway.app/sync/estado
curl "https://<tu-api>.up.railway.app/ventas?desde=01/11/2026&hasta=07/11/2026"
```

## Migraciones

El esquema lo gestiona Alembic (`migrations/`). La imagen corre `alembic upgrade head` en cada arranque, y si la base ya está al día no hace nada. Para cambiar el esquema:

```bash
alembic revision --autogenerate -m "describí el cambio"   # revisá el archivo generado
alembic upgrade head
```

Revisá siempre lo que genera `--autogenerate`: si la base tiene tablas ajenas al proyecto, propone borrarlas con `DROP TABLE`.
