#!/usr/bin/env bash
# votx-agent Docker 入口
# 支持两种 Key 配置方式:
#   1. 每用户独立 Key: docker exec <容器> python set_user.py add
#   2. 全局 .env Key: 在 .env 中设置 DEEPSEEK_API_KEY
# 方式 1 优先级更高，即使用户 Key 和全局 Key 同时存在，也使用用户 Key。

set -e

ENV_FILE="/app/.env"
ENV_EXAMPLE="/app/.env.example"
USERS_DIR="/app/users"

# 检查全局 Key 是否有效
key_valid() {
    [ -n "${DEEPSEEK_API_KEY}" ] && [ "${DEEPSEEK_API_KEY}" != "sk-your-key-here" ]
}

# 检查是否有已配置的用户（users/<name>/config.json）
has_users() {
    [ -d "$USERS_DIR" ] || return 1
    for d in "$USERS_DIR"/*/; do
        [ -f "${d}config.json" ] && return 0
    done
    return 1
}

if ! key_valid; then
    if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    fi

    if ! has_users; then
        echo "=============================================="
        echo "  votx-agent: 首次启动"
        echo "=============================================="
        echo ""
        echo "  请先创建用户（每用户可有独立 API Key）:"
        echo ""
        echo "    docker exec -it <容器> python set_user.py add"
        echo ""
        echo "  或配置全局 Key（编辑 .env 后重启）:"
        echo "    DEEPSEEK_API_KEY=sk-your-key-here"
        echo "    获取: https://platform.deepseek.com/api_keys"
        echo ""
        echo "=============================================="
    fi
fi

exec python /app/start_web.py "$@"
