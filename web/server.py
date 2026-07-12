"""votx-agent Web UI — Flask + SSE 流式聊天"""
import json
import mimetypes
import os
import sys
import traceback

# 修复 Windows SSL_CERT_FILE 问题
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from flask import Flask, jsonify, request, session as flask_session, Response, send_file
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


# ---- Access Token 鉴权 ----

@app.before_request
def _check_access_token():
    """URL token 鉴权：若 VOTX_ACCESS_TOKEN 已设，首次访问需带 ?token=xxx，
    命中后写入 Flask session，后续请求靠 cookie 自动放行。
    未设环境变量时完全不拦截。"""
    access_token = os.environ.get("VOTX_ACCESS_TOKEN", "")
    if not access_token:
        return

    if flask_session.get("authed"):
        return

    # 从 URL query param 获取 token
    token = request.args.get("token", "")
    if token and token == access_token:
        flask_session["authed"] = True
        return

    # 从 Authorization header 获取 token（供 API 客户端使用）
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == access_token:
            flask_session["authed"] = True
            return

    # 未鉴权：API 请求返回 JSON 401，页面请求返回高级白风格提示页
    if request.path.startswith("/api/"):
        return jsonify({"error": "需要提供有效的访问令牌"}), 401

    # 鉴权页使用项目根目录的品牌 Logo；单独放行该静态资源。
    if request.path == "/votx-agent-auth-logo.png":
        return send_file(os.path.join(_root, "votx-agent.png"), mimetype="image/png")

    _auth_page = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>访问验证 · votx-agent</title>
  <style>
    * { box-sizing: border-box; }
    html, body { width: 100%; min-height: 100%; margin: 0; }
    body {
      min-height: 100vh;
      overflow: hidden;
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: #172033;
      background:
        radial-gradient(circle at 18% 15%, rgba(206, 225, 255, .8), transparent 30%),
        radial-gradient(circle at 85% 80%, rgba(222, 237, 255, .75), transparent 34%),
        linear-gradient(145deg, #ffffff 0%, #f7faff 48%, #edf4ff 100%);
      display: grid;
      place-items: center;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(42, 91, 170, .035) 1px, transparent 1px), linear-gradient(90deg, rgba(42, 91, 170, .035) 1px, transparent 1px);
      background-size: 34px 34px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,.65), transparent 86%);
    }
    .shell {
      position: relative;
      width: min(92vw, 520px);
      padding: 46px 42px 40px;
      text-align: center;
      background: rgba(255, 255, 255, .76);
      border: 1px solid rgba(255, 255, 255, .95);
      border-radius: 30px;
      box-shadow: 0 28px 80px rgba(39, 79, 142, .16), 0 2px 12px rgba(52, 92, 155, .07), inset 0 1px 0 #fff;
      backdrop-filter: blur(24px) saturate(1.2);
      -webkit-backdrop-filter: blur(24px) saturate(1.2);
    }
    .logo-wrap {
      width: 154px;
      height: 154px;
      margin: 0 auto 24px;
      display: grid;
      place-items: center;
      border-radius: 36px;
      background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(239,246,255,.88));
      box-shadow: 0 16px 38px rgba(44, 91, 164, .15), inset 0 0 0 1px rgba(135, 171, 226, .18);
    }
    .logo { width: 130px; height: 130px; object-fit: contain; filter: drop-shadow(0 8px 15px rgba(38, 79, 143, .12)); }
    .eyebrow { margin: 0 0 9px; color: #6280ad; font-size: 12px; font-weight: 750; letter-spacing: .2em; text-transform: uppercase; }
    h1 { margin: 0; font-size: clamp(27px, 5vw, 34px); line-height: 1.18; letter-spacing: -.04em; font-weight: 780; color: #18233a; }
    .desc { margin: 14px auto 0; max-width: 370px; color: #657189; font-size: 15px; line-height: 1.75; }
    .hint {
      margin: 24px auto 0;
      padding: 13px 16px;
      border: 1px solid #dce8f8;
      border-radius: 14px;
      background: rgba(246, 250, 255, .86);
      color: #315b98;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .foot { margin-top: 25px; display: flex; align-items: center; justify-content: center; gap: 8px; color: #9aa6b9; font-size: 12px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #69a0ed; box-shadow: 0 0 0 5px rgba(105,160,237,.12); }
    @media (max-width: 560px) {
      .shell { padding: 36px 24px 32px; border-radius: 24px; }
      .logo-wrap { width: 132px; height: 132px; border-radius: 30px; }
      .logo { width: 110px; height: 110px; }
    }
  </style>
</head>
<body>
  <main class="shell" role="main">
    <div class="logo-wrap"><img class="logo" src="/votx-agent-auth-logo.png" alt="votx-agent Logo"></div>
    <p class="eyebrow">Secure Access</p>
    <h1>需要访问令牌</h1>
    <p class="desc">此 votx-agent 实例已启用访问保护。请使用包含有效令牌的专属地址完成首次验证。</p>
    <div class="hint">?token=你的令牌</div>
    <div class="foot"><span class="dot"></span><span>votx-agent · Web Access Control</span></div>
  </main>
</body>
</html>'''
    return Response(_auth_page, status=401, content_type="text/html; charset=utf-8")


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
