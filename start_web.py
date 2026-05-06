"""votx-agent Web UI 启动入口

用法:
    python start_web.py              # 默认端口 1478，冲突自动轮询
    python start_web.py --port=8080  # 自定义端口
"""
import os
import socket
import sys

from paths import get_project_root
_root = get_project_root()
sys.path.insert(0, _root)

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
    run_server(port=try_port)
    break
else:
    print(f"ERROR: 端口 {port}~{port + max_tries - 1} 全部被占用，无法启动")
    sys.exit(1)
