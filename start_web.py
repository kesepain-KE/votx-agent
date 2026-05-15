"""votx-agent Web UI 启动入口

用法:
    python start_web.py              # 默认端口 1478，冲突自动轮询
    python start_web.py --port=8080  # 自定义端口

启动时自动检测用户，无用户则交互式创建后再启动。
"""
import os
import socket
import sys

from paths import get_project_root
_root = get_project_root()
sys.path.insert(0, _root)


def _check_users() -> bool:
    """检查是否存在至少一个用户（users/<name>/config.json），无则引导创建。返回 True 表示可继续启动。"""
    users_dir = os.path.join(_root, "users")
    if not os.path.isdir(users_dir):
        os.makedirs(users_dir, exist_ok=True)

    existing = [
        d for d in os.listdir(users_dir)
        if os.path.isdir(os.path.join(users_dir, d))
        and os.path.exists(os.path.join(users_dir, d, "config.json"))
    ]
    if existing:
        return True

    print("\n" + "=" * 50)
    print("  欢迎使用 votx-agent！")
    print("  检测到没有用户，请先创建一个用户。")
    print("=" * 50)

    try:
        from set_user import add_user
        name = add_user()
        if name:
            print("\n用户创建成功，正在启动 Web UI...\n")
            return True
        else:
            print("\n用户创建失败或已取消。")
            return False
    except Exception as e:
        print(f"\n用户创建出错: {e}")
        return False


port = 1478
for arg in sys.argv:
    if arg.startswith("--port="):
        port = int(arg.split("=")[1])
        break

try:
    from web.server import run_server
except ModuleNotFoundError as e:
    if e.name == "flask":
        print("ERROR: Web UI 依赖 Flask 未安装")
        print("请在当前 Python 环境执行:")
        print("  python -m pip install flask")
        sys.exit(1)
    raise

# 端口冲突自动轮询（最多尝试 10 次）
max_tries = 10
for offset in range(max_tries):
    try_port = port + offset
    # 快速检测端口是否占用
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    in_use = sock.connect_ex(("127.0.0.1", try_port)) == 0
    sock.close()
    if in_use:
        if offset == 0:
            print(f"端口 {try_port} 已被占用，正在轮询...")
        continue
    if offset > 0:
        print(f"已切换到端口 {try_port}")

    # 启动前检测用户
    if not _check_users():
        sys.exit(1)

    run_server(port=try_port, host="127.0.0.1")
    break
else:
    print(f"ERROR: 端口 {port}~{port + max_tries - 1} 全部被占用，无法启动")
    sys.exit(1)
