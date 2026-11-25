#!/usr/bin/env bash
# Chequea las herramientas para desarrollar sobre la API (ver docs/herramientas.md).
# Uso: bash scripts/check_herramientas.sh
# Sale con 1 si falta alguna REQUERIDA. Las RECOMENDADAS solo se informan.

faltan_requeridas=0
faltantes=()

ok()    { printf '  [OK]    %-16s %s\n' "$1" "$2"; }
falta() { printf '  [FALTA] %-16s %s\n' "$1" "$2"; faltantes+=("$1"); }

version_de() { "$@" 2>/dev/null | head -n1; }

python_cmd() {
  for c in python3 python; do
    if v=$($c --version 2>/dev/null) && [[ $v == Python* ]]; then echo "$c"; return; fi
  done
}

echo "Requeridas:"

if command -v git >/dev/null; then ok git "$(version_de git --version)"; else falta git "control de versiones"; faltan_requeridas=1; fi

if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then ok docker "$(version_de docker --version)"
  else falta docker "instalado pero el daemon no responde (abrí Docker Desktop)"; faltan_requeridas=1; fi
  if docker compose version >/dev/null 2>&1; then ok "docker compose" "$(version_de docker compose version)"
  else falta "docker compose" "plugin compose v2"; faltan_requeridas=1; fi
else
  falta docker "Postgres de dev/tests y la imagen de la API"; faltan_requeridas=1
fi

py=$(python_cmd)
if [[ -n $py ]]; then
  v=$($py -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  if $py -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then ok python "$v"
  else falta python "hay $v, se necesita 3.12+"; faltan_requeridas=1; fi
else
  falta python "3.12+ para correr los tests"; faltan_requeridas=1
fi

echo "Recomendadas:"

if command -v gh >/dev/null; then
  if gh auth status >/dev/null 2>&1; then ok gh "$(version_de gh --version) (logueado)"
  else ok gh "$(version_de gh --version) (sin login: gh auth login)"; fi
else falta gh "GitHub CLI: forks, PRs, issues"; fi

if command -v railway >/dev/null; then ok railway "$(version_de railway --version)"
else falta railway "CLI del host (Railway): deploy, logs, variables"; fi

if command -v node >/dev/null; then ok node "$(version_de node --version)"
else falta node "solo para instalar la CLI de Railway con npm o sumar un frontend"; fi

echo
if (( ${#faltantes[@]} )); then
  echo "Faltan: ${faltantes[*]}"
  echo "Cómo instalarlas: docs/herramientas.md"
else
  echo "Todo listo."
fi
exit $faltan_requeridas
