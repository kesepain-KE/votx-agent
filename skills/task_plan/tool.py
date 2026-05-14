# -*- coding: utf-8 -*-
"""Task Plan Skill — 复杂任务自动分解为可执行步骤计划"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from run.tool import register_tool
from skills._common import err, truncate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_VALID_PLAN_FILE = re.compile(r'^plan_\w+\.json$')

# 共享上下文：因 register_all() 用 importlib 重载本模块，可能产生多个模块实例。
# 通过 skills._task_plan_ctx 共享 dict 确保上下文在所有实例间可见。
import skills
_ctx = skills._task_plan_ctx


def set_task_plan_context(provider=None, chat=None, user_name: str = ""):
    """由 session init 注入 provider/chat/user_name。tools_schemas 和 skills_info 由 task_plan_create 按需获取。"""
    _ctx["provider"] = provider
    _ctx["chat"] = chat
    _ctx["user_name"] = user_name


# ---- 内部辅助 ----

def _plans_dir(user_name: str) -> Path:
    return _PROJECT_ROOT / "users" / user_name / "task-plan"


def _load_plan(user_name: str, plan_id: str) -> dict | None:
    fp = _plans_dir(user_name) / plan_id
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_plan(user_name: str, plan_id: str, plan: dict):
    d = _plans_dir(user_name)
    d.mkdir(parents=True, exist_ok=True)
    plan_path = d / plan_id
    # 防竞态：如果用户已中止此计划，不再覆写（避免 SSE 流中的旧操作覆盖中止状态）
    if plan_path.exists():
        try:
            current = json.loads(plan_path.read_text(encoding="utf-8"))
            if current.get("status") == "aborted":
                return
        except Exception:
            pass
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_active_plan(user_name: str) -> tuple[dict | None, str | None]:
    """找到当前活跃计划（in_progress 或 paused），返回 (plan, plan_id)"""
    d = _plans_dir(user_name)
    if not d.is_dir():
        return None, None
    for fp in sorted(d.glob("plan_*.json")):
        plan = _load_plan(user_name, fp.name)
        if plan and plan.get("status") in ("in_progress", "paused", "pending"):
            return plan, fp.name
    return None, None


def _check_accept_task(user_name: str) -> str | None:
    """检查用户是否启用任务计划。返回错误信息或 None（通过）"""
    config_path = _PROJECT_ROOT / "users" / user_name / "config.json"
    if not config_path.exists():
        return "用户配置不存在"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        tp = config.get("task_plan", {})
        if not tp.get("accept_task", False):
            return "用户未启用任务计划功能（task_plan.accept_task=false）"
    except Exception as e:
        return f"读取用户配置失败: {e}"
    return None


def _get_active_plan_id(user_name: str) -> str | None:
    """获取活跃计划的 plan_id（不含 .json 扩展名）"""
    _, plan_file = _find_active_plan(user_name)
    if plan_file:
        return plan_file.replace(".json", "")
    return None


# ---- 工具函数 ----

def task_plan_create(description: str) -> str:
    """调用子代理生成执行计划并保存。

    Args:
        description: 用户请求的简要描述（用于计划标题和上下文）
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文，请重新进入会话")

    err_msg = _check_accept_task(user_name)
    if err_msg:
        return err(err_msg)

    provider = _ctx.get("provider")
    chat = _ctx.get("chat")
    if not provider or not chat:
        return err("缺少 provider/chat 上下文，请重新进入会话")

    # 检查是否已有活跃计划
    active, active_file = _find_active_plan(user_name)
    if active and active.get("status") == "in_progress":
        return err(
            f"已有活跃计划 [{active.get('title', '?')}] ({active_file})，"
            f"请先完成或中止后再创建新计划"
        )

    messages = getattr(chat, "messages", [])
    system_prompt = getattr(chat, "system_prompt", "")

    # 按需获取已注册的工具和技能信息
    from run.tool import load_tool_schemas
    from skills import get_cached_skills_info
    tools_schemas = load_tool_schemas()
    skills_info = get_cached_skills_info()

    system_info = {
        "user_name": user_name,
        "current_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_root": str(_PROJECT_ROOT),
    }

    # 读取 max_steps 配置
    try:
        core_config_path = _PROJECT_ROOT / "config" / "config_core.json"
        core_config = json.loads(core_config_path.read_text(encoding="utf-8"))
        max_steps = core_config.get("task_plan", {}).get("max_steps", 10)
    except Exception:
        max_steps = 10

    try:
        from agents.task_plan.agent import generate_plan
        result = generate_plan(
            provider, messages, tools_schemas, skills_info,
            system_prompt, system_info, max_steps,
        )
    except Exception as e:
        return err(f"计划生成失败: {e}")

    if result.get("error"):
        return err(result["error"])

    plan = result.get("plan")
    if plan is None:
        return "无需计划 — 当前请求足够简单，直接处理即可"

    # 保存计划
    plan_id = plan.get("id", "plan_unknown")
    plan_file = f"{plan_id}.json"
    _save_plan(user_name, plan_file, plan)

    steps_count = len(plan.get("steps", []))
    return (
        f"OK: 已创建计划 [{plan.get('title', '?')}] ({plan_id})\n"
        f"共 {steps_count} 个步骤:\n" +
        "\n".join(
            f"  {i+1}. [{s.get('status', '?')}] {s.get('description', '?')}"
            for i, s in enumerate(plan.get("steps", []))
        ) +
        "\n\n⚠ 请告知用户点击「批准」按钮后才会开始执行步骤。不要立即调用 task_plan_step_done。"
    )


