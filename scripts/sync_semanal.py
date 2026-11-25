"""Job corto para Railway Cron: dispara la sincronización semanal y termina.

Lanza POST /sync/todo (autenticado) en la API ya desplegada, que corre en segundo
plano VENTAS, COMPRAS y PDFS sobre el rango "mes anterior": desde el 1º del mes
pasado hasta hoy. Después consulta GET /sync/estado hasta que termine. El upsert de
la API hace que correr de más NO duplique.

NO abre Playwright ni loguea a ARCA: solo pega a la API, que es la única dueña de
la sesión. Así el cron no agrega un login extra.

Env:
  SYNC_API_URL   URL base de la API (ej. https://<tu-api>.up.railway.app)
  SYNC_TOKEN     token que la API exige en el header X-Sync-Token

Uso (Railway Cron, miércoles 20hs ART = 23:00 UTC):
  schedule: 0 23 * * 3
  comando : python scripts/sync_semanal.py
"""

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request


def rango_mes_anterior(hoy: dt.date) -> tuple[str, str]:
    """Desde el 1º del mes pasado hasta hoy (superset seguro del mes anterior)."""
    primero_mes_actual = hoy.replace(day=1)
    ultimo_mes_pasado = primero_mes_actual - dt.timedelta(days=1)
    desde = ultimo_mes_pasado.replace(day=1)
    return desde.strftime("%d/%m/%Y"), hoy.strftime("%d/%m/%Y")


# Consulta el estado cada 15 s, hasta 6 minutos: la consulta completa dura como
# mucho 4 en el backend; el resto es margen (por ejemplo, si ya había una en curso).
SEGUNDOS_ENTRE_CONSULTAS = 15
MAX_CONSULTAS_DE_ESTADO = 24


def lanzar(base_url: str, token: str, desde: str, hasta: str) -> None:
    """Lanza la consulta completa. Si ya hay una en curso (409), se espera esa."""
    url = f"{base_url.rstrip('/')}/sync/todo?desde={desde}&hasta={hasta}&origen=automatica"
    req = urllib.request.Request(url, method="POST", headers={"X-Sync-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=60):   # noqa: S310 (URL propia)
            pass
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        print("[sync] ya había una consulta en curso: se espera esa")


def leer_estado(base_url: str) -> dict:
    url = f"{base_url.rstrip('/')}/sync/estado"
    with urllib.request.urlopen(url, timeout=60) as resp:   # noqa: S310 (URL propia)
        return json.loads(resp.read().decode())


def esperar(segundos: float) -> None:
    time.sleep(segundos)


def main() -> int:
    base_url = os.getenv("SYNC_API_URL", "").strip()
    token = os.getenv("SYNC_TOKEN", "").strip()
    if not base_url:
        print("[sync] Falta SYNC_API_URL", file=sys.stderr)
        return 2

    desde, hasta = rango_mes_anterior(dt.date.today())
    print(f"[sync] rango {desde} -> {hasta}")
    lanzar(base_url, token, desde, hasta)
    for _ in range(MAX_CONSULTAS_DE_ESTADO):
        trabajo = leer_estado(base_url)["trabajo"]
        if trabajo["estado"] != "en_curso":
            break
        esperar(SEGUNDOS_ENTRE_CONSULTAS)
    else:
        print("[sync] la consulta no terminó a tiempo", file=sys.stderr)
        return 1

    fallo = trabajo["estado"] != "terminado"
    for tipo, r in trabajo["tipos"].items():
        print(f"[sync] {tipo}: {r}")
        fallo = fallo or r["estado"] != "ok"
    return 1 if fallo else 0


if __name__ == "__main__":
    raise SystemExit(main())
