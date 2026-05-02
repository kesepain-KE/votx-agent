"""kesepain-Agent Web UI — Flask + SSE 流式聊天"""
import json
import os
import sys
import traceback

# 修复 Windows SSL_CERT_FILE 问题
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# 确保项目根在 path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from provider.openai_api import DeepSeekProvider
from run.chat import ChatManager
from run.engine import build_system_prompt, run_chat_turn
from run.tool import ToolRunner, load_tool_schemas

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

# 会话状态
_session: dict = {}


def _init_session(user_name: str) -> dict:
    """初始化用户会话，返回会话状态"""
    root = _root
    user_dir = os.path.join(root, "users", user_name)

    if not os.path.isdir(user_dir):
        return {"error": f"用户目录不存在: {user_name}"}

    try:
        with open(os.path.join(root, "config", "config_core.json"), encoding="utf-8") as f:
            core_config = json.load(f)
        with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
            user_config = json.load(f)

        provider = DeepSeekProvider(user_config, core_config)
        tool_runner = ToolRunner(core_config, user_config)
        system_prompt = build_system_prompt(root, user_dir)  # 内部调用 register_all() 填充 TOOL_REGISTRY
        tools = load_tool_schemas()  # 必须在 build_system_prompt 之后

        chat = ChatManager(user_dir, core_config, user_config)
        chat.set_system_prompt(system_prompt)
        chat.load_history()

        _session.update({
            "user_name": user_name,
            "user_dir": user_dir,
            "root": root,
            "core_config": core_config,
            "user_config": user_config,
            "provider": provider,
            "tool_runner": tool_runner,
            "tools": tools,
            "chat": chat,
        })
        # 设置环境变量，让 ToolRunner.log_tool_call 能找到日志路径
        os.environ["KESEPAIN_USER_DIR"] = user_dir
        return {"ok": True, "user": user_name}
    except Exception as e:
        traceback.print_exc()
        return {"error": f"初始化失败: {e}"}


from run.summarize import (generate_summary, load_index, save_index,
                           summarize_and_store, sync_to_new_archives)


def _web_summarize() -> str:
    """Web 会话摘要：从 _session 取 provider/messages/user_dir"""
    chat = _session.get("chat")
    provider = _session.get("provider")
    user_dir = _session.get("user_dir")
    if not chat or not provider or not user_dir or not chat.messages:
        return "没有可摘要的内容"
    return summarize_and_store(provider, chat.messages, user_dir)


