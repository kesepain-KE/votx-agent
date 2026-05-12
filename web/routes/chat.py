"""核心聊天路由 — index, users, session, chat SSE, command, disconnect"""
import json
import os
import traceback

from flask import Response, jsonify, render_template, request, stream_with_context, session as flask_session

from web.server import app
from web.session import _root, get_session, get_active_user, clear_session, init_user_session
from web.commands import _dispatch


def _snapshot_plans(user_dir: str) -> dict[str, dict]:
    """扫描用户 task-plan 目录，返回 {plan_id: plan} 快照"""
    plans_dir = os.path.join(user_dir, "task-plan")
    if not os.path.isdir(plans_dir):
        return {}
    snap = {}
    for name in sorted(os.listdir(plans_dir)):
        if name.endswith(".json"):
            try:
                with open(os.path.join(plans_dir, name), encoding="utf-8") as f:
                    plan = json.load(f)
                pid = plan.get("id", name.replace(".json", ""))
                snap[pid] = plan
            except Exception:
                pass
    return snap


def _diff_plans(prev: dict, curr: dict) -> list[dict]:
    """比较前后快照，返回需要推送的 SSE 事件列表"""
    events = []
    prev_ids = set(prev.keys())
    curr_ids = set(curr.keys())

    # 新增计划
    for pid in curr_ids - prev_ids:
        plan = curr[pid]
        events.append({"type": "plan_created", "plan": plan, "plan_id": pid})

    # 已有计划变化
    for pid in curr_ids & prev_ids:
        old = prev[pid]
        new = curr[pid]
        if old == new:
            continue
        # 状态变化
        if old.get("status") != new.get("status"):
            if new["status"] == "completed":
                events.append({"type": "plan_complete", "plan_id": pid, "plan": new})
            elif new["status"] == "paused":
                events.append({"type": "plan_pause", "plan_id": pid, "plan": new})
            elif new["status"] == "aborted":
                events.append({"type": "plan_aborted", "plan_id": pid, "plan": new})
            elif new["status"] == "in_progress":
                events.append({"type": "plan_started", "plan_id": pid, "plan": new})
        # 步骤变化
        old_steps = {s["id"]: s for s in old.get("steps", [])}
        new_steps = {s["id"]: s for s in new.get("steps", [])}
        for sid, ns in new_steps.items():
            os = old_steps.get(sid, {})
            if os.get("status") != ns.get("status"):
                events.append({
                    "type": "plan_step",
                    "plan_id": pid,
                    "step": {"id": sid, "status": ns["status"],
                             "result": ns.get("result"), "error": ns.get("error")},
                })

    return events


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/users")
def api_users():
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

    user_dir = os.path.join(_root, "users", user_name)
    if not os.path.isdir(user_dir):
        return jsonify({"error": f"用户目录不存在: {user_name}"}), 400

    try:
        with open(os.path.join(_root, "config", "config_core.json"), encoding="utf-8") as f:
            core_config = json.load(f)
        with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
            user_config = json.load(f)
    except Exception as e:
        return jsonify({"error": f"读取配置失败: {e}"}), 400

    try:
        init_user_session(_root, user_dir, user_name, user_config, core_config)
        flask_session["user_name"] = user_name
        return jsonify({"ok": True, "user": user_name})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"初始化失败: {e}"}), 400


@app.route("/api/session")
def api_session():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"active": False})
    chat = session_data["chat"]
    return jsonify({
        "active": True,
        "user": session_data.get("user_name"),
        "message_count": len(chat.messages),
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """SSE 流式聊天端点"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400

    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    if message.startswith("/"):
        result = _dispatch(message, session_data)
        if result is None:
            result = {"type": "command_result", "content": f"未知命令: {message}"}
        return jsonify(result)

    from run.engine import run_chat_turn

    tool_runner = session_data["tool_runner"]
    provider = session_data["provider"]
    tools = session_data["tools"]

    chat.add_user_message(message)
    tool_runner.reset_count()
    chat.refresh_system_prompt(_root)

    def generate():
        user_dir = session_data.get("user_dir", "")
        prev_snap = _snapshot_plans(user_dir)
        try:
            for event in run_chat_turn(chat, tool_runner, provider, tools):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                # 工具调用后检查计划文件变化
                if event.get("type") == "tool_call":
                    curr_snap = _snapshot_plans(user_dir)
                    for pe in _diff_plans(prev_snap, curr_snap):
                        yield f"data: {json.dumps(pe, ensure_ascii=False)}\n\n"
                    prev_snap = curr_snap
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            # 最终检查一次计划变化
            try:
                curr_snap = _snapshot_plans(user_dir)
                for pe in _diff_plans(prev_snap, curr_snap):
                    yield f"data: {json.dumps(pe, ensure_ascii=False)}\n\n"
            except Exception:
                pass
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
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400

    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    cmd = data.get("command", "").strip()
    if not cmd:
        return jsonify({"error": "命令不能为空"}), 400

    result = _dispatch(cmd, session_data)
    if result is None:
        result = {"type": "command_result", "content": f"未知命令: {cmd}"}
    return jsonify(result)


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    """断开当前会话，自动生成摘要后保存"""
    from web.commands import _web_summarize
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"ok": True})

    chat = session_data.get("chat")
    if chat:
        try:
            _web_summarize(session_data)
            chat.save_history()
            chat.save_log(chat.build_messages())
        except Exception:
            pass

    clear_session(user_name)
    flask_session.pop("user_name", None)
    return jsonify({"ok": True})
