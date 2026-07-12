# -*- coding: utf-8 -*-
"""Task Plan Skill — 复杂任务自动分解为可执行步骤计划"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider.factory import create_provider
from run.tool import register_tool
from plugins._common import err, truncate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 共享上下文：因 register_all() 用 importlib 重载本模块，可能产生多个模块实例。
# 通过 skills._task_plan_ctx ContextVar 确保每个并发会话有独立的上下文副本。
import skills


def _get_ctx() -> dict:
    """获取当前会话的 task_plan 上下文，未设置时返回空 dict"""
    ctx = skills._task_plan_ctx.get()
    return ctx if ctx is not None else {}


def set_task_plan_context(provider=None, chat=None, user_name: str = ""):
    """由 session init 注入 provider/chat/user_name。tools_schemas 和 skills_info 由 task_plan_create 按需获取。"""
    skills._task_plan_ctx.set({
        "provider": provider,
        "chat": chat,
        "user_name": user_name,
    })


# ---- 内部辅助 ----

def _plans_dir(user_name: str) -> Path:
    """执行 plans_dir 内部辅助逻辑。"""
    return _PROJECT_ROOT / "users" / user_name / "task-plan"


def _load_plan(user_name: str, plan_id: str) -> dict | None:
    """执行 load_plan 内部辅助逻辑。"""
    fp = _plans_dir(user_name) / plan_id
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_save_plan(user_name: str, plan_id: str, plan: dict):
    """原子写入 plan 文件 — 先写临时文件再 rename，防止写一半被读到。

    同时保留 aborted 防覆写逻辑。
    """
    d = _plans_dir(user_name)
    d.mkdir(parents=True, exist_ok=True)
    plan_path = d / plan_id
    # 路径穿越校验
    real_dir = os.path.realpath(str(d))
    real_path = os.path.realpath(str(plan_path))
    if not real_path.startswith(real_dir + os.sep) and real_path != real_dir:
        print(f"[task_plan] 路径越权被阻止: {plan_id}", flush=True)
        return
    # 防竞态：如果磁盘上已是 aborted，不覆写
    if plan_path.exists():
        try:
            current = json.loads(plan_path.read_text(encoding="utf-8"))
            if current.get("status") == "aborted":
                return
        except Exception:
            pass
    # 先写临时文件，再原子重命名
    tmp_path = d / f".{plan_id}.tmp"
    tmp_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(plan_path)  # POSIX 原子 rename


# 兼容旧的调用名
_save_plan = _atomic_save_plan


def validate_plan_filepath(plans_dir: str, plan_id: str) -> tuple[str | None, str | None]:
    """统一校验 plan_id 并解析为绝对路径，返回 (resolved_path, error)。

    tool 层和 web 层共用此函数，确保校验逻辑一致。
    接受 plan_abc 或 plan_abc.json 两种格式。
    不检查文件是否存在 — 由调用方按需判断。
    """
    import re as _re
    _PLAN_PATTERN = _re.compile(r'^plan_\w+\.json$')

    clean_id = plan_id
    if clean_id.endswith('.json'):
        clean_id = clean_id[:-5]
    clean_id = clean_id + '.json'

    if not _PLAN_PATTERN.match(clean_id):
        return None, f"非法计划 ID: {plan_id}"

    plans_dir = str(Path(plans_dir).resolve())
    plan_path = os.path.realpath(os.path.join(plans_dir, clean_id))

    if not plan_path.startswith(plans_dir + os.sep) and plan_path != plans_dir:
        return None, "路径越权"
    return plan_path, None


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


def _check_accept_task(user_name: str) -> tuple[str | None, bool]:
    """检查用户是否启用任务计划。返回 (error_msg, accept_task)。

    accept_task 为 True 表示用户启用了自动批准模式。
    """
    config_path = _PROJECT_ROOT / "users" / user_name / "config.json"
    if not config_path.exists():
        return "用户配置不存在", False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        tp = config.get("task_plan", {})
        accept = tp.get("accept_task", False)
        return None, accept
    except Exception as e:
        return f"读取用户配置失败: {e}", False


def _load_user_provider(user_name: str):
    """从用户配置文件重新构造 provider。"""
    config_path = _PROJECT_ROOT / "users" / user_name / "config.json"
    core_config_path = _PROJECT_ROOT / "config" / "config_core.json"
    user_config = json.loads(config_path.read_text(encoding="utf-8"))
    core_config = json.loads(core_config_path.read_text(encoding="utf-8"))
    return create_provider(user_config, core_config)


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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文，请重新进入会话")

    err_msg, accept_task = _check_accept_task(user_name)
    if err_msg:
        return err(err_msg)

    chat = _get_ctx().get("chat")
    if not chat:
        return err("缺少 chat 上下文，请重新进入会话")

    try:
        provider = _load_user_provider(user_name)
    except Exception as e:
        return err(f"加载用户配置中的 provider 失败: {e}")

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

    # 检测流式上下文（Web UI SSE）vs 同步上下文（CLI/定时任务）
    from run.tool import current_tool_call_id as _tc_id_ctx, get_tool_event_queue as _get_q
    tc_id = _tc_id_ctx.get()
    event_q = _get_q(tc_id) if tc_id else None

    if event_q:
        # ── 流式路径：逐 chunk 推送到事件队列 ──
        from agents.task_plan.agent import generate_plan_stream
        plan = None
        stream_error = None
        try:
            for event in generate_plan_stream(
                provider, messages, tools_schemas, skills_info,
                system_prompt, system_info, max_steps,
            ):
                if event.get("type") == "plan_chunk":
                    event_q.put({
                        "type": "tool_chunk",
                        "name": "task_plan_create",
                        "content": event["content"],
                    })
                elif event.get("type") == "plan_done":
                    plan = event.get("plan")
                    stream_error = event.get("error")
        except Exception as e:
            return err(f"计划生成失败: {e}")

        if stream_error:
            return err(stream_error)
        if plan is None:
            return "无需计划 — 当前请求足够简单，直接处理即可"
    else:
        # ── 同步路径（CLI / cron）──
        from agents.task_plan.agent import generate_plan
        try:
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
    plans_dir = str(_plans_dir(user_name))
    _, path_err = validate_plan_filepath(plans_dir, plan_id)
    if path_err:
        return err(path_err)

    plan_file = f"{plan_id}.json"

    if accept_task:
        plan["status"] = "in_progress"
        if plan.get("steps"):
            plan["steps"][0]["status"] = "in_progress"
    _save_plan(user_name, plan_file, plan)

    # ── 强制刷新 system prompt，使计划信息立即注入 LLM 上下文 ──
    chat = _get_ctx().get("chat")
    if chat:
        from run.prompt_cache import build_cached_system_prompt
        root = str(_PROJECT_ROOT)
        user_dir = str(_PROJECT_ROOT / "users" / user_name)
        new_prompt = build_cached_system_prompt(root, user_dir, force=True)
        chat.set_system_prompt(new_prompt)

    steps_count = len(plan.get("steps", []))
    if accept_task:
        return (
            f"OK: 已自动批准计划 [{plan.get('title', '?')}] ({plan_id})\n"
            f"共 {steps_count} 个步骤，开始自动执行……\n" +
            "\n".join(
                f"  {i+1}. [{s.get('status', '?')}] {s.get('description', '?')}"
                for i, s in enumerate(plan.get("steps", []))
            )
        )
    return (
        f"OK: 已创建计划 [{plan.get('title', '?')}] ({plan_id})\n"
        f"共 {steps_count} 个步骤:\n" +
        "\n".join(
            f"  {i+1}. [{s.get('status', '?')}] {s.get('description', '?')}"
            for i, s in enumerate(plan.get("steps", []))
        )
    )


def task_plan_list() -> str:
    """列出当前用户的所有计划"""
    user_name = _get_ctx().get("user_name", "")
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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not plan_id:
        plan_id = _get_active_plan_id(user_name)
        if not plan_id:
            return "（无活跃计划）"

    plans_dir = str(_plans_dir(user_name))
    _, err_str = validate_plan_filepath(plans_dir, plan_id)
    if err_str:
        return err(err_str)

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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    plans_dir = str(_plans_dir(user_name))
    _, err_str = validate_plan_filepath(plans_dir, plan_id)
    if err_str:
        return err(err_str)

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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    plans_dir = str(_plans_dir(user_name))
    _, err_str = validate_plan_filepath(plans_dir, plan_id)
    if err_str:
        return err(err_str)

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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    if not plan_id:
        plan_id = _get_active_plan_id(user_name)
        if not plan_id:
            return "（无活跃计划）"

    plans_dir = str(_plans_dir(user_name))
    _, err_str = validate_plan_filepath(plans_dir, plan_id)
    if err_str:
        return err(err_str)

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
    user_name = _get_ctx().get("user_name", "")
    if not user_name:
        return err("缺少用户上下文")

    plans_dir = str(_plans_dir(user_name))
    _, err_str = validate_plan_filepath(plans_dir, plan_id)
    if err_str:
        return err(err_str)

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
    """处理 register 相关逻辑。"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