def _dispatch(cmd: str) -> dict | None:
    """处理斜杠命令，返回 JSON 结果。None 表示不是命令"""
    chat = _session.get("chat")
    if not chat:
        return {"type": "error", "content": "未选择用户"}

    cmd = cmd.strip().lower()
    if cmd in ("/exit", "/quit", "/q"):
        return {"type": "command_result", "content": "Web UI 中请使用侧栏「断开」按钮退出会话。"}
    if cmd == "/clear":
        # 仅清除当前历史 + 工具日志，不保存不归档
        count = len(chat.messages)
        chat.messages = []
        try:
            if os.path.exists(chat.data_path):
                os.remove(chat.data_path)
        except Exception:
            pass
        tl_count = 0
        try:
            if os.path.exists(chat.tool_log_path):
                with open(chat.tool_log_path, encoding="utf-8") as f:
                    tl_count = sum(1 for _ in f)
                os.remove(chat.tool_log_path)
        except Exception:
            pass
        extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
        return {"type": "command_result", "content": f"已清除 {count} 条历史消息{extra}。"}
    if cmd in ("/history", "/stats"):
        return {"type": "command_result", "content": chat.history_stats()}
    if cmd == "/archive":
        _web_summarize()
        before = set()
        archive_dir = os.path.join(_session["user_dir"], "history", "archive")
        if os.path.isdir(archive_dir):
            before = set(os.listdir(archive_dir))
        msg = chat.archive_now()
        sync_to_new_archives(_session["user_dir"], before)
        return {"type": "command_result", "content": msg}
    if cmd in ("/summarize", "/summary", "/总结"):
        summary = _web_summarize()
        return {"type": "command_result", "content": f"对话摘要: {summary}"}
    if cmd == "/retry":
        # 移除最后一条 assistant 回复，返回最后 user 消息让前端重新流式请求
        if not chat.messages:
            return {"type": "command_result", "content": "没有可重试的消息", "retry": False}
        # 找到最后一条 user 消息的索引
        last_user_idx = -1
        for i in range(len(chat.messages) - 1, -1, -1):
            if chat.messages[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx == -1:
            return {"type": "command_result", "content": "没有可重试的消息", "retry": False}
        user_msg = chat.messages[last_user_idx].get("content", "")
        # 截断：保留到该 user 消息为止，移除后续的 assistant/tool 响应
        chat.messages = chat.messages[:last_user_idx]
        chat.save_history()
        return {"type": "command_result", "content": user_msg, "retry": True}
    if cmd == "/help":
        return {"type": "command_result", "content": "/clear 清除历史 | /history 状态 | /archive 归档 | /retry 重试 | /help 帮助"}
    return None


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


# ---- Routes ----

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

    # 斜杠命令直接返回 JSON
    if message.startswith("/"):
        result = _dispatch(message)
        if result is None:
            result = {"type": "command_result", "content": f"未知命令: {message}"}
        return jsonify(result)

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


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """文件上传 — 保存到 users/<name>/history/file/"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    file_dir = os.path.join(user_dir, "history", "file")
    os.makedirs(file_dir, exist_ok=True)

    uploaded = []
    for key in request.files:
        f = request.files[key]
        if f.filename:
            safe_name = os.path.basename(f.filename)
            if not safe_name:
                safe_name = "unnamed"
            dest = os.path.join(file_dir, safe_name)
            base, ext = os.path.splitext(safe_name)
            n = 1
            while os.path.exists(dest):
                dest = os.path.join(file_dir, f"{base}_{n}{ext}")
                n += 1
            f.save(dest)
            uploaded.append({
                "name": os.path.basename(dest),
                "path": os.path.join("users", _session["user_name"], "history", "file", os.path.basename(dest)).replace("\\", "/"),
                "size": os.path.getsize(dest),
            })

    return jsonify({"ok": True, "files": uploaded})


@app.route("/api/files")
def api_files():
    """列出当前用户已上传的文件"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = _session["user_dir"]
    file_dir = os.path.join(user_dir, "history", "file")
    files = []
    if os.path.isdir(file_dir):
        for name in sorted(os.listdir(file_dir)):
            p = os.path.join(file_dir, name)
            if os.path.isfile(p):
                files.append({
                    "name": name,
                    "path": os.path.join("users", _session["user_name"], "history", "file", name).replace("\\", "/"),
                    "size": os.path.getsize(p),
                })
    return jsonify(files)


@app.route("/api/files/view/<filename>")
def api_file_view(filename):
    """提供上传文件的原始内容（用于图片预览等）"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = _session["user_dir"]
    file_dir = os.path.join(user_dir, "history", "file")
    target = os.path.join(file_dir, os.path.basename(filename))
    real_file_dir = os.path.realpath(file_dir)
    real_target = os.path.realpath(target)
    if not real_target.startswith(real_file_dir + os.sep) and real_target != real_file_dir:
        return jsonify({"error": "路径越权"}), 403
    if not os.path.isfile(target):
        return jsonify({"error": "文件不存在"}), 404
    # MIME 类型检测
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".bmp": "image/bmp", ".ico": "image/x-icon",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    return Response(open(target, "rb").read(), mimetype=mime)


@app.route("/api/files/<filename>", methods=["DELETE"])
def api_delete_file(filename):
    """删除指定用户上传的文件（从磁盘）"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    file_dir = os.path.join(user_dir, "history", "file")
    target = os.path.join(file_dir, os.path.basename(filename))

    # 安全检查
    real_file_dir = os.path.realpath(file_dir)
    real_target = os.path.realpath(target)
    if not real_target.startswith(real_file_dir + os.sep) and real_target != real_file_dir:
        return jsonify({"error": "路径越权"}), 403

    if not os.path.isfile(target):
        return jsonify({"error": "文件不存在"}), 404

    try:
        os.remove(target)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"error": f"删除失败: {e}"}), 500


