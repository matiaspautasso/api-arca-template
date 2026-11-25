# Cómo funciona la consulta a ARCA

ARCA (ex AFIP) no ofrece una API pública para "Mis Comprobantes", así que esta API **scrapea el portal web** con un navegador real (Playwright + Chromium) y guarda los datos en Postgres. Los clientes leen siempre de la base, nunca de ARCA directamente.

## Herramientas

| Pieza | Para qué |
|---|---|
| **FastAPI** + Uvicorn | API HTTP (`app/main.py`). |
| **Playwright** (Python, API sync, Chromium) | Navega el portal con clave fiscal. Imagen base `mcr.microsoft.com/playwright/python`. |
| **BeautifulSoup** | Parsea el HTML de las grillas (`ventas_parsing.py`, `compras_parsing.py`, `rcel_parsing.py`). |
| **PostgreSQL** + SQLAlchemy 2 + psycopg 3 | Comprobantes, PDFs y estado de las consultas. |
| **Alembic** | Esquema de la base. El contenedor corre `alembic upgrade head` al arrancar. |
| **pytest** | Tests contra un Postgres real (base `arca_test`). |
| **Railway** (opcional) | Servicio `api` (1 réplica) y servicio cron (`scripts/sync_semanal.py`). |

## Piezas

```
POST /sync/todo ──► hilo de fondo ──► RcelWorker (1 hilo, 1 sesión) ──► PlaywrightRcelSession ──► ARCA
                                           │                                   │
GET /sync/estado ◄── tabla sync_trabajo    └── caché TTL + circuit breaker     └── HTML ──► parsers ──► repos ──► Postgres
```

| Módulo | Rol |
|---|---|
| `app/worker.py` (`RcelWorker`) | Único hilo dueño de la sesión de ARCA. Serializa los pedidos (el portal guarda estado y la API sync de Playwright solo funciona desde el hilo que la creó). Tiene caché de 5 min por rango y reintenta con relogin ante `SesionExpirada`. |
| `app/circuit_breaker.py` | Protege el login: 30 s mínimo entre logins, y corte de 1 hora tras 3 fallos seguidos. Evita bloquear la clave fiscal. |
| `app/playwright_session.py` | Navegación real (adapter de I/O). |
| `app/rcel_selectors.py` | **Todos los selectores del portal.** Si ARCA cambia la pantalla, se corrige acá. |
| `app/session.py` | Contrato de la sesión + lógica pura: `detectar_expiracion` y `primer_camino`. |
| `app/ventas_parsing.py`, `compras_parsing.py`, `rcel_parsing.py` | HTML → modelos. Mapean columnas por texto de encabezado. |
| `app/repo.py` | Upsert por clave de negocio, PDFs, estado de sync. |
| `app/main.py` | Endpoints y orquestación de la consulta completa. |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Salud. |
| POST | `/sync/todo?desde&hasta` | **202**. Corre ventas, compras y PDFs en segundo plano. 400 si el rango supera 92 días, 409 si ya hay una consulta en curso. |
| GET | `/sync/estado` | Última sync exitosa y avance por tipo de la última consulta (`pendiente`, `en_curso`, `ok`, `fallo`). |
| POST | `/sync?tipo=ventas\|compras\|pdfs&desde&hasta` | Sincroniza un solo tipo, de forma sincrónica. |
| GET | `/ventas?desde&hasta`, `/compras?desde&hasta` | Leen **solo de la base**. |
| GET | `/ventas/pdf?tipo&punto_venta&numero` | PDF guardado (404 si todavía no se bajó). |

Las fechas van en formato `dd/mm/aaaa`. Si `SYNC_TOKEN` está configurado, los `POST /sync*` exigen el header `X-Sync-Token`. Hay documentación interactiva en `/docs`.

## Flujo de una consulta completa

1. `POST /sync/todo` valida el rango, registra el trabajo en `sync_trabajo` y responde 202.
2. **Cierra cualquier sesión anterior**: cada consulta loguea de cero, porque ARCA vence las sesiones sin avisar.
3. **Login**: abre `ARCA_LOGIN_URL`, completa el CUIT, toca "Siguiente", completa la clave y toca "Ingresar". El login cuenta como exitoso cuando aparece el buscador del portal (`#buscadorInput`). No espera `networkidle` ([ADR-0003](adr/0003-sin-networkidle-en-el-portal-de-arca.md)).
4. **Ventas**: abre Mis Comprobantes desde el buscador del portal. Si falla, entra por "Ver todos" > Mis servicios. Después va a **Emitidos**, filtra fecha y tipos, **verifica que el filtro aplicado sea el pedido**, muestra las columnas de IVA, pasa a 50 por página y lee todas las páginas.
5. **Compras**: el mismo flujo, en **Recibidos**.
6. **PDFs**: abre Comprobantes en Línea (RCEL), elige la empresa (`ARCA_EMPRESA`), busca por fechas y baja con la sesión autenticada (`context.request.get`) el PDF de cada venta que no esté guardado. Baja como máximo 30 por consulta, y la siguiente sigue con los que falten.
7. Cada tipo hace upsert y anota su resultado. Si un tipo falla, siguen los demás.
8. Al final cierra la sesión y marca el trabajo como terminado, aunque algo haya fallado.

## Límites y protecciones

| Límite | Valor | Dónde |
|---|---|---|
| Consulta completa | 4 min | `PLAZO_CONSULTA_S` en `main.py` ([ADR-0001](adr/0001-consulta-arca-en-segundo-plano-con-plazo-total.md)) |
| Cada acción de Playwright | 30 s | `set_default_timeout` |
| Rango por consulta | 92 días | `MAX_DIAS_CONSULTA` |
| PDFs por consulta | 30 | `PDFS_POR_CONSULTA` |
| Playwright colgado | Pasado el plazo + 60 s, se termina el proceso y la plataforma lo reinicia | `worker.py` ([ADR-0002](adr/0002-playwright-colgado-reinicia-el-proceso.md)) |
| Reinicio a mitad de una consulta | Al arrancar, la marca `interrumpido` | `lifespan` en `main.py` |

**Regla de oro: una sola sesión de clave fiscal a la vez.** Se corre una réplica, con un worker, y el cron no loguea: solo llama a la API. Varias sesiones simultáneas arriesgan el bloqueo de la clave.

**Diagnóstico sin credenciales:** ante una falla, los logs muestran la URL (sin query string) y el título de cada pestaña (`[login] falló en …`, `[falla] mcmp: …`). Las fallas de RCEL dejan un screenshot y el HTML en `_spike_out/`, que está ignorado por git porque contiene datos reales.

## Datos

- **Ventas** (`ventas`): Emitidos. Upsert por `(tipo, punto_venta, numero)`. El IVA es el que informa ARCA por alícuota (10,5 %, 21 %, 27 %).
- **Compras** (`compras`): Recibidos. Upsert por `(cuit_emisor, tipo, punto_venta, numero)`.
- **Notas de crédito**: `iva_total` sale con signo negativo.
- **PDFs** (`ventas_pdf`): bytes del PDF por clave de venta.
- **Estado** (`sync_estado`, `sync_trabajo`): última sync exitosa y avance de la consulta en curso.
