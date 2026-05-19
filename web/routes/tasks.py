"""定时任务 API — GET/POST/DELETE 管理 cron tasks"""
import json
import os

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import _root, require_session


def _require_user_dir():
    """获取当前用户目录，未登录则返回 (error, status_code) 元组"""
    session_data, err, code = require_session()
    if err:
        return err, code
    return session_data.get("user_dir", ""), None


@app.route("/api/tasks", methods=["GET"])
def api_tasks_list():
    """处理 api_tasks_list 相关逻辑。"""
    user_dir, err = _require_user_dir()
    if err:
        return user_dir, err
    from cron.tasks import load_tasks
    tasks = load_tasks(user_dir)
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def api_tasks_create():
    """处理 api_tasks_create 相关逻辑。"""
    user_dir, err = _require_user_dir()
    if err:
        return user_dir, err

    data = request.get_json(silent=True) or {}
    task_type = data.get("type", "daily")
    time = data.get("time", "09:00")
    command = data.get("command", "")

    if not command.strip():
        return jsonify({"error": "任务命令不能为空"}), 400
    if task_type not in ("daily", "once", "recurring"):
        return jsonify({"error": f"无效的任务类型: {task_type}"}), 400

    from cron.tasks import create_task
    task = create_task(user_dir, {
        "type": task_type,
        "time": time,
        "command": command.strip(),
    })
    return jsonify(task)


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_tasks_delete(task_id):
    """处理 api_tasks_delete 相关逻辑。"""
    user_dir, err = _require_user_dir()
    if err:
        return user_dir, err

    from cron.tasks import delete_task
    ok = delete_task(user_dir, task_id)
    if not ok:
        return jsonify({"error": f"任务不存在: {task_id}"}), 404
    return jsonify({"ok": True})
