"""核心聊天路由 — index, users, session, chat SSE, command, disconnect"""
import json
import os
import traceback
import uuid
from pathlib import Path

from flask import Response, jsonify, render_template, request, send_file, stream_with_context, session as flask_session

from web.server import app
from web.session import (
    _root,
    cancel_active_run,
    clear_session,
    get_or_restore_session,
    get_session,
    init_user_session,
    require_session,
    start_active_run,
    clear_active_run,
)
from web.commands import _dispatch
from run.user_locks import get_user_lock


# ---- 启动时清理残留的 .running flag 文件 ----
def _cleanup_stale_running_flags():
    """扫描所有用户的 task-plan 目录，删除残留的 .plan_*.json.running 文件。"""
    users_root = os.path.join(_root, "users")
    if not os.path.isdir(users_root):
        return
    for user_name in os.listdir(users_root):
        plans_dir = os.path.join(users_root, user_name, "task-plan")
        if not os.path.isdir(plans_dir):
            continue
        for name in os.listdir(plans_dir):
            if name.startswith(".plan_") and name.endswith(".json.running"):
                try:
                    os.remove(os.path.join(plans_dir, name))
                except Exception:
                    pass


_cleanup_stale_running_flags()


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


def _auto_resume_paused_plans(user_dir: str):
    """用户发送新消息时，自动将所有已暂停的计划恢复为执行中"""
    import json as _json, os as _os
    plans_dir = _os.path.join(user_dir, "task-plan")
    if not _os.path.isdir(plans_dir):
        return
    modified = False
    for name in sorted(_os.listdir(plans_dir)):
        if not name.endswith(".json"):
            continue
        plan_path = _os.path.join(plans_dir, name)
        try:
            with open(plan_path, encoding="utf-8") as f:
                plan = _json.load(f)
            if plan.get("status") == "paused":
                plan["status"] = "in_progress"
                with open(plan_path, "w", encoding="utf-8") as f:
                    _json.dump(plan, f, ensure_ascii=False, indent=2)
                modified = True
        except Exception:
            pass
    if modified:
        from run.prompt_cache import invalidate_prompt_cache
        invalidate_prompt_cache(user_dir)


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
            # 检测步骤的任何变化（状态、描述、参数、结果）
            if (os.get("status") != ns.get("status")
                    or os.get("description") != ns.get("description")
                    or os.get("result") != ns.get("result")
                    or os.get("error") != ns.get("error")):
                events.append({
                    "type": "plan_step",
                    "plan_id": pid,
                    "step": {
                        "id": sid,
                        "status": ns["status"],
                        "description": ns.get("description", ""),
                        "result": ns.get("result"),
                        "error": ns.get("error"),
                    },
                })

    return events


