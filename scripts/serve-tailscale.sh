#!/usr/bin/env bash
# Start the app on this machine's Tailscale address and open it in the browser.
#
# Binds to the Tailscale IP specifically rather than 0.0.0.0, so the app is reachable
# from the tailnet but not from the local network. Running it again while the app is
# up just opens the browser.
set -euo pipefail

# Resolved through symlinks, so the command also works when linked into ~/.local/bin.
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
FRONTEND="$ROOT/frontend"
PORT="${RENFE_PORT:-8000}"

if ! HOST="${RENFE_HOST:-$(tailscale ip -4 2>/dev/null | head -1)}" || [ -z "$HOST" ]; then
  echo "No se pudo obtener la IP de Tailscale. ¿Está 'tailscale up'?" >&2
  exit 1
fi

# The IP changes whenever the node re-registers; the MagicDNS name does not. The short
# name is not used because on this machine it resolves to its own IPv6 addresses, which
# the server does not listen on.
NAME="$(tailscale status --json 2>/dev/null | python3 -c '
import json, sys
status = json.load(sys.stdin)
if status.get("CurrentTailnet", {}).get("MagicDNSEnabled"):
    print(status["Self"]["DNSName"].rstrip("."))
' 2>/dev/null || true)"
URL="http://${NAME:-$HOST}:$PORT"

healthy() {
  curl -fsS --max-time 1 "http://$HOST:$PORT/api/health" >/dev/null 2>&1
}

open_browser() {
  # Only from a desktop session: over SSH there is no screen to open it on.
  if [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] && command -v xdg-open >/dev/null; then
    xdg-open "$URL" >/dev/null 2>&1 &
  fi
}

if healthy; then
  echo "Renfe Enjoyer ya estaba en marcha: $URL"
  open_browser
  exit 0
fi

for candidate in "$ROOT/.venv" "$ROOT/backend/.venv"; do
  if [ -x "$candidate/bin/uvicorn" ]; then VENV="$candidate"; break; fi
done
if [ -z "${VENV:-}" ]; then
  echo "No se encontró el entorno virtual. Crea uno con:" >&2
  echo "  python -m venv .venv && .venv/bin/pip install -e 'backend[dev]'" >&2
  exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  (cd "$FRONTEND" && npm ci)
fi

# Rebuild when any source is newer than the last build, so an edit is never served stale.
BUILT="$FRONTEND/dist/index.html"
if [ ! -f "$BUILT" ] || [ -n "$(find "$FRONTEND/src" "$FRONTEND/public" "$FRONTEND/index.html" \
  "$FRONTEND/vite.config.ts" "$FRONTEND/package-lock.json" -newer "$BUILT" -print -quit 2>/dev/null)" ]; then
  echo "Compilando el frontend..."
  (cd "$FRONTEND" && npm run build --silent)
fi

cd "$ROOT/backend"
"$VENV/bin/uvicorn" app.main:app --host "$HOST" --port "$PORT" --log-level warning &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM HUP

until healthy; do
  if ! kill -0 "$server" 2>/dev/null; then
    echo "El servidor no llegó a arrancar." >&2
    exit 1
  fi
  sleep 0.25
done

echo "Renfe Enjoyer en marcha: $URL"
echo "Solo alcanzable desde tu tailnet. Ctrl+C para pararlo."
open_browser
wait "$server"
