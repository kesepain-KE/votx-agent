"""对话管理路由 — 列表/预览/选择/继续/删除/重命名

策略 A：选择归档对话只做只读预览，不覆盖当前对话。
只有点"从此对话继续"才把归档恢复为当前对话。
"""
import gzip
import json
import os
import re
import traceback

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import get_session, get_active_user


# ---- 路径安全 ----

_VALID_ARCHIVE_FILE = re.compile(r'^history_\d{8}T\d{6}_\d+\.json(?:\.gz)?$')


def _validate_conv_id(user_dir: str, conv_id: str) -> tuple[str | None, str | None]:
    """校验 conversation_id，返回 (kind, resolved_path) 或 (None, error_msg)。

    只允许:
      - "__current__"  →  当前对话
      - 合法归档文件名   →  archive/<filename>
    拒绝任何包含 /、..、非 .json/.json.gz 结尾的 id。
    """
    if conv_id == "__current__":
        chat_path = os.path.join(user_dir, "history", "chat", "chat_data.json")
        return ("current", chat_path)

    if "/" in conv_id or "\\" in conv_id or ".." in conv_id:
        return (None, f"非法会话 ID: {conv_id}")

    if not (conv_id.endswith(".json") or conv_id.endswith(".json.gz")):
        return (None, f"不支持的文件格式: {conv_id}")

    if not _VALID_ARCHIVE_FILE.match(conv_id):
        return (None, f"非法归档文件名: {conv_id}")

    archive_path = os.path.join(user_dir, "history", "archive", conv_id)
    real_archive = os.path.realpath(os.path.join(user_dir, "history", "archive"))
    real_path = os.path.realpath(archive_path)
    if not real_path.startswith(real_archive + os.sep) and real_path != real_archive:
        return (None, "路径越权")

    if not os.path.exists(archive_path):
        return (None, f"归档文件不存在: {conv_id}")

    return ("archive", archive_path)


def _read_conv_messages(kind: str, path: str) -> list[dict]:
    """读取对话消息列表（不修改 ChatManager）"""
    if kind == "current":
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    else:
        with open(path, "rb") if path.endswith(".gz") else open(path, encoding="utf-8") as f:
            if path.endswith(".gz"):
                data = json.loads(gzip.decompress(f.read()).decode("utf-8"))
            else:
                data = json.load(f)
        msgs = data if isinstance(data, list) else []
        # 去掉首条 system prompt（重启后由 engine 重建）
        if msgs and msgs[0].get("role") == "system":
            msgs = msgs[1:]
        return msgs


# ---- API 端点 ----

@app.route("/api/conversations")
def api_conversations():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    from run.summarize import load_index

    user_dir = session_data["user_dir"]
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
                "title": "当前对话",
                "label": meta.get("summary") or "新对话",
                "summary": meta.get("summary", ""),
                "msg_count": msg_count,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "kind": "current",
            })
        except Exception:
            pass

    # 归档会话
    if os.path.isdir(archive_dir):
        try:
            files = []
            for name in os.listdir(archive_dir):
                if name.endswith(".json.gz") or (name.endswith(".json") and not name.endswith(".json.gz")):
                    path = os.path.join(archive_dir, name)
                    try:
                        stat = os.stat(path)
                        files.append((name, path, stat))
                    except OSError:
                        pass
            files.sort(key=lambda x: x[2].st_mtime, reverse=True)

            for name, path, stat in files:
                meta = index.get(name, {})
                summary = meta.get("summary", "")
                raw_label = name.rsplit(".", 1)[0].replace("history_", "").replace(".json", "")
                conversations.append({
                    "id": name,
                    "title": summary or raw_label,
                    "label": summary or raw_label,
                    "raw_label": raw_label,
                    "summary": summary,
                    "msg_count": meta.get("msg_count", 0),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "kind": "archive",
                })
        except OSError:
            pass

    return jsonify(conversations)