@app.route("/api/files", methods=["DELETE"])
def api_delete_files_batch():
    """批量删除用户上传的文件"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    file_dir = os.path.join(user_dir, "history", "file")
    real_file_dir = os.path.realpath(file_dir)

    # 支持 JSON body 传文件名列表，也支持清空全部
    data = request.get_json(silent=True) or {}
    names = data.get("files", None)

    deleted = 0
    if names is not None:
        for name in names:
            target = os.path.join(file_dir, os.path.basename(name))
            real_target = os.path.realpath(target)
            if real_target.startswith(real_file_dir + os.sep) and os.path.isfile(target):
                try:
                    os.remove(target)
                    deleted += 1
                except OSError:
                    pass
    else:
        # 无文件名列表则清空全部
        if os.path.isdir(file_dir):
            for name in os.listdir(file_dir):
                target = os.path.join(file_dir, name)
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                        deleted += 1
                    except OSError:
                        pass

    return jsonify({"ok": True, "deleted": deleted})


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
    chat = _session.get("chat")
    if chat:
        try:
            _web_summarize()  # 自动摘要
            chat.save_history()
            chat.save_log(chat.build_messages())
        except Exception:
            pass
    _session.clear()
    return jsonify({"ok": True})


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    """删除指定的归档对话文件"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    if conv_id == "__current__":
        return jsonify({"error": "不能删除当前对话"}), 400

    user_dir = _session["user_dir"]
    archive_path = os.path.join(user_dir, "history", "archive", conv_id)

    # 安全检查：确保文件在 archive 目录内
    real_archive = os.path.realpath(os.path.join(user_dir, "history", "archive"))
    real_path = os.path.realpath(archive_path)
    if not real_path.startswith(real_archive + os.sep) and real_path != real_archive:
        return jsonify({"error": "路径越权"}), 403

    if not os.path.exists(archive_path):
        return jsonify({"error": "文件不存在"}), 404

    try:
        os.remove(archive_path)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"error": f"删除失败: {e}"}), 500


