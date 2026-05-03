"""核心聊天路由 — index, users, session, chat SSE, command, disconnect"""
import json
import os

from flask import Response, jsonify, render_template, request, stream_with_context

from web.server import app
from web.session import _session, _init_session
from web.commands import _dispatch


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/users")
def api_users():
    from web.session import _root
    users_dir = os.path.join(_root, "users")
    try:
        names = sorted(os.listdir(users_dir))
    except OSError:
        names = []
    return jsonify([n for n in names if os.path.isdir(os.path.join(users_dir, n))])


@app.route("/api/select-user", methods=["POST"])
def api_select_user():
    data = request.get_json() or {}
    user_name = data.get("user", "").strip()
    if not user_name:
        return jsonify({"error": "缺少 user 参数"}), 400
    result = _init_session(user_name)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/session")
def api_session():
    if not _session.get("chat"):
        return jsonify({"active": False})
    chat = _session["chat"]
    return jsonify({
        "active": True,
        "user": _session.get("user_name"),
        "message_count": len(chat.messages),
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """SSE 流式聊天端点"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    if message.startswith("/"):
        result = _dispatch(message)
        if result is None:
            result = {"type": "command_result", "content": f"未知命令: {message}"}
        return jsonify(result)

    from run.engine import run_chat_turn

    tool_runner = _session["tool_runner"]
    provider = _session["provider"]
    tools = _session["tools"]

    chat.add_user_message(message)
    tool_runner.reset_count()

    def generate():
        try:
            for event in run_chat_turn(chat, tool_runner, provider, tools):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            try:
                chat.save_history()
                chat.save_log(chat.build_messages())
            except Exception:
                pass
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/command", methods=["POST"])
def api_command():
    """非流式命令端点"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    cmd = data.get("command", "").strip()
    if not cmd:
        return jsonify({"error": "命令不能为空"}), 400

    result = _dispatch(cmd)
    if result is None:
        result = {"type": "command_result", "content": f"未知命令: {cmd}"}
    return jsonify(result)


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    """断开当前会话，自动生成摘要后保存"""
    from web.commands import _web_summarize
    chat = _session.get("chat")
    if chat:
        try:
            _web_summarize()
            chat.save_history()
            chat.save_log(chat.build_messages())
        except Exception:
            pass
    _session.clear()
    return jsonify({"ok": True})