@app.route("/api/conversations/load", methods=["POST"])
def api_conversations_load():
    """预览对话消息（只读，不修改当前对话）"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    conv_id = data.get("id", "").strip()
    if not conv_id:
        return jsonify({"error": "缺少 id 参数"}), 400

    user_dir = session_data["user_dir"]
    kind, path_or_err = _validate_conv_id(user_dir, conv_id)
    if kind is None:
        return jsonify({"error": path_or_err}), 400

    try:
        msgs = _read_conv_messages(kind, path_or_err)
        return jsonify({
            "id": conv_id,
            "kind": kind,
            "messages": msgs,
            "msg_count": len(msgs),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"读取失败: {e}"}), 500


@app.route("/api/conversations/select", methods=["POST"])
def api_conversations_select():
    """切换到指定对话进行预览（只设置 active_conversation_id，不覆盖当前消息）"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    conv_id = data.get("id", "").strip()
    if not conv_id:
        return jsonify({"error": "缺少 id 参数"}), 400

    user_dir = session_data["user_dir"]
    kind, path_or_err = _validate_conv_id(user_dir, conv_id)
    if kind is None:
        return jsonify({"error": path_or_err}), 400

    session_data["_preview_conv_id"] = conv_id
    session_data["_preview_conv_kind"] = kind

    try:
        msgs = _read_conv_messages(kind, path_or_err)
        return jsonify({
            "ok": True,
            "id": conv_id,
            "kind": kind,
            "preview": True,
            "msg_count": len(msgs),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"加载失败: {e}"}), 500


@app.route("/api/conversations/continue", methods=["POST"])
def api_conversations_continue():
    """从归档继续：自动归档当前对话 → 将目标归档加载为当前对话"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400

    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    conv_id = data.get("id", "").strip()
    if not conv_id:
        return jsonify({"error": "缺少 id 参数"}), 400

    user_dir = session_data["user_dir"]
    kind, path_or_err = _validate_conv_id(user_dir, conv_id)
    if kind is None:
        return jsonify({"error": path_or_err}), 400

    if kind == "current":
        return jsonify({"error": "当前对话无需继续操作，直接聊天即可"}), 400

    try:
        from web.commands import _web_summarize

        # 1. 如果当前有消息，先自动归档
        if chat.messages:
            _web_summarize(session_data)
            chat.save_history()
            chat.save_log(chat.build_messages())
            chat.archive_now()

        # 2. 读归档消息
        msgs = _read_conv_messages(kind, path_or_err)

        # 3. 加载为当前对话
        chat.load_messages(msgs)
        chat.save_history()

        # 4. 清除预览状态
        session_data.pop("_preview_conv_id", None)
        session_data.pop("_preview_conv_kind", None)

        # 5. 清除工具日志（旧工具调用结果在新对话中无意义）
        old_log_path = os.path.join(os.path.dirname(chat.tool_log_path), "tool_log.json")
        for log_path in (chat.tool_log_path, old_log_path):
            try:
                if os.path.exists(log_path):
                    os.remove(log_path)
            except Exception:
                pass

        return jsonify({
            "ok": True,
            "id": conv_id,
            "msg_count": len(msgs),
            "kind": "current",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"继续对话失败: {e}"}), 500


@app.route("/api/conversations/preview-state")
def api_conversations_preview_state():
    """查询当前预览状态"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"preview": False})

    preview_id = session_data.get("_preview_conv_id")
    preview_kind = session_data.get("_preview_conv_kind")
    if preview_id:
        return jsonify({
            "preview": True,
            "id": preview_id,
            "kind": preview_kind,
        })
    return jsonify({"preview": False})


# ---- 删除 / 重命名 ----

@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    if conv_id == "__current__":
        return jsonify({"error": "不能删除当前对话"}), 400

    user_dir = session_data["user_dir"]
    archive_path = os.path.join(user_dir, "history", "archive", conv_id)

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


@app.route("/api/conversations/<conv_id>/rename", methods=["POST"])
def api_rename_conversation(conv_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "缺少 name 参数"}), 400

    user_dir = session_data["user_dir"]

    # __current__ 没有实体文件，更新索引中的 summary
    if conv_id == "__current__":
        from run.summarize import load_index, save_index
        try:
            idx = load_index(user_dir)
            idx.setdefault("chat_data.json", {})["summary"] = new_name
            save_index(user_dir, idx)
            return jsonify({"ok": True, "new_name": new_name})
        except Exception as e:
            return jsonify({"error": f"更新失败: {e}"}), 500

    archive_dir = os.path.join(user_dir, "history", "archive")
    old_path = os.path.join(archive_dir, conv_id)

    real_archive = os.path.realpath(archive_dir)
    real_old = os.path.realpath(old_path)
    if not real_old.startswith(real_archive + os.sep) and real_old != real_archive:
        return jsonify({"error": "路径越权"}), 403

    if not os.path.exists(old_path):
        return jsonify({"error": "文件不存在"}), 404

    _, ext = os.path.splitext(conv_id)
    if conv_id.endswith(".json.gz"):
        ext = ".json.gz"
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
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
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
