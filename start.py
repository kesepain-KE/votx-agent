"""kesepain-Agent 启动入口

用法:
    python start.py           # CLI 模式（选择用户 → subprocess main.py）
    python start.py --web     # Web UI 模式（端口 13579）
    python start.py --web --port=8080   # Web UI 自定义端口
"""
import os
import subprocess
import sys

root = os.path.dirname(__file__)


def main_cli():
    """CLI 模式：列出用户 → 选择 → 子进程 main.py"""
    users_dir = os.path.join(root, "users")
    user_list = sorted(os.listdir(users_dir))
    print("请选择当前用户:")
    for i, name in enumerate(user_list, 1):
        print(f"{i}: {name}")

    try:
        idx = int(input("请输入选择: ")) - 1
        selected = user_list[idx]
    except (ValueError, IndexError):
        print("无效选择")
        sys.exit(1)

    user_dir = os.path.join(users_dir, selected)
    print(f"已加载用户: {selected}")

    subprocess.run(
        [sys.executable, os.path.join(root, "main.py")],
        env={**os.environ, "KESEPAIN_USER_DIR": user_dir},
    )


def main_web():
    """Web UI 模式"""
    port = 13579
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
            print("  python -m pip install -r requirements.txt")
            print("或仅安装 Web 依赖:")
            print("  python -m pip install flask")
            sys.exit(1)
        raise
    run_server(port=port)


if __name__ == "__main__":
    if "--web" in sys.argv:
        main_web()
    else:
        main_cli()
