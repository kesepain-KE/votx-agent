"""任务计划路由 — 列表/查看/暂停/继续/中止/编辑/批准执行"""
import json
import os
import traceback
import uuid
from datetime import datetime, timezone

from flask import Response, jsonify, request, session as flask_session, stream_with_context

from web.server import app
from web.session import (
    require_session,
    start_active_run,
    clear_active_run,
)
from run.user_locks import get_user_lock
from plugins.task_plan.tool import validate_plan_filepath
from paths import get_project_root


def _validate_plan_id(user_dir: str, plan_id: str) -> tuple[str | None, str | None]:
    """校验 plan_id（兼容旧接口，内部委托给统一校验函数）。"""
    plans_dir = os.path.join(user_dir, "task-plan")
    plan_path, err = validate_plan_filepath(plans_dir, plan_id)
    if err:
        return None, err
    if not os.path.exists(plan_path):
        return None, f"计划文件不存在: {plan_id}"
    return plan_path, None


def _load_plan(path: str) -> dict | None:
    """执行 load_plan 内部辅助逻辑。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_plan(path: str, plan: dict):
    """原子写入 plan 文件 — 先写临时文件再 rename，防止读脏数据。

    同时保留 aborted 防覆写逻辑（与 tool 层 _atomic_save_plan 对齐）。
    """
    # 防竞态：如果磁盘上已是 aborted，不覆写
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                current = json.load(f)
            if current.get("status") == "aborted":
                return
        except Exception:
            pass
    # 先写临时文件，再原子重命名
    plan_dir = os.path.dirname(path)
    plan_name = os.path.basename(path)
    tmp_path = os.path.join(plan_dir, f".{plan_name}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


# ---- API 端点 ----


@app.route("/api/task-plan")
def api_task_plan_list():
    """处理 api_task_plan_list 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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
    """处理 api_task_plan_get 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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
    """处理 api_task_plan_pause 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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
    """处理 api_task_plan_resume 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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
    """处理 api_task_plan_abort 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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
    """处理 api_task_plan_edit_step 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

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


@app.route("/api/task-plan/<plan_id>/reject", methods=["POST"])
def api_task_plan_reject(plan_id):
    """拒绝计划 — 标记为 aborted，未完成步骤标记为 skipped"""
    session_data, err, code = require_session()
    if err:
        return err, code

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


@app.route("/api/task-plan/clear-completed", methods=["DELETE", "POST"])
def api_task_plan_clear_completed():
    """删除所有已完成/已中止的计划（不影响活跃计划）"""
    session_data, err, code = require_session()
    if err:
        return err, code

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


@app.route("/api/task-plan/generate-stream", methods=["POST"])
def api_task_plan_generate_stream():
    """流式生成计划 SSE 端点 — 用户点击创建计划后实时看到生成进度。

    Request: {"description": "任务描述"}
    SSE events: plan_chunk (思考片段), plan_done (最终计划), error
    """
    session_data, err, code = require_session()
    if err:
        return err, code

    data = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "缺少 description 参数"}), 400

    user_dir = session_data.get("user_dir", "")
    user_name = session_data.get("user_name", "")
    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "会话无效"}), 400

    # 加载 provider（使用用户配置）
    from provider.factory import create_provider
    try:
        provider = create_provider(
            session_data["user_config"],
            session_data["core_config"],
        )
    except Exception as e:
        return jsonify({"error": f"加载 provider 失败: {e}"}), 500

    # 获取工具和技能信息
    from run.tool import load_tool_schemas
    from skills import get_cached_skills_info
    tools_schemas = load_tool_schemas()
    skills_info = get_cached_skills_info()

    messages = getattr(chat, "messages", [])
    system_prompt = getattr(chat, "system_prompt", "")

    system_info = {
        "user_name": user_name,
        "current_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_root": str(get_project_root()),
    }

    try:
        core_config_path = os.path.join(get_project_root(), "config", "config_core.json")
        with open(core_config_path, encoding="utf-8") as f:
            core_config = json.load(f)
        max_steps = core_config.get("task_plan", {}).get("max_steps", 10)
    except Exception:
        max_steps = 10

    from agents.task_plan.agent import generate_plan_stream

    def generate():
        """处理 generate 相关逻辑。"""
        try:
            for event in generate_plan_stream(
                provider, messages, tools_schemas, skills_info,
                system_prompt, system_info, max_steps,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/task-plan/<plan_id>/approve-run", methods=["POST"])
def api_task_plan_approve_run(plan_id):
    """批准并执行计划 — SSE 流式端点

    幂等容错: pending/paused → in_progress; 已 in_progress → 直接执行; completed/aborted → 拒绝。
    使用磁盘 .running flag 文件防止重复执行（进程重启安全）。
    """
    session_data, err, code = require_session()
    if err:
        return err, code

    user_dir = session_data["user_dir"]
    user_name = session_data.get("user_name", "")
    path, plan_err = _validate_plan_id(user_dir, plan_id)
    if plan_err:
        return jsonify({"error": plan_err}), 400

    initial_plan = _load_plan(path)
    if initial_plan is None:
        return jsonify({"error": "无法读取计划文件"}), 500

    current_status = initial_plan.get("status", "pending")

    if current_status in ("completed", "aborted"):
        return jsonify({"error": f"计划已完成/已中止，无法执行 (status={current_status})"}), 400

    # run_id is optional; the web client always sends it.
    body = request.get_json(silent=True) or {}
    run_id = str(body.get("run_id") or "").strip() or uuid.uuid4().hex

    # 磁盘 running flag 文件路径
    running_flag = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}.running")

    def generate():
        """处理 generate 相关逻辑。"""
        # 原子创建 running flag（O_CREAT | O_EXCL 保证 POSIX 并发安全）
        try:
            fd = os.open(running_flag, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            yield f"data: {json.dumps({'type': 'error', 'content': '计划正在执行中，请勿重复启动'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        try:
            with get_user_lock(user_name):
                cancel_event = start_active_run(session_data, run_id)
                plan = _load_plan(path)
                if plan is None:
                    yield f"data: {json.dumps({'type': 'error', 'content': '无法读取计划文件'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                current_status = plan.get("status", "pending")
                if current_status in ("completed", "aborted"):
                    yield f"data: {json.dumps({'type': 'error', 'content': f'计划已完成/已中止，无法执行 (status={current_status})'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                if current_status in ("pending", "paused"):
                    plan["status"] = "in_progress"
                    for step in plan.get("steps", []):
                        if step.get("status") == "pending":
                            step["status"] = "in_progress"
                            break
                    _save_plan(path, plan)

                from run.prompt_cache import invalidate_prompt_cache
                invalidate_prompt_cache(user_dir)

                # 组装含计划上下文的 extra_user_message
                plan_id_clean = plan.get("id", plan_id.replace(".json", ""))
                plan_title = plan.get("title", "?")

                # 找第一个待执行步骤
                pending_steps = [
                    s for s in plan.get("steps", [])
                    if s.get("status") in ("pending", "in_progress")
                ]
                next_hint = ""
                if pending_steps:
                    next_hint = f"\n下一步待执行: {pending_steps[0].get('description', '?')}"

                extra_msg = (
                    f"用户已批准执行计划 [{plan_title}] ({plan_id_clean})。"
                    f"请按活跃计划中的步骤依次执行。{next_hint}"
                )

                from web.routes.chat import _run_chat_stream

                # 立即推送 plan_started
                yield f"data: {json.dumps({'type': 'plan_started', 'plan_id': plan_id_clean, 'plan': plan}, ensure_ascii=False)}\n\n"
                yield from _run_chat_stream(
                    session_data,
                    extra_user_message=extra_msg,
                    cancel_event=cancel_event,
                )
        finally:
            clear_active_run(session_data, run_id)
            # 删除 running flag
            try:
                os.unlink(running_flag)
            except Exception:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
