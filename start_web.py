"""votx-agent Web UI 启动入口

用法:
    python start_web.py              # 默认端口 1478，冲突自动轮询
    python start_web.py --port=8080  # 自定义端口
    python start_web.py --host=0.0.0.0 --port=1478  # 开放局域网访问

启动时自动检测用户，无用户则交互式创建后再启动。
"""
import os
import base64
import json
import platform
import socket
import sys
import threading
import urllib.request
from pathlib import Path

from paths import get_project_root
_root = get_project_root()
sys.path.insert(0, _root)


def _load_dotenv():
    """加载项目 .env，让 Web 监听地址、端口等启动变量在入口处生效。"""
    for env_path in (
        os.path.join(_root, ".env"),
        os.path.join(os.getcwd(), ".env"),
    ):
        try:
            if not os.path.isfile(env_path):
                continue
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass


_load_dotenv()


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
        try:
            from set_user import ensure_user_skeleton
            for name in existing:
                ensure_user_skeleton(Path(users_dir) / name)
        except Exception as exc:
            print(f"警告: 补齐用户目录骨架失败: {exc}")
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


def _read_local_version() -> str:
    try:
        with open(os.path.join(_root, "version.json"), encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("version", "")).strip() or "unknown"
    except Exception:
        return "unknown"


def _version_tuple(value: str) -> tuple[int, ...] | None:
    parts = value.strip().split(".")
    if not parts or any(not p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _compare_versions(left: str, right: str) -> int:
    a = _version_tuple(left)
    b = _version_tuple(right)
    if a is None or b is None:
        return 0
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _print_version_status():
    """后台检测远程版本（非阻塞），仅打印提示，不执行更新。"""
    if os.environ.get("VOTX_SKIP_VERSION_CHECK", "").strip() in ("1", "true", "yes"):
        return

    local_version = _read_local_version()

    def _read_remote_version() -> str:
        urls = []
        custom_url = os.environ.get("VOTX_VERSION_URL", "").strip()
        if custom_url:
            urls.append(("custom", custom_url))
        urls.extend([
            ("raw", "https://raw.githubusercontent.com/kesepain-KE/votx-agent/main/version.json"),
            ("api", "https://api.github.com/repos/kesepain-KE/votx-agent/contents/version.json?ref=main"),
            ("cdn", "https://cdn.jsdelivr.net/gh/kesepain-KE/votx-agent@main/version.json"),
        ])

        last_error = None
        for source, url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "votx-agent-version-check"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if source == "api" and isinstance(data, dict) and "content" in data:
                    raw = base64.b64decode(str(data["content"]).encode("ascii")).decode("utf-8")
                    data = json.loads(raw)
                version = str(data.get("version", "")).strip()
                if version:
                    return version
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(last_error or "all version endpoints failed")

    def _worker():
        try:
            remote_version = _read_remote_version()
        except Exception as e:
            print(f"[版本] 本地 {local_version}；远程版本检查未完成，已跳过。({e})")
            return

        cmp_result = _compare_versions(local_version, remote_version)
        if cmp_result < 0:
            print(f"[版本] 本地 {local_version}；远程 {remote_version}。发现新版本，可运行 python update.py 更新。")
        elif cmp_result > 0:
            print(f"[版本] 本地 {local_version}；远程 {remote_version}。本地版本高于 main 发布版本。")
        else:
            print(f"[版本] 本地 {local_version}；远程 {remote_version}。当前已是最新版本。")

    threading.Thread(target=_worker, daemon=True, name="version-check").start()


port = int(os.environ.get("PORT", "1478"))
host = os.environ.get("VOTX_HOST", "127.0.0.1")
for arg in sys.argv:
    if arg.startswith("--port="):
        port = int(arg.split("=")[1])
    elif arg.startswith("--host="):
        host = arg.split("=", 1)[1].strip() or host

try:
    from web.server import run_server, PortBindError
except ModuleNotFoundError as e:
    if e.name == "flask":
        print("ERROR: Web UI 依赖 Flask 未安装")
        print("请在当前 Python 环境执行:")
        print("  python -m pip install flask")
        sys.exit(1)
    raise

if not _check_users():
    sys.exit(1)

_print_version_status()


def _can_bind(host: str, port: int) -> tuple[bool, str]:
    probe_host = host if host not in ("", "*") else "0.0.0.0"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((probe_host, port))
        return True, ""
    except OSError as e:
        return False, str(e)
    finally:
        sock.close()


# 端口冲突自动轮询（最多尝试 10 次）
max_tries = 10
for offset in range(max_tries):
    try_port = port + offset
    can_bind, bind_error = _can_bind(host, try_port)
    if not can_bind:
        if offset == 0:
            print(f"端口 {try_port} 不可用，正在轮询... ({bind_error})")
        continue
    if offset > 0:
        print(f"已切换到端口 {try_port}")
    try:
        run_server(port=try_port, host=host)
        break
    except PortBindError as e:
        print(f"端口 {try_port} 绑定失败: {e}")
        if offset == 0:
            print("正在尝试下一个端口...")
        continue
else:
    print(f"ERROR: 端口 {port}~{port + max_tries - 1} 全部被占用，无法启动")
    sys.exit(1)