def _run_chat_stream(session_data: dict, extra_user_message: str | None = None,
                     user_message: str | None = None, cancel_event=None):
    """公共 SSE 聊天执行流 — 供 /api/chat 和 /api/task-plan/<id>/approve-run 共用

    Args:
        session_data: 会话数据字典
        extra_user_message: 可选，临时注入的内部用户消息（不持久化）
        user_message: 可选，用户真实消息（持久化，在 SSE 流内写入以支持压缩状态通知）
    """
    from run.engine import run_chat_turn

    chat = session_data["chat"]
    tool_runner = session_data["tool_runner"]
    provider = session_data["provider"]
    tools = session_data["tools"]
    user_dir = session_data.get("user_dir", "")
    user_name = session_data.get("user_name", "")

    chat.refresh_system_prompt(_root)
    tool_runner.reset_count()

    from plugins.auto_improve.tool import set_auto_improve_context
    from plugins.task_plan.tool import set_task_plan_context
    from plugins._common import set_multimodal_context
    set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    set_multimodal_context(provider=provider, chat=chat, user_name=user_name)

    # 清除上一轮可能遗留的压缩 flag（save_log 中的 build_messages 可能设置它）
    chat._compress_occurred = False

    # 按对象引用注入临时内部消息，finally 中按引用安全删除（避免 index pop 受历史裁剪影响）
    internal_msg = None
    if extra_user_message:
        internal_msg = {"role": "user", "content": extra_user_message, "internal": True}
        chat.messages.append(internal_msg)

    # add_user_message 可能触发 _trim_if_needed（含 auto_improve），耗时较长。
    # 先做无副作用预判，压缩可能时发 ui_status 通知前端，让用户看到"进行中"。
    if user_message:
        est_compress = len(chat.messages) >= getattr(chat, 'max_history', 999999)
        if not est_compress:
            sys_prompt = getattr(chat, 'system_prompt', '')
            est_msgs = [{"role": "system", "content": sys_prompt}] if sys_prompt else []
            est_msgs.extend(chat.messages)
            est_msgs.append({"role": "user", "content": user_message})
            context_max = getattr(chat, 'context_max', 200000)
            safe_ratio = getattr(chat, 'context_safe_ratio', 0.85)
            est_compress = sum(chat._msg_tokens(m) for m in est_msgs) > context_max * safe_ratio
        if est_compress:
            yield f"data: {json.dumps({'type': 'ui_status', 'content': '正在压缩上下文...'}, ensure_ascii=False)}\n\n"
        chat.add_user_message(user_message)
        if est_compress:
            yield f"data: {json.dumps({'type': 'ui_status_clear'}, ensure_ascii=False)}\n\n"

    def _emit_compress_status():
        """消费 _compress_occurred flag 并发出 ui_status 事件对."""
        if getattr(chat, '_compress_occurred', False):
            chat._compress_occurred = False
            yield f"data: {json.dumps({'type': 'ui_status', 'content': '正在压缩上下文...'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'ui_status_clear'}, ensure_ascii=False)}\n\n"

    prev_snap = _snapshot_plans(user_dir)
    try:
        # 预检：压缩可能在 run_chat_turn 第一个 event 之前已发生（add_user_message / build_messages）
        yield from _emit_compress_status()
        for event in run_chat_turn(chat, tool_runner, provider, tools, cancel_event=cancel_event):
            yield from _emit_compress_status()
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
        # 按对象引用安全删除（build_messages 可能裁剪历史，不能用 index pop）
        if internal_msg is not None and internal_msg in chat.messages:
            chat.messages.remove(internal_msg)
        # 先删 internal 再 save，确保 save_log 不会写入内部指令
        try:
            curr_snap = _snapshot_plans(user_dir)
            for pe in _diff_plans(prev_snap, curr_snap):
                yield f"data: {json.dumps(pe, ensure_ascii=False)}\n\n"
        except Exception:
            pass
        try:
            # build_messages 可能触发 token 压缩并改写 chat.messages；
            # 先拿 full_messages 再 save_history，确保压缩版持久化到 chat_data.json
            full_messages = chat.build_messages()
            chat.save_history()
            chat.save_log(full_messages)
            chat._compress_occurred = False  # 清零本轮压缩 flag，避免遗留到下一请求
        except Exception:
            pass
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.route("/")
def index():
    """处理 index 相关逻辑。"""
    return render_template("index.html")


@app.route("/api/users")
def api_users():
    """返回用户列表及 provider 元数据。"""
    users_dir = os.path.join(_root, "users")
    try:
        names = sorted(os.listdir(users_dir))
    except OSError:
        names = []
    result = []
    for name in names:
        user_dir = os.path.join(users_dir, name)
        if not os.path.isdir(user_dir):
            continue
        provider_type = ""
        model = ""
        try:
            cfg_path = os.path.join(user_dir, "config.json")
            if os.path.isfile(cfg_path):
                from set_user import ensure_user_skeleton
                ensure_user_skeleton(Path(user_dir))
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                p = cfg.get("provider", {})
                provider_type = p.get("type", "")
                model = p.get("model", "")
        except Exception:
            pass
        result.append({"name": name, "provider_type": provider_type, "model": model})
    return jsonify(result)


AVATAR_NAMES = ["avatar.jpg", "avatar.png", "avatar.jpeg", "avatar.webp", "avatar.gif"]
AVATAR_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}


