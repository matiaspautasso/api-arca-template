# Personalizar el template

Qué cambiar para usar esta API con tu propio CUIT y tu negocio. Cada cambio de comportamiento va **test-first** (ver `CLAUDE.md` / `AGENTS.md`).

## 1. Credenciales (obligatorio)

Copiá `.env.example` a `.env` y completá:

| Variable | Qué poner |
|---|---|
| `ARCA_CUIT` | CUIT de la persona que entra con clave fiscal (sin guiones). |
| `ARCA_PASSWORD` | Clave fiscal. **Solo en `.env` o en las variables de la plataforma.** |
| `ARCA_EMPRESA` | Nombre de la empresa a representar en Comprobantes en Línea, **tal como aparece en ARCA**. Solo hace falta para bajar PDFs. |
| `SYNC_TOKEN` | Un secreto largo y aleatorio (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Si está vacío, cualquiera puede disparar una consulta. |

Tu clave fiscal tiene que tener habilitados los servicios **Mis Comprobantes** y, si querés PDFs, **Comprobantes en Línea**.

## 2. Tipos de comprobante

En `app/rcel_selectors.py`:

```python
"tipos_ventas":  ["Factura A", "Factura B", "Nota de Crédito A"],
"tipos_compras": ["Factura A", "Factura B", "Factura C", "Recibo B", "Nota de Crédito A"],
```

Usá los nombres **exactos** del desplegable "Tipo de Comprobante" de Mis Comprobantes. El flujo verifica que queden marcados exactamente esos tipos, y falla antes de leer datos si no coinciden.

## 3. Columnas

`cols_ventas` y `cols_compras` (mismo archivo) son las columnas que se encienden con "Mostrar/ocultar columnas". Para sumar una columna nueva:

1. Agregá un test en `tests/test_ventas_parsing.py` o `test_compras_parsing.py`, con un fixture HTML que la incluya (los datos tienen que ser ficticios).
2. Sumá el campo al modelo (`app/models.py`), al parser y a la fila (`app/repo.py`).
3. Generá la migración: `alembic revision --autogenerate -m "..."`, y revisala antes de commitear.

## 4. Límites

En `app/main.py`: `PLAZO_CONSULTA_S` (240), `MAX_DIAS_CONSULTA` (92) y `PDFS_POR_CONSULTA` (30). Si subís el rango, medí cuánto tarda en tu cuenta: con más comprobantes, la consulta se acerca al plazo.

## 5. Cron

`railway.cron.json` trae `"cronSchedule": "0 23 * * 3"`, que es miércoles a las 23:00 UTC (20:00 en Argentina). El rango lo calcula `rango_mes_anterior` en `scripts/sync_semanal.py`.

## 6. Si ARCA cambia la pantalla

1. Mirá los logs: `[login] falló en <url> | título: …` y `[falla] mcmp: …` muestran dónde quedó cada pestaña.
2. Corré local con `HEADLESS=false` para ver el navegador.
3. Corregí el selector en `app/rcel_selectors.py`. Varios elementos tienen más de un candidato, que se prueban en orden.
4. **No pruebes contra ARCA real en loop**: el circuit breaker corta tras 3 logins fallidos, pero varios intentos seguidos igual pueden bloquear tu clave.

## 7. Sumar un frontend

La API ya tiene CORS (`CORS_ORIGINS`). Recomendación: que el frontend llame a la API **desde el servidor** (un proxy server-side), así `SYNC_TOKEN` no queda expuesto en el navegador. Para el botón "Consultar": `POST /sync/todo` y después consultar `GET /sync/estado` cada pocos segundos hasta que ningún tipo quede `en_curso`.