def task_plan_list() -> str:
    """列出当前用户的所有计划"""
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    d = _plans_dir(user_name)
    if not d.is_dir():
        return "（无计划）"

    plans = []
    for fp in sorted(d.glob("plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        plan = _load_plan(user_name, fp.name)
        if plan:
            plans.append((fp.name, plan))

    if not plans:
        return "（无计划）"

    lines = [f"共 {len(plans)} 个计划:"]
    for fname, p in plans:
        status = p.get("status", "?")
        status_icon = {"pending": "⬜", "in_progress": "🔄", "completed": "✅",
                       "paused": "⏸️", "aborted": "❌"}.get(status, "❓")
        steps_done = sum(1 for s in p.get("steps", []) if s.get("status") == "completed")
        steps_total = len(p.get("steps", []))
        lines.append(
            f"  {status_icon} [{p.get('id', fname)}] {p.get('title', '?')} "
            f"({steps_done}/{steps_total} 步) - {status}"
        )
    return "\n".join(lines)


def task_plan_view(plan_id: str | None = None) -> str:
    """查看计划详情。不传 plan_id 时查看当前活跃计划。

    Args:
        plan_id: 计划 ID（如 plan_a1b2c3d4），可选
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not plan_id:
        plan_id = _get_active_plan_id(user_name)
        if not plan_id:
            return "（无活跃计划）"

    # 安全校验
    if not _VALID_PLAN_FILE.match(f"{plan_id}.json"):
        return err(f"非法计划 ID: {plan_id}")

    plan = _load_plan(user_name, f"{plan_id}.json")
    if plan is None:
        return err(f"计划不存在: {plan_id}")

    steps = plan.get("steps", [])
    lines = [
        f"计划: {plan.get('title', '?')}",
        f"ID: {plan.get('id', plan_id)}",
        f"状态: {plan.get('status', '?')}",
        f"描述: {plan.get('description', '无')}",
        f"创建: {plan.get('created_at', '?')}",
        "",
        f"步骤 ({len(steps)}):",
    ]
    for i, s in enumerate(steps):
        icon = {"pending": "⬜", "in_progress": "🔄", "completed": "✅",
                "failed": "❌", "skipped": "⏭️"}.get(s.get("status", ""), "❓")
        desc = s.get("description", "?")
        result = s.get("result", "")
        result_str = f" → {truncate(result, 200)}" if result else ""
        lines.append(f"  {icon} {s.get('id', i+1)}: {desc}{result_str}")
        if s.get("error"):
            lines.append(f"      错误: {truncate(s['error'], 200)}")

    return "\n".join(lines)


def task_plan_step_done(plan_id: str, step_id: str, result: str = "") -> str:
    """标记步骤完成并记录结果。

    Args:
        plan_id: 计划 ID
        step_id: 步骤 ID
        result: 步骤执行结果摘要（可选）
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not _VALID_PLAN_FILE.match(f"{plan_id}.json"):
        return err(f"非法计划 ID: {plan_id}")

    plan = _load_plan(user_name, f"{plan_id}.json")
    if plan is None:
        return err(f"计划不存在: {plan_id}")

    found = False
    for step in plan.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "completed"
            if result:
                step["result"] = result
            step.setdefault("updated_at", datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"))
            found = True
            break

    if not found:
        return err(f"步骤不存在: {step_id}")

    # 更新 current_step；如果计划被暂停则恢复为执行中
    if plan.get("status") == "paused":
        plan["status"] = "in_progress"
    steps = plan["steps"]
    for i, s in enumerate(steps):
        if s["status"] != "completed":
            plan["current_step"] = i
            break
    else:
        plan["status"] = "completed"
        plan["current_step"] = len(steps)

    plan["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_plan(user_name, f"{plan_id}.json", plan)

    return f"OK: 步骤 [{step_id}] 已完成"


def task_plan_step_fail(plan_id: str, step_id: str, error: str) -> str:
    """标记步骤失败并记录错误。

    Args:
        plan_id: 计划 ID
        step_id: 步骤 ID
        error: 错误信息
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not _VALID_PLAN_FILE.match(f"{plan_id}.json"):
        return err(f"非法计划 ID: {plan_id}")

    plan = _load_plan(user_name, f"{plan_id}.json")
    if plan is None:
        return err(f"计划不存在: {plan_id}")

    found = False
    for step in plan.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = "failed"
            step["error"] = error
            found = True
            break

    if not found:
        return err(f"步骤不存在: {step_id}")

    plan["status"] = "paused"
    plan["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_plan(user_name, f"{plan_id}.json", plan)

    return f"OK: 步骤 [{step_id}] 失败，计划已暂停。错误: {truncate(error, 300)}"


def task_plan_abort(plan_id: str | None = None) -> str:
    """中止计划。不传 plan_id 时中止当前活跃计划。

    Args:
        plan_id: 计划 ID，可选
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not plan_id:
        plan_id = _get_active_plan_id(user_name)
        if not plan_id:
            return "（无活跃计划）"

    if not _VALID_PLAN_FILE.match(f"{plan_id}.json"):
        return err(f"非法计划 ID: {plan_id}")

    plan = _load_plan(user_name, f"{plan_id}.json")
    if plan is None:
        return err(f"计划不存在: {plan_id}")

    plan["status"] = "aborted"
    for step in plan.get("steps", []):
        if step["status"] in ("pending", "in_progress"):
            step["status"] = "skipped"
    plan["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_plan(user_name, f"{plan_id}.json", plan)

    return f"OK: 计划 [{plan.get('title', plan_id)}] 已中止"


def task_plan_edit(plan_id: str, step_id: str | None = None,
                   description: str = "", params: str = "") -> str:
    """编辑计划步骤的描述或参数。

    Args:
        plan_id: 计划 ID
        step_id: 步骤 ID（可选，不传则编辑计划标题/描述）
        description: 新的步骤描述或计划描述
        params: 新的工具参数（JSON 字符串）
    """
    user_name = _ctx.get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not _VALID_PLAN_FILE.match(f"{plan_id}.json"):
        return err(f"非法计划 ID: {plan_id}")

    plan = _load_plan(user_name, f"{plan_id}.json")
    if plan is None:
        return err(f"计划不存在: {plan_id}")

    if step_id:
        found = False
        for step in plan.get("steps", []):
            if step.get("id") == step_id:
                if description:
                    step["description"] = description
                if params:
                    try:
                        new_params = json.loads(params)
                    except json.JSONDecodeError:
                        return err(f"params 不是合法 JSON: {params[:100]}")
                    for tc in step.get("tool_calls", []):
                        tc["params"] = new_params
                step.setdefault("updated_at", datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"))
                found = True
                break
        if not found:
            return err(f"步骤不存在: {step_id}")
    else:
        if description:
            plan["description"] = description

    # 编辑后若计划被暂停则恢复为执行中
    if plan.get("status") == "paused":
        plan["status"] = "in_progress"
    plan["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_plan(user_name, f"{plan_id}.json", plan)

    target = f"步骤 [{step_id}]" if step_id else f"计划 [{plan_id}]"
    return f"OK: {target} 已更新"


# ---- Schema ----

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "task_plan_create",
            "description": "分析用户复杂请求并生成分步执行计划。计划创建后状态为pending，必须等用户在Web UI点击「批准」后才能执行步骤。适用于多步骤任务：下载分析、批量处理、跨文件操作等。受用户 task_plan.accept_task 配置控制。",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "用户请求的简要描述，用于生成计划标题和上下文定位",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_list",
            "description": "列出当前用户的所有任务计划及其状态和进度",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_view",
            "description": "查看指定计划的详细信息，含所有步骤、状态和结果。不传 plan_id 时查看当前活跃计划。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "计划 ID（如 plan_a1b2c3d4），可选",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_step_done",
            "description": "标记指定步骤已完成并记录执行结果。AI 执行完计划中的一步后必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "计划 ID",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "步骤 ID",
                    },
                    "result": {
                        "type": "string",
                        "description": "步骤执行结果摘要（可选，建议 200 字以内）",
                    },
                },
                "required": ["plan_id", "step_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_step_fail",
            "description": "标记指定步骤失败并记录错误。失败后计划自动暂停，等待用户介入。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "计划 ID",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "步骤 ID",
                    },
                    "error": {
                        "type": "string",
                        "description": "错误描述",
                    },
                },
                "required": ["plan_id", "step_id", "error"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_abort",
            "description": "中止计划，所有未完成步骤标记为跳过。不传 plan_id 时中止当前活跃计划。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "计划 ID，可选",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_edit",
            "description": "编辑计划步骤的描述或参数。用户要求修改计划时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "计划 ID",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "步骤 ID（编辑特定步骤时必填）",
                    },
                    "description": {
                        "type": "string",
                        "description": "新的描述文本",
                    },
                    "params": {
                        "type": "string",
                        "description": "新的工具参数（JSON 字符串）",
                    },
                },
                "required": ["plan_id"],
            },
        },
    },
]

HANDLERS = {
    "task_plan_create": task_plan_create,
    "task_plan_list": task_plan_list,
    "task_plan_view": task_plan_view,
    "task_plan_step_done": task_plan_step_done,
    "task_plan_step_fail": task_plan_step_fail,
    "task_plan_abort": task_plan_abort,
    "task_plan_edit": task_plan_edit,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
