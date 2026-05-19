"""文件操作路由 — 上传/列出/下载/预览/删除"""
import os
import json

from flask import jsonify, request, send_file, session as flask_session

from web.server import app
from web.session import require_session

# 允许上传的文件扩展名白名单
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".7z",
    ".py", ".js", ".ts", ".html", ".css", ".sh",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
}

# 单文件最大上传大小 (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024


# ---- Helpers ----

def _resolve_file_dir(session_data, subdir="file"):
    """执行 resolve_file_dir 内部辅助逻辑。"""
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
    """执行 file_rel_path 内部辅助逻辑。"""
    user = session_data.get("user_name", "")
    if subdir == "download":
        return os.path.join("users", user, "download", name).replace("\\", "/")
    if subdir == "knowledge":
        return os.path.join("users", user, "knowledge", name).replace("\\", "/")
    if subdir == "global-knowledge":
        return os.path.join("knowledge", name).replace("\\", "/")
    return os.path.join("users", user, "history", "file", name).replace("\\", "/")


def _check_file_path(file_dir, filename, must_exist=True):
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
    if must_exist and not os.path.isfile(target):
        return None, jsonify({"error": "文件不存在"}), 404
    return target, None, None


# ---- Routes ----

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """处理 api_upload 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

    subdir = request.args.get("dir", "file")
    if subdir == "global-knowledge":
        return jsonify({"error": "全局知识库为只读，不允许上传"}), 403
    file_dir = _resolve_file_dir(session_data, subdir)
    os.makedirs(file_dir, exist_ok=True)

    uploaded = []
    for key in request.files:
        f = request.files[key]
        if f.filename:
            safe_name = os.path.basename(f.filename)
            if not safe_name:
                safe_name = "unnamed"

            # 扩展名白名单检查
            ext = os.path.splitext(safe_name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return jsonify({"error": f"不支持的文件类型: {ext}"}), 400

            # 文件大小检查
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            if size > MAX_FILE_SIZE:
                return jsonify({"error": f"文件大小超限 (最大 {MAX_FILE_SIZE // 1024 // 1024}MB)"}), 413

            # 路径安全校验 (上传时文件尚不存在，must_exist=False)
            dest, err, code = _check_file_path(file_dir, safe_name, must_exist=False)
            if err:
                return err, code

            base, _ext = os.path.splitext(safe_name)
            n = 1
            # 重名处理: 文件名已存在时追加 _1, _2 区分
            while os.path.exists(dest):
                dest = os.path.join(file_dir, f"{base}_{n}{_ext}")
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
    """处理 api_files 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
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
    """处理 api_file_download 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    target, err, code = _check_file_path(file_dir, filename)
    if err:
        return err, code
    return send_file(target, as_attachment=True, download_name=os.path.basename(filename))


@app.route("/api/files/view/<filename>")
def api_file_view(filename):
    """处理 api_file_view 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    subdir = request.args.get("dir", "file")
    file_dir = _resolve_file_dir(session_data, subdir)
    target, err, code = _check_file_path(file_dir, filename)
    if err:
        return err, code
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
        ".bmp": "image/bmp", ".ico": "image/x-icon",
    }
    # .svg 已移除 — 仅通过 /download 端点以 attachment 方式下载
    mime = mime_map.get(ext, "application/octet-stream")
    response = send_file(target, mimetype=mime, as_attachment=False, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/api/files/<filename>", methods=["DELETE"])
def api_delete_file(filename):
    """处理 api_delete_file 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    subdir = request.args.get("dir", "file")
    if subdir == "global-knowledge":
        return jsonify({"error": "全局知识库为只读，不允许删除"}), 403
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
    """处理 api_delete_files_batch 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    subdir = request.args.get("dir", "file")
    if subdir == "global-knowledge":
        return jsonify({"error": "全局知识库为只读，不允许删除"}), 403
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
