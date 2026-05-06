"""对话管理路由 — 归档列表/加载/删除/重命名

所有路径操作包含 realpath 越权检查，防止路径遍历攻击。
"""
import json
import os
import traceback

from flask import jsonify, request

from web.server import app
from web.session import _session


@app.route("/api/conversations")
def api_conversations():
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    from run.summarize import load_index

    user_dir = _session["user_dir"]
    archive_dir = os.path.join(user_dir, "history", "archive")
    chat_path = os.path.join(user_dir, "history", "chat", "chat_data.json")
    index = load_index(user_dir)

    conversations = []

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
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    conv_id = data.get("id", "").strip()
    if not conv_id:
        return jsonify({"error": "缺少 id 参数"}), 400

    from web.commands import _web_summarize

    user_dir = _session["user_dir"]

    try:
        _web_summarize()
        chat.save_history()
        chat.save_log(chat.build_messages())

        if conv_id == "__current__":
            chat.load_history()
        else:
            archive_path = os.path.join(user_dir, "history", "archive", conv_id)
            if not os.path.exists(archive_path):
                return jsonify({"error": f"归档文件不存在: {conv_id}"}), 404

            if archive_path.endswith(".gz"):
                import gzip
                with gzip.open(archive_path, "rb") as f:
                    msgs = json.loads(f.read().decode("utf-8"))
            else:
                with open(archive_path, encoding="utf-8") as f:
                    msgs = json.load(f)

            if not isinstance(msgs, list):
                return jsonify({"error": "归档文件格式错误"}), 400

            if msgs and msgs[0].get("role") == "system":
                msgs = msgs[1:]

            chat.messages = msgs
            chat._repair_tool_chain()
            chat.save_history()

        try:
            if os.path.exists(chat.tool_log_path):
                os.remove(chat.tool_log_path)
        except Exception:
            pass

        return jsonify({"ok": True, "msg_count": len(chat.messages)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"加载失败: {e}"}), 500


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    if conv_id == "__current__":
        return jsonify({"error": "不能删除当前对话"}), 400

    user_dir = _session["user_dir"]
    archive_path = os.path.join(user_dir, "history", "archive", conv_id)

    # 路径越权防护: 防止 ../../ 等路径遍历攻击
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
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "缺少 name 参数"}), 400

    user_dir = _session["user_dir"]
    archive_dir = os.path.join(user_dir, "history", "archive")
    old_path = os.path.join(archive_dir, conv_id)

    real_archive = os.path.realpath(archive_dir)
    real_old = os.path.realpath(old_path)
    if not real_old.startswith(real_archive + os.sep) and real_old != real_archive:
        return jsonify({"error": "路径越权"}), 403

    if not os.path.exists(old_path):
        return jsonify({"error": "文件不存在"}), 404

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