@app.route("/api/avatar/<username>")
def api_avatar_public(username):
    """公开头像接口 — 不需要 session，用于登录前显示。"""
    user_dir = os.path.join(_root, "users", os.path.basename(username))
    avatar_dir = os.path.join(user_dir, "avatar")
    if not os.path.isdir(avatar_dir):
        return "", 204
    for name in AVATAR_NAMES:
        path = os.path.join(avatar_dir, name)
        if os.path.isfile(path):
            ext = os.path.splitext(name)[1].lower()
            mime = AVATAR_MIME.get(ext, "image/jpeg")
            response = send_file(path, mimetype=mime, as_attachment=False, conditional=True)
            response.headers["Cache-Control"] = "public, max-age=300"
            return response
    return "", 204


@app.route("/api/select-user", methods=["POST"])
def api_select_user():
    """处理 api_select_user 相关逻辑。"""
    data = request.get_json() or {}
    user_name = data.get("user", "").strip()
    if not user_name:
        return jsonify({"error": "缺少 user 参数"}), 400

    # 校验用户名安全：拒绝路径穿越字符
    if "/" in user_name or "\\" in user_name or ".." in user_name:
        return jsonify({"error": "非法用户名"}), 400

    # 可选的访问口令鉴权
    access_token = os.environ.get("VOTX_ACCESS_TOKEN", "")
    if access_token:
        token = data.get("token", "")
        if token != access_token:
            return jsonify({"error": "访问口令错误"}), 401

    user_dir = os.path.realpath(os.path.join(_root, "users", user_name))
    users_root = os.path.realpath(os.path.join(_root, "users"))
    # 路径 containment 双重保障
    if not user_dir.startswith(users_root + os.sep) and user_dir != users_root:
        return jsonify({"error": "非法用户名"}), 400
    if not os.path.isdir(user_dir):
        return jsonify({"error": f"用户目录不存在: {user_name}"}), 400

    try:
        from set_user import ensure_user_skeleton
        ensure_user_skeleton(Path(user_dir))
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
    """处理 api_session 相关逻辑。"""
    user_name = flask_session.get("user_name")
    session_data = get_or_restore_session(user_name) if user_name else None
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
    session_data, err, code = require_session()
    if err:
        return err, code

    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "会话无效"}), 400

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    run_id = str(data.get("run_id") or "").strip() or uuid.uuid4().hex
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    if message.startswith("/"):
        with get_user_lock(session_data.get("user_name", "")):
            result = _dispatch(message, session_data)
        if result is None:
            result = {"type": "command_result", "content": f"未知命令: {message}"}
        return jsonify(result)

    def generate():
        """处理 generate 相关逻辑。"""
        with get_user_lock(session_data.get("user_name", "")):
            _auto_resume_paused_plans(session_data.get("user_dir", ""))
            cancel_event = start_active_run(session_data, run_id)
            try:
                yield from _run_chat_stream(session_data, user_message=message, cancel_event=cancel_event)
            finally:
                clear_active_run(session_data, run_id)

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
    session_data, err, code = require_session()
    if err:
        return err, code

    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "会话无效"}), 400

    data = request.get_json() or {}
    cmd = data.get("command", "").strip()
    if not cmd:
        return jsonify({"error": "命令不能为空"}), 400

    with get_user_lock(session_data.get("user_name", "")):
        result = _dispatch(cmd, session_data)
    if result is None:
        result = {"type": "command_result", "content": f"未知命令: {cmd}"}
    return jsonify(result)


@app.route("/api/chat/stop", methods=["POST"])
def api_chat_stop():
    """Cancel the currently active chat/task-plan run."""
    session_data, err, code = require_session()
    if err:
        return err, code

    data = request.get_json(silent=True) or {}
    run_id = str(data.get("run_id") or "").strip()
    stopped = cancel_active_run(session_data, run_id or None)
    return jsonify({"ok": True, "stopped": stopped})


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    """断开当前会话，自动生成摘要后保存"""
    from web.commands import _web_summarize
    user_name = flask_session.get("user_name")
    if not user_name:
        return jsonify({"ok": True})
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"ok": True})

    chat = session_data.get("chat")
    if chat:
        try:
            _web_summarize(session_data)
            full_messages = chat.build_messages()
            chat.save_history()
            chat.save_log(full_messages)
        except Exception:
            pass

    clear_session(user_name)
    flask_session.pop("user_name", None)
    return jsonify({"ok": True})
