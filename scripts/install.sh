#!/usr/bin/env bash
# One-off setup on a new machine: Python and Node dependencies plus the `renfe` command.
#
# Nothing is installed system-wide. Missing system packages are reported, not installed,
# so the script never needs sudo and can be re-run safely.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
BIN_DIR="${RENFE_BIN_DIR:-$HOME/.local/bin}"

missing=()
command -v python3 >/dev/null || missing+=("python (3.12 o superior)")
command -v npm >/dev/null || missing+=("nodejs y npm")
command -v tailscale >/dev/null || missing+=("tailscale")
browser_found=""
for browser in google-chrome google-chrome-stable chromium chromium-browser; do
  command -v "$browser" >/dev/null && browser_found=1 && break
done
[ -n "$browser_found" ] || missing+=("chromium o google-chrome")

if [ ${#missing[@]} -gt 0 ]; then
  echo "Faltan programas del sistema. Instálalos con tu gestor de paquetes y vuelve a lanzar esto:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
  echo "Hace falta Python 3.12 o superior; este equipo tiene $(python3 --version)." >&2
  exit 1
fi

echo "==> Dependencias de Python"
[ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -e "$ROOT/backend[dev]"

echo "==> Dependencias del frontend"
(cd "$ROOT/frontend" && npm ci --no-audit --no-fund --loglevel=error)

echo "==> Comando renfe"
mkdir -p "$BIN_DIR"
if [ -e "$BIN_DIR/renfe" ] && [ ! -L "$BIN_DIR/renfe" ]; then
  echo "Ya existe $BIN_DIR/renfe y no es un enlace de esta instalación; no lo toco." >&2
  exit 1
fi
ln -sfn "$ROOT/scripts/serve-tailscale.sh" "$BIN_DIR/renfe"
echo "    $BIN_DIR/renfe -> $ROOT/scripts/serve-tailscale.sh"

command -v chromedriver >/dev/null \
  || echo "Aviso: no hay chromedriver en el sistema; Selenium descargará uno la primera vez."

case ":$PATH:" in
  *":$BIN_DIR:"*)
    echo "Listo. Arranca la app con: renfe"
    ;;
  *)
    echo "Listo, pero $BIN_DIR no está en tu PATH. Añádelo y abre una terminal nueva:"
    # The shell that ran this script, which may differ from the login shell in $SHELL.
    case "$(ps -o comm= -p "$PPID" 2>/dev/null || basename "${SHELL:-}")" in
      fish) echo "  fish_add_path $BIN_DIR" ;;
      zsh) echo "  echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.zshrc" ;;
      *) echo "  echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc" ;;
    esac
    echo "Mientras tanto funciona igual con: $ROOT/scripts/serve-tailscale.sh"
    ;;
esac
