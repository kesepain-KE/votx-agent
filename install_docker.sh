#!/usr/bin/env bash
# Docker installer/start helper for votx-agent.
# NapCat is intentionally not managed here; run it as an external container or
# process and point message-runtime/config.json to its forward WebSocket URL.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=()
NO_UP=false

for arg in "$@"; do
  case "$arg" in
    --no-up) NO_UP=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required: install Docker with the compose plugin." >&2
  exit 1
fi

cd "$REPO_DIR"

mkdir -p users message-runtime
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if [ ! -f message-runtime/config.json ] && [ -f message/config.example.json ]; then
  cp message/config.example.json message-runtime/config.example.json
  echo "Created message-runtime/config.example.json"
  echo "Copy it to message-runtime/config.json after filling NapCat/Telegram bindings."
fi

echo "Building Docker image..."
"${COMPOSE[@]}" build

if [ "$NO_UP" = false ]; then
  echo "Starting votx-agent..."
  "${COMPOSE[@]}" up -d
  echo "Web UI: http://localhost:1478"
else
  echo "Build complete. Start later with: ${COMPOSE[*]} up -d"
fi

cat <<'NOTE'

Message router notes:
  - Config path in container: /app/message-runtime/config.json
  - Host path: ./message-runtime/config.json
  - NapCat is external. For Linux Docker, use host.docker.internal if NapCat is
    on the Docker host, or use the NapCat container/service DNS name if both
    containers share a Docker network.
  - Example OneBot URL: ws://host.docker.internal:3001
NOTE
