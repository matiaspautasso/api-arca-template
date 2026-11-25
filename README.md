# API ARCA (template)

API propia para traer tus **ventas, compras y PDFs de facturas desde ARCA (ex AFIP)** y guardarlos en Postgres. ARCA no tiene una API pública para "Mis Comprobantes", así que esta API entra al portal con tu clave fiscal usando un navegador real (Playwright), lee las grillas y las expone por HTTP.

Es un **template**: forkealo, poné tus credenciales y desplegalo como servicio propio. Viene preparado para trabajar con **Claude Code** (`CLAUDE.md`) o **Codex** (`AGENTS.md`).

> ⚠️ Usás **tu** clave fiscal. Una sola sesión a la vez y nada de loops contra ARCA real: los logins repetidos pueden bloquear la clave. Sin garantías: el portal de ARCA puede cambiar sin aviso.

## Qué hace

- `POST /sync/todo?desde&hasta` lanza en segundo plano **ventas** (Emitidos), **compras** (Recibidos) y **PDFs** (Comprobantes en Línea), con un plazo total de 4 minutos.
- `GET /sync/estado` muestra el avance de cada tipo.
- `GET /ventas`, `GET /compras` y `GET /ventas/pdf` leen de la base, sin tocar ARCA.
- Un cron semanal opcional mantiene la base al día.

El IVA es el que informa ARCA por alícuota (10,5 %, 21 %, 27 %), no uno calculado. Las notas de crédito restan.

Detalle del flujo, herramientas y límites: **[docs/funcionamiento.md](docs/funcionamiento.md)**.

## Requisitos

- Docker (con Docker Compose), Git y Python 3.12+. Recomendadas: GitHub CLI, Railway CLI y, si tu agente no tiene una guía de buenas prácticas, las [skills de Matt Pocock](https://github.com/mattpocock/skills).
- Clave fiscal con **Mis Comprobantes** habilitado (y **Comprobantes en Línea** para los PDFs).

Chequealas con `bash scripts/check_herramientas.sh`. Cómo instalar cada una: **[docs/herramientas.md](docs/herramientas.md)**.

## Arranque rápido

```bash
cp .env.example .env              # completá ARCA_CUIT, ARCA_PASSWORD, ARCA_EMPRESA, SYNC_TOKEN
docker compose up --build         # API en http://127.0.0.1:8000/docs
```

```bash
curl -X POST "http://127.0.0.1:8000/sync/todo?desde=01/11/2026&hasta=15/11/2026" -H "X-Sync-Token: <tu token>"
curl http://127.0.0.1:8000/sync/estado
curl "http://127.0.0.1:8000/ventas?desde=01/11/2026&hasta=15/11/2026"
```

## Tests

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d db
python -m pytest -q
```

Los tests corren contra un Postgres real en una base aparte (`arca_test`) y **nunca tocan ARCA**: el navegador se reemplaza por fakes y los parsers usan fixtures HTML con datos ficticios.

## Personalizar y desplegar

- **[docs/personalizar.md](docs/personalizar.md)**: credenciales, tipos de comprobante, columnas, límites, cron y qué hacer si ARCA cambia la pantalla.
- **[docs/deploy.md](docs/deploy.md)**: Railway (api con 1 réplica, cron y Postgres).
- **[docs/adr/](docs/adr/)**: por qué la consulta corre en segundo plano, por qué un Playwright colgado reinicia el proceso y por qué no se espera `networkidle`.

## Con Claude Code o Codex

Abrí el repo con tu agente y pedile cambios en lenguaje natural ("sumá la columna Neto No Gravado a ventas"). Las reglas del proyecto están en `AGENTS.md`, y `CLAUDE.md` las importa: TDD, una sola sesión de ARCA, selectores centralizados y secretos fuera del código. Al empezar, el agente chequea tus herramientas y te pregunta si querés que instale las que faltan. Pedile siempre que **no** pruebe contra ARCA real sin tu confirmación.

## Licencia

[MIT](LICENSE).
