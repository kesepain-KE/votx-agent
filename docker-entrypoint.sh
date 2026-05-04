#!/usr/bin/env bash
# votx-agent Docker 入口
# 自动检测 .env 配置，未配置则引导用户

set -e

ENV_FILE="/app/.env"
ENV_EXAMPLE="/app/.env.example"

# 检查 API Key 是否已配置
if [ -z "${DEEPSEEK_API_KEY}" ] || [ "${DEEPSEEK_API_KEY}" = "sk-your-key-here" ]; then
    # 自动从模板创建 .env（如果不存在）
    if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    fi

    echo "=============================================="
    echo "  votx-agent: API Key 未配置"
    echo "=============================================="
    echo ""
    echo "  请编辑项目目录下的 .env 文件，填入你的 Key:"
    echo ""
    echo "    DEEPSEEK_API_KEY=sk-your-key-here"
    echo ""
    echo "  获取: https://platform.deepseek.com/api_keys"
    echo ""
    echo "  配置完成后重新启动:"
    echo ""
    echo "    docker compose up -d"
    echo ""
    echo "=============================================="
    exit 1
fi

exec python /app/start_web.py "$@"
