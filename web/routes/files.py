"""文件操作路由 — 上传/列出/下载/预览/删除"""
import os
import json

from flask import Response, jsonify, request, send_file, session as flask_session

from web.server import app
from web.session import get_session, get_active_user


# ---- Helpers ----

def _resolve_file_dir(session_data, subdir="file"):
    user_dir = session_data.get("user_dir", "")
    if subdir == "download":
        d = os.path.join(user_dir, "download")
    elif subdir == "knowledge":
        d = os.path.join(user_dir, "knowledge")
    elif subdir == "global-knowledge":
        root = session_data.get("root", "")
        d = os.path.join(root, "knowledge")
    else:
        d = os.path.join(user_dir, "history", "file")
    os.makedirs(d, exist_ok=True)
    return d


def _file_rel_path(session_data, name, subdir="file"):
    user = session_data.get("user_name", "")
    if subdir == "download":
        return os.path.join("users", user, "download", name).replace("\\", "/")
    if subdir == "knowledge":
        return os.path.join("users", user, "knowledge", name).replace("\\", "/")
    if subdir == "global-knowledge":
        return os.path.join("knowledge", name).replace("\\", "/")
    return os.path.join("users", user, "history", "file", name).replace("\\", "/")


def _check_file_path(file_dir, filename):
    """校验文件路径安全性，防止路径遍历攻击。

    os.path.basename 剥离目录部分 → realpath 解析符号链接 → 检查是否在允许目录内。
    返回 (target_path, error_response, status_code) 三元组。
    """
    target = os.path.join(file_dir, os.path.basename(filename))
    real_dir = os.path.realpath(file_dir)
    real_target = os.path.realpath(target)
    # 越权检查: 确保解析后的真实路径仍在允许的目录内
    if not real_target.startswith(real_dir + os.sep) and real_target != real_dir:
        return None, jsonify({"error": "路径越权"}), 403
    if not os.path.isfile(target):
        return None, jsonify({"error": "文件不存在"}), 404
    return target, None, None


# ---- Routes ----

@app.route("/api/upload", methods=["POST"])
def api_upload():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400
    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
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
            # 重名处理: 文件名已存在时追加 _1, _2 区分
            while os.path.exists(dest):
                dest = os.path.join(file_dir, f"{base}_{n}{ext}")
                n += 1
            f.save(dest)
            uploaded.append({
                "name": os.path.basename(dest),
                "path": _file_rel_path(session_data, os.path.basename(dest), subdir),
                "size": os.path.getsize(dest),
                "mtime": os.path.getmtime(dest),
                "dir": subdir,
            })

    return jsonify({"ok": True, "files": uploaded})


@app.route("/api/files")
def api_files():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    files = []
    if os.path.isdir(file_dir):
        for name in sorted(os.listdir(file_dir)):
            p = os.path.join(file_dir, name)
            if os.path.isfile(p):
                files.append({
                    "name": name,
                    "path": _file_rel_path(session_data, name, subdir),
                    "size": os.path.getsize(p),
                    "mtime": os.path.getmtime(p),
                    "dir": subdir,
                })
    return jsonify(files)


@app.route("/api/files/download/<filename>")
def api_file_download(filename):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    target, err, code = _check_file_path(file_dir, filename)
    if err:
        return err, code
    return send_file(target, as_attachment=True, download_name=os.path.basename(filename))


@app.route("/api/files/view/<filename>")
def api_file_view(filename):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    target, err, code = _check_file_path(file_dir, filename)
    if err:
        return err, code
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
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    target, err, code = _check_file_path(file_dir, filename)
    if err:
        return err, code
    try:
        os.remove(target)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"error": f"删除失败: {e}"}), 500


@app.route("/api/files", methods=["DELETE"])
def api_delete_files_batch():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    real_file_dir = os.path.realpath(file_dir)

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
