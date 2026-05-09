#!/usr/bin/env bash
# votx-agent 一键安装脚本
# 用法: bash install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
VOTX_BIN="/usr/local/bin/votx"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}votx-agent 安装脚本${NC}"
echo ""

# ---- 1. 检查 Python ----
echo "[1/5] 检查 Python..."
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo "")
if [ -z "$PYTHON" ]; then
    echo -e "${RED}错误: 未找到 Python，请先安装 Python >= 3.10${NC}"
    exit 1
fi

PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
PY_MAJOR=$($PYTHON --version 2>&1 | awk '{print $2}' | cut -d. -f1)
PY_MINOR=$($PYTHON --version 2>&1 | awk '{print $2}' | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}错误: Python >= 3.10 需要，当前版本: $PY_VER${NC}"
    exit 1
fi
echo "  Python $PY_VER  [OK]"

# ---- 2. 创建虚拟环境 ----
echo "[2/5] 创建虚拟环境..."
$PYTHON -m venv "$VENV_DIR"
echo "  .venv 已创建"

# ---- 3. 安装依赖 ----
echo "[3/5] 安装依赖..."
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
echo "  依赖安装完成"

# ---- 4. 注册 votx 命令 ----
echo "[4/5] 注册 votx 命令..."

if [ "$(id -u)" -eq 0 ] || [ -w /usr/local/bin ]; then
    cat > "$VOTX_BIN" << ENTRY
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python3" "$REPO_DIR/votx.py" "\$@"
ENTRY
    chmod +x "$VOTX_BIN"
    echo "  /usr/local/bin/votx  [OK]"
else
    echo -e "  ${YELLOW}需要 sudo 写入 /usr/local/bin${NC}"
    sudo tee "$VOTX_BIN" > /dev/null << ENTRY
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python3" "$REPO_DIR/votx.py" "\$@"
ENTRY
    sudo chmod +x "$VOTX_BIN"
    echo "  /usr/local/bin/votx  [OK]"
fi

# ---- 5. 配置 ----
ENV_FILE="$REPO_DIR/.env"
ENV_EXAMPLE="$REPO_DIR/.env.example"
NEED_CONFIG=false

if [ ! -f "$ENV_FILE" ]; then
    NEED_CONFIG=true
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    fi
elif grep -q "sk-your-key-here" "$ENV_FILE" 2>/dev/null; then
    NEED_CONFIG=true
fi

echo ""
echo "[5/5] 创建用户..."
echo ""
echo -e "  votx-agent 支持两种 Key 配置方式:"
echo "    A) 每用户独立 Key — 通过 set_user.py 创建用户，在用户配置中设置"
echo "    B) 全局 .env Key  — 在 .env 文件中设置 DEEPSEEK_API_KEY"
echo ""

read -p "  是否现在创建用户？(Y/n): " -r CREATE_USER
CREATE_USER=${CREATE_USER:-y}

if [[ "$CREATE_USER" =~ ^[Yy] ]]; then
    echo ""
    "$VENV_DIR/bin/python3" "$REPO_DIR/set_user.py" add
    echo ""
    echo -e "  ${GREEN}用户创建完成${NC}"
else
    if $NEED_CONFIG; then
        echo ""
        echo -e "  ${YELLOW}.env 模板已创建，之后可编辑:${NC}"
        echo "    DEEPSEEK_API_KEY=sk-your-key-here"
        echo "    获取: https://platform.deepseek.com/api_keys"
    fi
    echo ""
    echo "  之后可随时创建用户:"
    echo "    python set_user.py add"
fi

# ---- 完成 ----
echo ""
echo -e "${GREEN}安装完成！${NC}"
echo ""
echo "使用:"
echo "  votx       启动 Web UI"
echo "  votx web   启动 Web UI"
echo "  votx cli   启动终端对话"
echo "  votx help  查看帮助"
echo ""

# 检查 PATH
if ! echo "$PATH" | grep -q "/usr/local/bin"; then
    echo -e "${YELLOW}注意: /usr/local/bin 不在 PATH 中，可能需要重新登录${NC}"
fi
