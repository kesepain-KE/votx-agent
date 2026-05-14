"""任务计划路由 — 列表/查看/暂停/继续/中止/编辑"""
import json
import os
import re
import traceback

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import get_session, get_active_user


_VALID_PLAN_FILE = re.compile(r'^plan_\w+\.json$')


def _validate_plan_id(user_dir: str, plan_id: str) -> tuple[str | None, str | None]:
    """校验 plan_id，返回 (resolved_path, error_msg)"""
    if "/" in plan_id or "\\" in plan_id or ".." in plan_id:
        return (None, f"非法计划 ID: {plan_id}")

    if not _VALID_PLAN_FILE.match(plan_id):
        return (None, f"非法计划文件名: {plan_id}")

    plans_dir = os.path.join(user_dir, "task-plan")
    plan_path = os.path.join(plans_dir, plan_id)
    real_dir = os.path.realpath(plans_dir)
    real_path = os.path.realpath(plan_path)
    if not real_path.startswith(real_dir + os.sep) and real_path != real_dir:
        return (None, "路径越权")

    if not os.path.exists(plan_path):
        return (None, f"计划文件不存在: {plan_id}")

    return (plan_path, None)


def _load_plan(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_plan(path: str, plan: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


# ---- API 端点 ----


@app.route("/api/task-plan")
def api_task_plan_list():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    plans_dir = os.path.join(user_dir, "task-plan")

    plans = []
    if os.path.isdir(plans_dir):
        for name in sorted(os.listdir(plans_dir)):
            if name.endswith(".json"):
                path = os.path.join(plans_dir, name)
                plan = _load_plan(path)
                if plan:
                    plan["id"] = plan.get("id", name.replace(".json", ""))
                    plans.append(plan)

    plans.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return jsonify(plans)


@app.route("/api/task-plan/<plan_id>")
def api_task_plan_get(plan_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    path, err = _validate_plan_id(user_dir, plan_id)
    if err:
        return jsonify({"error": err}), 400

    plan = _load_plan(path)
    if plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    plan["id"] = plan.get("id", plan_id.replace(".json", ""))
    return jsonify(plan)


@app.route("/api/task-plan/<plan_id>/pause", methods=["POST"])
def api_task_plan_pause(plan_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    path, err = _validate_plan_id(user_dir, plan_id)
    if err:
        return jsonify({"error": err}), 400

    plan = _load_plan(path)
    if plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    plan["status"] = "paused"
    _save_plan(path, plan)
    from run.prompt_cache import invalidate_prompt_cache
    invalidate_prompt_cache(user_dir)
    return jsonify({"ok": True})


@app.route("/api/task-plan/<plan_id>/resume", methods=["POST"])
def api_task_plan_resume(plan_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    path, err = _validate_plan_id(user_dir, plan_id)
    if err:
        return jsonify({"error": err}), 400

    plan = _load_plan(path)
    if plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    plan["status"] = "in_progress"
    _save_plan(path, plan)
    # 强制刷新 system prompt 缓存，确保 agent 立即看到新状态
    from run.prompt_cache import invalidate_prompt_cache
    invalidate_prompt_cache(user_dir)
    return jsonify({"ok": True})


@app.route("/api/task-plan/<plan_id>/abort", methods=["POST"])
def api_task_plan_abort(plan_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    path, err = _validate_plan_id(user_dir, plan_id)
    if err:
        return jsonify({"error": err}), 400

    plan = _load_plan(path)
    if plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    plan["status"] = "aborted"
    for step in plan.get("steps", []):
        if step["status"] in ("pending", "in_progress"):
            step["status"] = "skipped"
    _save_plan(path, plan)
    from run.prompt_cache import invalidate_prompt_cache
    invalidate_prompt_cache(user_dir)
    return jsonify({"ok": True})


@app.route("/api/task-plan/<plan_id>/edit-step", methods=["POST"])
def api_task_plan_edit_step(plan_id):
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    step_id = data.get("step_id", "").strip()
    if not step_id:
        return jsonify({"error": "缺少 step_id 参数"}), 400

    user_dir = session_data["user_dir"]
    path, err = _validate_plan_id(user_dir, plan_id)
    if err:
        return jsonify({"error": err}), 400

    plan = _load_plan(path)
    if plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    found = False
    for step in plan.get("steps", []):
        if step["id"] == step_id:
            if "description" in data:
                step["description"] = data["description"]
            if "params" in data:
                for tc in step.get("tool_calls", []):
                    tc["params"] = data["params"]
            found = True
            break

    if not found:
        return jsonify({"error": f"步骤不存在: {step_id}"}), 404

    _save_plan(path, plan)
    from run.prompt_cache import invalidate_prompt_cache
    invalidate_prompt_cache(user_dir)
    return jsonify({"ok": True})


@app.route("/api/task-plan/clear-completed", methods=["DELETE", "POST"])
def api_task_plan_clear_completed():
    """删除所有已完成/已中止的计划（不影响活跃计划）"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    plans_dir = os.path.join(user_dir, "task-plan")
    if not os.path.isdir(plans_dir):
        return jsonify({"ok": True, "deleted": 0})

    deleted = 0
    for name in sorted(os.listdir(plans_dir)):
        if name.endswith(".json"):
            path = os.path.join(plans_dir, name)
            plan = _load_plan(path)
            if plan and plan.get("status") in ("completed", "aborted"):
                try:
                    os.remove(path)
                    deleted += 1
                except Exception:
                    pass

    return jsonify({"ok": True, "deleted": deleted})
