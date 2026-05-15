#!/usr/bin/env bash
# votx-agent Docker entrypoint.
# It prepares writable runtime directories only. NapCat/OneBot remains an
# external service and is reached through VOTX_MESSAGE_CONFIG.

set -euo pipefail

ENV_FILE="/app/.env"
ENV_EXAMPLE="/app/.env.example"
USERS_DIR="/app/users"
MESSAGE_RUNTIME_DIR="/app/message-runtime"
MESSAGE_CONFIG="${VOTX_MESSAGE_CONFIG:-/app/message-runtime/config.json}"

key_valid() {
  [ -n "${DEEPSEEK_API_KEY:-}" ] && [ "${DEEPSEEK_API_KEY:-}" != "sk-your-key-here" ]
}

has_users() {
  [ -d "$USERS_DIR" ] || return 1
  for d in "$USERS_DIR"/*/; do
    [ -f "${d}config.json" ] && return 0
  done
  return 1
}

mkdir -p "$USERS_DIR" "$MESSAGE_RUNTIME_DIR" /app/tmp

if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

if [ ! -f "$MESSAGE_RUNTIME_DIR/config.example.json" ] && [ -f /app/message/config.example.json ]; then
  cp /app/message/config.example.json "$MESSAGE_RUNTIME_DIR/config.example.json"
fi

if ! key_valid && ! has_users; then
  cat <<'NOTE'
==============================================
  votx-agent first start
==============================================

Create a user with an API key:
  docker exec -it votx-agent python set_user.py add

Or configure a global key in .env and restart:
  DEEPSEEK_API_KEY=sk-your-key-here

==============================================
NOTE
fi

if [ ! -f "$MESSAGE_CONFIG" ]; then
  cat <<NOTE
[message] Message router config not found: $MESSAGE_CONFIG
[message] Copy message-runtime/config.example.json to config.json, then fill
[message] bound_users and NapCat/Telegram settings when you want external chat.
NOTE
fi

exec python /app/start_web.py "$@"
