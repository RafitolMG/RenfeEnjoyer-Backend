#!/usr/bin/env bash
# Serve the app on this machine's Tailscale address.
#
# Binds to the Tailscale IP specifically rather than 0.0.0.0, so the app is reachable
# from the tailnet but not from the local network.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${RENFE_PORT:-8000}"

if ! HOST="${RENFE_HOST:-$(tailscale ip -4 2>/dev/null | head -1)}" || [ -z "$HOST" ]; then
  echo "No se pudo obtener la IP de Tailscale. ¿Está 'tailscale up'?" >&2
  exit 1
fi

for candidate in "$ROOT/backend/.venv" "$ROOT/.venv"; do
  if [ -x "$candidate/bin/uvicorn" ]; then VENV="$candidate"; break; fi
done
if [ -z "${VENV:-}" ]; then
  echo "No se encontró el entorno virtual. Crea uno con:" >&2
  echo "  cd backend && python -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

if [ ! -d "$ROOT/frontend/dist" ]; then
  echo "Compilando el frontend..."
  (cd "$ROOT/frontend" && npm run build)
fi

echo "Sirviendo en http://$HOST:$PORT  (solo alcanzable desde tu tailnet)"
cd "$ROOT/backend"
exec "$VENV/bin/uvicorn" app.main:app --host "$HOST" --port "$PORT"
