#!/usr/bin/env bash
# Native Linux installer for votx-agent.
# Usage:
#   bash install.sh
#   bash install.sh --skip-user
#   bash install.sh --skip-web

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
VOTX_BIN="${VOTX_BIN:-/usr/local/bin/votx}"
SKIP_USER=false
SKIP_WEB=false

for arg in "$@"; do
  case "$arg" in
    --skip-user) SKIP_USER=true ;;
    --skip-web) SKIP_WEB=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red() { printf '\033[0;31m%s\033[0m\n' "$*"; }

find_python() {
  command -v python3 2>/dev/null || command -v python 2>/dev/null || true
}

ensure_python() {
  local py="$1"
  if [ -z "$py" ]; then
    red "Python >= 3.10 is required."
    exit 1
  fi
  "$py" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
print(f"  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} [OK]")
PY
}

write_launcher() {
  local target="$1"
  local content
  content="#!/usr/bin/env bash
exec \"$VENV_DIR/bin/python\" \"$REPO_DIR/votx.py\" \"\$@\"
"
  if [ "$(id -u)" -eq 0 ] || [ -w "$(dirname "$target")" ]; then
    printf '%s' "$content" > "$target"
    chmod +x "$target"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    printf '%s' "$content" | sudo tee "$target" >/dev/null
    sudo chmod +x "$target"
    return
  fi
  yellow "Cannot write $target. Add this alias manually:"
  echo "  alias votx='$VENV_DIR/bin/python $REPO_DIR/votx.py'"
}

green "votx-agent Linux installer"
cd "$REPO_DIR"

echo "[1/7] Checking Python"
PYTHON="$(find_python)"
ensure_python "$PYTHON"

echo "[2/7] Creating virtual environment"
"$PYTHON" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null

echo "[3/7] Installing Python dependencies"
"$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements.txt"

echo "[4/7] Building Web UI"
if [ "$SKIP_WEB" = false ]; then
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    (cd "$REPO_DIR/web" && npm install && npm run build)
  elif [ -f "$REPO_DIR/web/dist/index.html" ]; then
    yellow "Node.js/npm not found; reusing existing web/dist build."
  else
    red "Node.js >= 18 and npm are required to build the Web UI."
    echo "Install Node.js or rerun with --skip-web if you only need CLI/runtime setup."
    exit 1
  fi
else
  yellow "Skipping Web UI build."
fi

echo "[5/7] Preparing configuration files"
if [ ! -f "$REPO_DIR/.env" ] && [ -f "$REPO_DIR/.env.example" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "  Created .env from .env.example"
fi

mkdir -p "$REPO_DIR/users" "$REPO_DIR/tmp" "$REPO_DIR/message/push_queue"
if [ ! -f "$REPO_DIR/message/config.local.json" ] && [ -f "$REPO_DIR/message/config.example.json" ]; then
  cp "$REPO_DIR/message/config.example.json" "$REPO_DIR/message/config.local.json"
  echo "  Created message/config.local.json from the disabled example template"
fi

echo "[6/7] Registering votx command"
write_launcher "$VOTX_BIN"
echo "  $VOTX_BIN [OK]"

echo "[7/7] User setup"
if [ "$SKIP_USER" = false ]; then
  if ! find "$REPO_DIR/users" -mindepth 2 -maxdepth 2 -name config.json | grep -q .; then
    read -r -p "Create a user now? [Y/n] " CREATE_USER
    CREATE_USER="${CREATE_USER:-y}"
    if [[ "$CREATE_USER" =~ ^[Yy]$ ]]; then
      "$VENV_DIR/bin/python" "$REPO_DIR/set_user.py" add
    fi
  else
    echo "  Existing user configuration found."
  fi
else
  yellow "Skipping interactive user creation."
fi

green "Install complete"
echo "Start Web UI:"
echo "  votx web --port=1478"
echo "Message router config:"
echo "  Native Linux: edit $REPO_DIR/message/config.local.json"
echo "  NapCat must expose forward WebSocket; votx-agent only connects to it."
