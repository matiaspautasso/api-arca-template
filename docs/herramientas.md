# Herramientas para desarrollar sobre la API

Chequeo rápido:

```bash
bash scripts/check_herramientas.sh     # [OK] / [FALTA] por herramienta. Sale con 1 si falta una requerida
```

En Windows, corrélo desde Git Bash.

## Qué se necesita

| Herramienta | Nivel | Para qué |
|---|---|---|
| **Git** | Requerida | Clonar o forkear y versionar. |
| **Docker** + Compose v2 | Requerida | Postgres de dev y tests (`docker compose up -d db`) y la imagen de la API, que incluye Chromium. El daemon tiene que estar corriendo. |
| **Python 3.12+** | Requerida | Correr los tests y Alembic fuera de Docker. |
| **GitHub CLI** (`gh`) | Recomendada | Forks, PRs e issues desde la terminal. Después de instalarla: `gh auth login`. |
| **Railway CLI** (`railway`) | Recomendada | CLI del host: deploy, logs y variables. Después de instalarla: `railway login` y `railway link`. |
| **Node.js LTS** | Opcional | Instalar la CLI de Railway con npm, o sumar un frontend. |

Si desplegás en otro host, reemplazá la CLI de Railway por la de ese host (por ejemplo `flyctl` para Fly.io o `render` para Render). Las reglas de `docs/deploy.md` son las mismas: una réplica y reinicio ante fallas.

## Cómo instalarlas

| Herramienta | Windows (winget) | macOS (Homebrew) | Linux (Debian/Ubuntu) |
|---|---|---|---|
| Git | `winget install --id Git.Git -e` | `brew install git` | `sudo apt install git` |
| Docker | `winget install --id Docker.DockerDesktop -e` | `brew install --cask docker` | [Docker Engine](https://docs.docker.com/engine/install/) + `docker-compose-plugin` |
| Python 3.12 | `winget install --id Python.Python.3.12 -e` | `brew install python@3.12` | `sudo apt install python3.12 python3.12-venv` |
| GitHub CLI | `winget install --id GitHub.cli -e` | `brew install gh` | [cli.github.com](https://cli.github.com/) |
| Railway CLI | `npm i -g @railway/cli` (o `scoop install railway`) | `brew install railway` | `bash <(curl -fsSL cli.new)` o `npm i -g @railway/cli` |
| Node.js LTS | `winget install --id OpenJS.NodeJS.LTS -e` | `brew install node` | [nodejs.org](https://nodejs.org/) |

Docker Desktop en Windows necesita WSL 2 y suele pedir reiniciar la máquina. Después de instalar, abrí una terminal nueva para que el `PATH` se actualice.

Dependencias del proyecto, una sola vez:

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No hace falta `playwright install`: los tests no abren un navegador, y la imagen Docker ya trae Chromium. Solo lo necesitás para correr la API fuera de Docker con `HEADLESS=false`.

## Chequeo guiado (agentes)

Al empezar a trabajar en el repo:

1. Corré `bash scripts/check_herramientas.sh`.
2. Si aparece alguna `[FALTA]`, preguntale al usuario **"¿Querés que instale estas herramientas recomendadas?"**, con una opción por herramienta faltante (selección múltiple) y su nivel (requerida, recomendada u opcional). Detectá el sistema operativo y mostrá el comando exacto de la tabla de arriba. Esperá la respuesta antes de seguir.
3. Instalá solo las que el usuario eligió, con el comando de su sistema. Si un instalador pide permisos de administrador, reinicio o un login interactivo (`gh auth login`, `railway login`), indicale al usuario que lo corra él.
4. Volvé a correr el script. **Terminaste** cuando todas las herramientas elegidas aparecen `[OK]`. Si una requerida sigue faltando, informalo y frená antes de tocar código.
