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
echo "[1/6] 检查 Python..."
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo "")
if [ -z "$PYTHON" ]; then
    echo -e "${RED}错误: 未找到 Python，请先安装 Python >= 3.10${NC}"
    exit 1
fi

PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
PY_MAJOR=$($PYTHON --version 2>&1 | awk '{print $2}' | cut -d. -f1)
PY_MINOR=$($PYTHON --version 2>&1 | awk '{print $2}' | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}错误: Python >= 3.10 需要，当前版本: $PY_VER${NC}"
    exit 1
fi
echo "  Python $PY_VER  [OK]"

# ---- 2. 检查 Node.js ----
echo "[2/6] 检查 Node.js..."
NODE=$(which node 2>/dev/null || echo "")
NPM=$(which npm 2>/dev/null || echo "")
if [ -n "$NODE" ] && [ -n "$NPM" ]; then
    NODE_VER=$($NODE --version 2>&1)
    echo "  Node.js $NODE_VER  [OK]"
    HAS_NODE=true
else
    echo -e "  ${YELLOW}未找到 Node.js，无法构建 React 前端${NC}"
    echo "  Web UI 需要 web/dist/index.html。请安装 Node.js >= 18 后重新运行安装脚本，或手动执行: cd web && npm install && npm run build"
    HAS_NODE=false
fi

# ---- 3. 创建虚拟环境 ----
echo "[3/6] 创建虚拟环境..."
$PYTHON -m venv "$VENV_DIR"
echo "  .venv 已创建"

# ---- 4. 安装依赖 ----
echo "[4/6] 安装 Python 依赖..."
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
echo "  Python 依赖安装完成"

# ---- 4.5 安装并构建前端 ----
if $HAS_NODE; then
    echo "  安装并构建 React 前端..."
    cd "$REPO_DIR/web"
    if ! $NPM install --silent; then
        echo -e "  ${RED}npm install 失败，前端无法构建${NC}"
        exit 1
    fi
    if ! $NPM run build; then
        echo -e "  ${RED}npm run build 失败，Web UI 将不可用${NC}"
        exit 1
    fi
    cd "$REPO_DIR"
    echo "  React 前端构建完成"
fi

# ---- 5. 注册 votx 命令 ----
echo "[5/6] 注册 votx 命令..."

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

# ---- 6. 配置 ----
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
echo "[6/6] 创建用户..."
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
if [ ! -f "$REPO_DIR/web/dist/index.html" ]; then
    echo -e "${YELLOW}注意: 未检测到 web/dist/index.html，Web UI 暂不可用${NC}"
    echo "      安装 Node.js >= 18 后执行: cd web && npm install && npm run build"
    echo ""
fi
if $HAS_NODE; then
    echo "前端开发:"
    echo "  cd web && npm run dev   Vite 开发服务器"
    echo "  cd web && npm run build 生产构建"
    echo ""
fi

# 检查 PATH
if ! echo "$PATH" | grep -q "/usr/local/bin"; then
    echo -e "${YELLOW}注意: /usr/local/bin 不在 PATH 中，可能需要重新登录${NC}"
fi
