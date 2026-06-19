"""votx-agent Web UI — Flask + SSE 流式聊天"""
import json
import mimetypes
import os
import sys
import traceback

# 修复 Windows SSL_CERT_FILE 问题
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from flask import Flask, jsonify
from paths import get_project_root

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# 项目根路径（dev / PyInstaller 通用）
_root = get_project_root()
if _root not in sys.path:
    sys.path.insert(0, _root)

app = Flask(
    __name__,
    static_folder=os.path.join(_root, "web", "dist"),
    static_url_path="",
    template_folder=os.path.join(_root, "web", "dist"),
)
app.config["SESSION_COOKIE_NAME"] = os.environ.get("VOTX_SESSION_COOKIE_NAME", "votx_agent_session")

# Flask session cookie secret key — 优先读环境变量，否则用项目根路径 hash 生成
_secret = os.environ.get("VOTX_SECRET_KEY")
if not _secret:
    _secret_path = os.path.join(_root, ".session_secret")
    if os.path.exists(_secret_path):
        with open(_secret_path, "r", encoding="utf-8") as f:
            _secret = f.read().strip()
    if not _secret:
        import secrets
        _secret = secrets.token_hex(32)
        with open(_secret_path, "w", encoding="utf-8") as f:
            f.write(_secret)
app.secret_key = _secret


# ---- Error Handlers ----

@app.errorhandler(500)
def handle_500(e):
    """处理 handle_500 相关逻辑。"""
    traceback.print_exc()
    return jsonify({"error": f"服务器内部错误: {e}"}), 500


@app.errorhandler(404)
def handle_404(e):
    """处理 handle_404 相关逻辑。"""
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(Exception)
def handle_all(e):
    """处理 handle_all 相关逻辑。"""
    traceback.print_exc()
    return jsonify({"error": f"请求处理错误: {e}"}), 500


# ---- 路由注册（在 app 创建之后导入，避免循环依赖） ----

from web.routes import chat, files, conversations, system, config, tasks, task_plan  # noqa: E402,F401


# ---- Runner ----

class PortBindError(OSError):
    """端口绑定失败 —— 供 start_web.py 区分"需要换端口重试"和"真实启动错误"。"""


def run_server(port=13579, host="127.0.0.1"):
    """启动 Web UI + 后台调度 + 消息路由。

    先用 werkzeug make_server 真实绑定端口，成功后再启动 cron/message router，
    最后 serve_forever()。端口占用时抛出 PortBindError，调用方可据此重试下一端口；
    其他异常（配置缺失、导入失败等）直接透传，不会被误判为端口冲突。
    """
    import atexit
    from werkzeug.serving import make_server

    # 1. 先创建并绑定服务器 —— 端口占用在此处失败，无后台副作用
    try:
        server = make_server(host, port, app, threaded=True)
    except (OSError, SystemExit) as e:
        # Windows 上端口占用时 werkzeug 可能抛 SystemExit(1) 而非 OSError
        code = getattr(e, "code", "")
        msg = f"{host}:{port}" + (f" (code={code})" if code else "")
        raise PortBindError(msg) from e
    if host in ("0.0.0.0", "::", "*", ""):
        print(f"\n  votx-agent Web UI  →  http://localhost:{port}")
        print(f"  局域网访问地址       →  http://<本机局域网IP>:{port}\n")
    else:
        display_host = "localhost" if host in ("127.0.0.1", "localhost") else host
        print(f"\n  votx-agent Web UI  →  http://{display_host}:{port}\n")

    # 2. 端口确认可用后，再启动后台组件
    import json
    from paths import get_project_root
    _root = get_project_root()
    with open(os.path.join(_root, "config", "config_core.json"), encoding="utf-8") as f:
        _core_config = json.load(f)
    from cron import start_cron, stop_cron
    start_cron(_root, _core_config, web_mode=True)
    atexit.register(stop_cron)

    from message import start_message_router, stop_message_router
    start_message_router(_root, _core_config)
    atexit.register(stop_message_router)

    # 3. 开始服务（阻塞）
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    run_server()