@app.route("/api/messages")
def api_messages():
    """返回当前会话的消息列表（不含 system prompt）"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400
    return jsonify(chat.messages)


@app.route("/api/system-prompt")
def api_system_prompt():
    """返回当前会话的 system prompt 及分段内容"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session.get("user_dir", "")
    root = _session.get("root", _root)

    # 读取 soul 源文件
    soul = ""
    soul_path = os.path.join(user_dir, "self_soul.md")
    if os.path.exists(soul_path):
        with open(soul_path, encoding="utf-8") as f:
            soul = f.read()
    global_soul = os.path.join(root, "config", "soul.md")
    if os.path.exists(global_soul) and os.path.getsize(global_soul) > 0:
        with open(global_soul, encoding="utf-8") as f:
            gs = f.read().strip()
            if gs and not gs.startswith("<!--"):
                soul += "\n\n" + gs

    # 读取 AGENT.md
    agent = ""
    agent_md = os.path.join(root, "AGENT.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            agent = f.read()

    # "其他" 部分：skill 目录 + 持久记忆（从完整 system prompt 中提取）
    full = chat.system_prompt
    other = ""
    skill_marker = "## 可用 Skill 目录"
    mem_marker = "## 持久记忆"
    skill_idx = full.find(skill_marker)
    mem_idx = full.find(mem_marker)
    if skill_idx > 0:
        other = full[skill_idx:]
    elif mem_idx > 0:
        other = full[mem_idx:]
    else:
        other = "Skill 摘要、持久记忆等\n\n在完整 prompt 中查看…"

    return jsonify({
        "content": full,
        "soul": soul,
        "agent": agent,
        "other": other,
    })


@app.route("/api/export-markdown")
def api_export_markdown():
    """导出当前对话为 Markdown"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    lines = [f"# kesepain-Agent 对话导出", ""]
    user_name = _session.get("user_name", "unknown")
    from datetime import datetime, timezone
    lines.append(f"**用户**: {user_name}  |  **导出时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for m in chat.messages:
        role = m.get("role", "")
        content = m.get("content", "")
        tool_calls = m.get("tool_calls")

        if role == "user":
            lines.append(f"### 🧑 用户")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            if tool_calls:
                for tc in tool_calls:
                    name = tc.get("function", {}).get("name", "unknown")
                    args = tc.get("function", {}).get("arguments", "{}")
                    try:
                        args_obj = json.loads(args)
                        args_str = json.dumps(args_obj, ensure_ascii=False)
                    except Exception:
                        args_str = args
                    lines.append(f"### 🔧 工具调用: `{name}`")
                    lines.append("")
                    lines.append(f"```json")
                    lines.append(args_str)
                    lines.append(f"```")
                    lines.append("")
            if content:
                lines.append(f"### 🤖 助手")
                lines.append("")
                lines.append(content)
                lines.append("")
        elif role == "tool":
            tid = m.get("tool_call_id", "")[:16]
            lines.append(f"📋 工具结果 `{tid}...`:")
            lines.append("")
            lines.append(f"```")
            lines.append(content[:2000] if len(content) > 2000 else content)
            if len(content) > 2000:
                lines.append(f"...[截断: 原始 {len(content)} 字符]")
            lines.append(f"```")
            lines.append("")

    md = "\n".join(lines)
    return Response(md, mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=conversation.md"})


@app.route("/api/conversations")
def api_conversations():
    """列出当前用户的所有对话（当前 + 归档），含摘要"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = _session["user_dir"]
    archive_dir = os.path.join(user_dir, "history", "archive")
    chat_path = os.path.join(user_dir, "history", "chat", "chat_data.json")
    index = load_index(user_dir)

    conversations = []

    # 当前对话
    if os.path.exists(chat_path):
        try:
            stat = os.stat(chat_path)
            with open(chat_path, encoding="utf-8") as f:
                msgs = json.load(f)
            msg_count = len(msgs) if isinstance(msgs, list) else 0
            meta = index.get("chat_data.json", {})
            conversations.append({
                "id": "__current__",
                "label": "当前对话",
                "msg_count": msg_count,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "summary": meta.get("summary", ""),
            })
        except Exception:
            pass

    # 归档对话
    if os.path.isdir(archive_dir):
        try:
            for name in sorted(os.listdir(archive_dir), reverse=True):
                if name.endswith(".json.gz") or name.endswith(".json"):
                    path = os.path.join(archive_dir, name)
                    stat = os.stat(path)
                    meta = index.get(name, {})
                    raw_label = name.rsplit(".", 1)[0].replace("history_", "")
                    summary = meta.get("summary", "")
                    conversations.append({
                        "id": name,
                        "label": summary or raw_label,
                        "raw_label": raw_label,
                        "msg_count": meta.get("msg_count", 0),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "archived": True,
                        "summary": summary,
                    })
        except OSError:
            pass

    return jsonify(conversations)


@app.route("/api/load-conversation", methods=["POST"])
def api_load_conversation():
    """加载指定的归档对话替换当前对话"""
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    conv_id = data.get("id", "").strip()
    if not conv_id:
        return jsonify({"error": "缺少 id 参数"}), 400

    user_dir = _session["user_dir"]
    chat_path = os.path.join(user_dir, "history", "chat", "chat_data.json")

    try:
        # 保存当前对话并生成摘要
        _web_summarize()
        chat.save_history()
        chat.save_log(chat.build_messages())

        if conv_id == "__current__":
            chat.load_history()
        else:
            archive_path = os.path.join(user_dir, "history", "archive", conv_id)
            if not os.path.exists(archive_path):
                return jsonify({"error": f"归档文件不存在: {conv_id}"}), 404

            # 加载归档文件
            if archive_path.endswith(".gz"):
                import gzip
                with gzip.open(archive_path, "rb") as f:
                    msgs = json.loads(f.read().decode("utf-8"))
            else:
                with open(archive_path, encoding="utf-8") as f:
                    msgs = json.load(f)

            if not isinstance(msgs, list):
                return jsonify({"error": "归档文件格式错误"}), 400

            # 替换当前消息并落盘
            chat.messages = msgs
            chat._repair_tool_chain()
            chat.save_history()

        return jsonify({"ok": True, "msg_count": len(chat.messages)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"加载失败: {e}"}), 500


@app.route("/api/conversations/<conv_id>/rename", methods=["POST"])
def api_rename_conversation(conv_id):
    """重命名归档对话文件"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "缺少 name 参数"}), 400

    user_dir = _session["user_dir"]
    archive_dir = os.path.join(user_dir, "history", "archive")
    old_path = os.path.join(archive_dir, conv_id)

    # 安全检查
    real_archive = os.path.realpath(archive_dir)
    real_old = os.path.realpath(old_path)
    if not real_old.startswith(real_archive + os.sep) and real_old != real_archive:
        return jsonify({"error": "路径越权"}), 403

    if not os.path.exists(old_path):
        return jsonify({"error": "文件不存在"}), 404

    # 保持扩展名
    _, ext = os.path.splitext(conv_id)
    new_filename = new_name + ext
    new_path = os.path.join(archive_dir, new_filename)

    if os.path.exists(new_path):
        return jsonify({"error": "同名文件已存在"}), 409

    try:
        os.rename(old_path, new_path)
        return jsonify({"ok": True, "new_name": new_filename})
    except OSError as e:
        return jsonify({"error": f"重命名失败: {e}"}), 500


@app.route("/api/conversations", methods=["DELETE"])
def api_delete_all_conversations():
    """删除所有归档对话"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    archive_dir = os.path.join(user_dir, "history", "archive")

    if not os.path.isdir(archive_dir):
        return jsonify({"ok": True, "deleted": 0})

    deleted = 0
    for name in os.listdir(archive_dir):
        path = os.path.join(archive_dir, name)
        if os.path.isfile(path) and (name.endswith(".json") or name.endswith(".json.gz")):
            try:
                os.remove(path)
                deleted += 1
            except OSError:
                pass

    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/config", methods=["POST"])
def api_update_config():
    """更新用户配置（调试面板：think/stream/model/base-url/key）"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    user_dir = _session["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        provider = config.setdefault("provider", {})

        if "model" in data:
            provider["model"] = data["model"]
        if "think" in data:
            provider["think"] = bool(data["think"])
        if "stream" in data:
            provider["stream"] = bool(data["stream"])
        if "base_url" in data:
            provider["base_url"] = data["base_url"]
        if "api_key" in data:
            provider["api_key"] = data["api_key"]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 同步更新内存中的 provider
        provider_obj = _session.get("provider")
        if provider_obj:
            if "model" in data:
                provider_obj.model = data["model"]
            if "think" in data:
                provider_obj.think = bool(data["think"])
            if "stream" in data:
                provider_obj.stream = bool(data["stream"])
            if "base_url" in data:
                provider_obj.base_url = data["base_url"]
            if "api_key" in data:
                provider_obj.api_key = data["api_key"]

        return jsonify({"ok": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"保存配置失败: {e}"}), 500


@app.route("/api/config")
def api_get_config():
    """获取当前用户配置"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"读取配置失败: {e}"}), 500


@app.route("/api/tool-logs")
def api_tool_logs():
    """返回工具调用日志（JSON Lines）"""
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = _session["user_dir"]
    log_path = os.path.join(user_dir, "history", "log", "tool_log.json")

    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

    return jsonify(logs)


def run_server(port=13579, host="0.0.0.0"):
    print(f"\n  kesepain-Agent Web UI  →  http://localhost:{port}\n")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
