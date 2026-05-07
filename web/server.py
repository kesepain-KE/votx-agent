"""votx-agent Web UI — Flask + SSE 流式聊天"""
import json
import os
import sys
import traceback

# 修复 Windows SSL_CERT_FILE 问题
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from flask import Flask, jsonify

# 项目根路径（dev / PyInstaller 通用）
from paths import get_project_root
_root = get_project_root()
if _root not in sys.path:
    sys.path.insert(0, _root)

app = Flask(__name__, template_folder=os.path.join(_root, "web", "templates"))

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
        os.chmod(_secret_path, 0o600)
app.secret_key = _secret


# ---- Error Handlers ----

@app.errorhandler(500)
def handle_500(e):
    traceback.print_exc()
    return jsonify({"error": f"服务器内部错误: {e}"}), 500


@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(Exception)
def handle_all(e):
    traceback.print_exc()
    return jsonify({"error": f"请求处理错误: {e}"}), 500


# ---- 路由注册（在 app 创建之后导入，避免循环依赖） ----

from web.routes import chat, files, conversations, system, config  # noqa: E402,F401


# ---- Runner ----

def run_server(port=13579, host="0.0.0.0"):
    print(f"\n  votx-agent Web UI  →  http://localhost:{port}\n")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
