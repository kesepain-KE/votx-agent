"""定时任务 API — GET/POST/DELETE 管理 corn tasks"""
import json
import os

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import _root, get_session, get_active_user


def _get_user_dir():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return None
    return session_data.get("user_dir", "")


@app.route("/api/tasks", methods=["GET"])
def api_tasks_list():
    user_dir = _get_user_dir()
    if not user_dir:
        return jsonify({"error": "未选择用户"}), 400

    from corn.tasks import load_tasks
    tasks = load_tasks(user_dir)
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def api_tasks_create():
    user_dir = _get_user_dir()
    if not user_dir:
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json(silent=True) or {}
    task_type = data.get("type", "daily")
    time = data.get("time", "09:00")
    command = data.get("command", "")

    if not command.strip():
        return jsonify({"error": "任务命令不能为空"}), 400
    if task_type not in ("daily", "once"):
        return jsonify({"error": f"无效的任务类型: {task_type}"}), 400

    from corn.tasks import create_task
    task = create_task(user_dir, {
        "type": task_type,
        "time": time,
        "command": command.strip(),
    })
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_tasks_delete(task_id):
    user_dir = _get_user_dir()
    if not user_dir:
        return jsonify({"error": "未选择用户"}), 400

    from corn.tasks import delete_task
    ok = delete_task(user_dir, task_id)
    if not ok:
        return jsonify({"error": f"任务不存在: {task_id}"}), 404
    return jsonify({"ok": True})
