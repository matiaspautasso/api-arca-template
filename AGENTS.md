# API ARCA: instrucciones para agentes

FastAPI + Postgres que scrapea el portal de ARCA (ex AFIP) con Playwright: ventas (Mis Comprobantes > Emitidos), compras (> Recibidos) y PDFs de ventas (Comprobantes en Línea). Cómo funciona: `docs/funcionamiento.md`. Personalización: `docs/personalizar.md`.

## Herramientas

Al empezar una sesión, corré `bash scripts/check_herramientas.sh`. Si falta alguna, seguí el **chequeo guiado** de `docs/herramientas.md`: preguntá al usuario qué instalar y esperá su respuesta.

## Comandos

```bash
docker compose up -d db                  # Postgres en 127.0.0.1:5440 (tests y dev)
python -m pytest -q                      # tests (base arca_test, se crea sola)
python -m pytest -q -k nombre            # un test
docker compose up --build                # API + base en http://127.0.0.1:8000/docs
alembic revision --autogenerate -m "…"   # migración nueva (revisarla antes de commitear)
```

Usá `127.0.0.1`, no `localhost`: en Windows, `localhost` prueba IPv6 primero y cada conexión tarda minutos.

## Reglas

- **TDD**: todo cambio de comportamiento va test-first. Escribí el test, miralo fallar y recién después escribí el código. Los tests nunca tocan ARCA: el worker se reemplaza por fakes (`FakeClient` en `tests/test_api.py`) y los parsers se prueban con fixtures HTML.
- **Una sola sesión de clave fiscal a la vez.** Una réplica, un worker (`app/worker.py`), y todo Playwright corre en el hilo del worker. No abras navegadores en paralelo, no agregues réplicas y no hagas que el cron loguee.
- **ARCA real solo con confirmación del usuario.** Logins repetidos pueden bloquear la clave fiscal.
- **Selectores solo en `app/rcel_selectors.py`.** Antes de cada acción, confirmá la pantalla esperada. Nunca hagas clics a ciegas.
- **Sin `wait_for_load_state("networkidle")` en el portal** (`docs/adr/0003-*`): esperá el elemento que confirma la pantalla.
- **Secretos solo en `.env` o en las variables de la plataforma.** No los imprimas en logs (el diagnóstico loguea URL sin query string y título). Los fixtures y ejemplos usan CUITs y nombres ficticios. `_spike_out/` tiene datos reales y está ignorado por git.
- **Esquema solo con Alembic**: la app no crea tablas.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/).

## Mapa

| Ruta | Contenido |
|---|---|
| `app/main.py` | Endpoints, consulta completa en segundo plano y límites (`PLAZO_CONSULTA_S`, `MAX_DIAS_CONSULTA`, `PDFS_POR_CONSULTA`). |
| `app/worker.py` | `RcelWorker`: hilo único, cola, caché, relogin y vigilante de cuelgues. |
| `app/playwright_session.py` | Navegación real (adapter de I/O, sin unit tests de navegación). |
| `app/session.py` | Contrato de la sesión + lógica pura (`detectar_expiracion`, `primer_camino`). |
| `app/*_parsing.py` | HTML → modelos. |
| `app/repo.py`, `migrations/` | Persistencia y esquema. |
| `scripts/sync_semanal.py` | Cron: llama a la API, no a ARCA. |
| `docs/adr/` | Decisiones de diseño. Leelas antes de cambiar el flujo de consulta. |
