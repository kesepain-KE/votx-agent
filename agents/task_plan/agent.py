# -*- coding: utf-8 -*-
"""Task Plan 子代理 — 将复杂用户请求分解为可执行步骤计划

调用方式:
    from agents.task_plan.agent import generate_plan
    result = generate_plan(provider, messages, tools_schemas, skills_info, system_prompt, system_info)
    # result: {"plan": dict | None, "error": str | None}

与 auto_improve 子代理一致：同步调用 provider.respond()，无流式，无工具。
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator


# ──── 内部辅助 ────

def _load_agent_md() -> str:
    """执行 load_agent_md 内部辅助逻辑。"""
    root = Path(__file__).resolve().parent.parent.parent
    agent_md_path = root / "agents" / "task_plan" / "AGENT.md"
    if agent_md_path.exists():
        return agent_md_path.read_text(encoding="utf-8")
    return ""


def _extract_conversation_text(messages: list[dict]) -> str:
    """提取对话核心内容（用户+助手回复，去 tool_calls/思考），每条约 500 字截断"""
    lines = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user" and content:
            text = content[:500]
            lines.append(f"[用户]: {text}")
        elif role == "assistant" and content and not m.get("tool_calls"):
            text = content[:500]
            lines.append(f"[助手]: {text}")
        elif role == "assistant" and m.get("tool_calls"):
            tc_names = [tc.get("function", {}).get("name", "?") for tc in m["tool_calls"]]
            lines.append(f"[助手调用工具]: {', '.join(tc_names)}")
        elif role == "tool":
            result = content[:200] if content else "(空)"
            lines.append(f"[工具结果: {m.get('tool_call_id', '?')}]: {result}")
    return "\n".join(lines)


def _build_tools_text(tools_schemas: list[dict]) -> str:
    """将工具 Schema 列表格式化为可读文本"""
    if not tools_schemas:
        return "（无可用工具）\n"

    parts = []
    for s in sorted(tools_schemas, key=lambda x: x.get("function", {}).get("name", "")):
        fn = s.get("function", {})
        name = fn.get("name", "?")
        desc = fn.get("description", "")
        params = fn.get("parameters", {}).get("properties", {})
        required = fn.get("parameters", {}).get("required", [])

        lines = [f"### {name}" + (f" — {desc}" if desc else "")]
        if params:
            for pname, pinfo in params.items():
                req_mark = " *必填*" if pname in required else ""
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                lines.append(f"  - `{pname}` ({ptype}){req_mark}: {pdesc}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _build_skills_text(skills_info: list[dict]) -> str:
    """将技能摘要列表格式化为可读文本"""
    if not skills_info:
        return "（无可用技能）\n"

    lines = []
    for si in skills_info:
        lines.append(si.get("summary", f"- {si.get('name', '?')}"))
    return "\n".join(lines)


def _build_agent_messages(
    conv_text: str,
    tools_text: str,
    skills_text: str,
    system_prompt: str,
    system_info: dict,
    max_steps: int,
) -> list[dict]:
    """构建子代理 LLM 调用 messages"""
    agent_md = _load_agent_md()
    agent_md = agent_md.replace("{{max_steps}}", str(max_steps))

    # 截断过长的 system_prompt（保留前面部分优先：soul + skills + permanent improve）
    sp_text = system_prompt
    if len(sp_text) > 3000:
        sp_text = sp_text[:3000] + "\n\n...(后续省略)"

    si = system_info
    info_lines = [
        f"用户名: {si.get('user_name', '?')}",
        f"当前时间: {si.get('current_time', '?')}",
        f"项目根路径: {si.get('project_root', '?')}",
    ]

    user_message = (
        "## 系统信息\n\n"
        + "\n".join(info_lines)
        + "\n\n## 当前对话\n\n"
        + (conv_text or "（无对话）")
        + "\n\n## 可用工具列表\n\n"
        + tools_text
        + "\n\n## 可用技能目录\n\n"
        + skills_text
        + "\n\n## 系统提示上下文\n\n"
        + sp_text
    )

    return [
        {"role": "system", "content": agent_md},
        {"role": "user", "content": user_message},
    ]


def _parse_response(response_text: str) -> dict | None:
    """从 LLM 响应中提取 JSON 对象（多策略容错）"""
    text = response_text.strip()

    # 策略1：从 ```json 代码块中提取
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # 策略2：从任意 ``` 代码块中提取
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # 策略3：尝试解析全文
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略4：通过 { } 括号匹配提取 JSON 对象（兜底）
    first_brace = text.find("{")
    if first_brace >= 0:
        depth = 0
        for i in range(first_brace, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[first_brace:i + 1])
                    except json.JSONDecodeError:
                        break

    return None


def _validate_plan(plan: dict, tools_schemas: list[dict], max_steps: int) -> str | None:
    """校验计划结构，返回错误信息或 None（通过）"""
    if not isinstance(plan, dict):
        return "计划必须是 JSON 对象"

    # 检查必填字段
    for field in ("title", "steps"):
        if field not in plan:
            return f"缺少必填字段: {field}"

    if not isinstance(plan.get("title"), str) or not plan["title"].strip():
        return "title 必须是非空字符串"

    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return "steps 必须是数组"
    if not steps:
        return "steps 不能为空"
    if len(steps) > max_steps:
        return f"步骤数 {len(steps)} 超过上限 {max_steps}"

    # 收集所有已注册的工具名
    valid_names: set[str] = set()
    for s in tools_schemas:
        fn = s.get("function", {})
        name = fn.get("name", "")
        if name:
            valid_names.add(name)

    # 校验每个步骤
    seen_ids: set[str] = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return f"步骤 {i+1} 必须是对象"

        sid = step.get("id", f"step_{i+1}")
        if sid in seen_ids:
            return f"步骤 ID 重复: {sid}"
        seen_ids.add(sid)

        if not step.get("description"):
            return f"步骤 {sid} 缺少 description"

        tc_list = step.get("tool_calls", [])
        if not isinstance(tc_list, list):
            return f"步骤 {sid} 的 tool_calls 必须是数组"

        for j, tc in enumerate(tc_list):
            action = tc.get("action", "")
            if not action:
                return f"步骤 {sid} tool_call[{j}] 缺少 action"
            if action not in valid_names:
                return f"步骤 {sid} 使用了未注册的工具: {action}"
            if action.startswith("task_plan_"):
                return f"步骤 {sid} 禁止引用任务计划管理工具: {action}"

    return None


# ──── 入口函数 ────


def generate_plan(
    provider,
    messages: list[dict],
    tools_schemas: list[dict],
    skills_info: list[dict],
    system_prompt: str,
    system_info: dict,
    max_steps: int = 10,
) -> dict:
    """分析用户请求并生成执行计划。

    Args:
        provider: LLM provider（需支持 respond(messages, tools=None)）
        messages: 当前完整对话消息
        tools_schemas: 已注册的工具 Schema 列表（来自 load_tool_schemas()）
        skills_info: 技能摘要列表（来自 register_all()）
        system_prompt: 当前主代理的完整 system prompt
        system_info: {"user_name": str, "current_time": str, "project_root": str}
        max_steps: 计划步骤上限（默认 10）

    Returns:
        {"plan": dict | None, "error": str | None}
    """
    conv_text = _extract_conversation_text(messages)

    # 简单任务检测：只有 1-2 条用户消息且没有工具调用 → 可能不需要计划
    user_msgs = [m for m in messages if m.get("role") == "user"]
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    if len(user_msgs) <= 1 and len(tool_msgs) == 0:
        last_content = user_msgs[-1].get("content", "") if user_msgs else ""
        # 过滤明显不需要计划的简短请求
        simple_patterns = ["你好", "hi", "hello", "帮助", "help", "? ", "？"]
        if len(last_content) < 50 or any(p in last_content.lower() for p in simple_patterns):
            return {"plan": None, "error": None}

    tools_text = _build_tools_text(tools_schemas)
    skills_text = _build_skills_text(skills_info)
    agent_messages = _build_agent_messages(
        conv_text, tools_text, skills_text,
        system_prompt, system_info, max_steps,
    )

    try:
        response = provider.respond(agent_messages, tools=None)
        response_text = response.text
    except Exception as e:
        return {"plan": None, "error": f"LLM 调用失败: {e}"}

    parsed = _parse_response(response_text)
    if parsed is None:
        return {"plan": None, "error": "无法解析子代理响应为 JSON"}

    # 允许返回 null plan（表示不需要计划）
    if isinstance(parsed, dict) and parsed.get("plan") is None:
        return {"plan": None, "error": None}

    plan = parsed.get("plan") if isinstance(parsed, dict) else parsed

    err = _validate_plan(plan, tools_schemas, max_steps)
    if err:
        return {"plan": None, "error": f"计划校验失败: {err}"}

    # 补齐标准化字段
    import uuid
    plan.setdefault("id", "plan_" + uuid.uuid4().hex[:8])
    plan.setdefault("description", "")
    plan.setdefault("created_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    plan.setdefault("status", "pending")
    plan.setdefault("current_step", 0)
    for i, step in enumerate(plan.get("steps", [])):
        step.setdefault("id", f"step_{i+1}")
        step.setdefault("status", "pending")
        step.setdefault("result", None)
        step.setdefault("error", None)
        step.setdefault("critical", False)

    return {"plan": plan, "error": None}


def generate_plan_stream(
    provider,
    messages: list[dict],
    tools_schemas: list[dict],
    skills_info: list[dict],
    system_prompt: str,
    system_info: dict,
    max_steps: int = 10,
) -> Generator[dict, None, None]:
    """流式版 generate_plan — 逐 chunk yield 思考过程。

    yield 事件:
        {"type": "plan_chunk", "content": str}        — 文本片段
        {"type": "plan_done", "plan": dict | None, "error": str | None}  — 最终结果
    """
    conv_text = _extract_conversation_text(messages)

    # 简单任务检测（与同步版一致）
    user_msgs = [m for m in messages if m.get("role") == "user"]
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    if len(user_msgs) <= 1 and len(tool_msgs) == 0:
        last_content = user_msgs[-1].get("content", "") if user_msgs else ""
        simple_patterns = ["你好", "hi", "hello", "帮助", "help", "? ", "？"]
        if len(last_content) < 50 or any(p in last_content.lower() for p in simple_patterns):
            yield {"type": "plan_done", "plan": None, "error": None}
            return

    tools_text = _build_tools_text(tools_schemas)
    skills_text = _build_skills_text(skills_info)
    agent_messages = _build_agent_messages(
        conv_text, tools_text, skills_text,
        system_prompt, system_info, max_steps,
    )

    # 流式调用：full_text 只积累 text_chunk（供 JSON 解析），thinking_chunk 仅推送前端
    full_text = ""
    try:
        for event in provider.respond_stream(agent_messages, tools=None):
            if event.get("type") == "text_chunk":
                chunk = event.get("content", "")
                full_text += chunk
                yield {"type": "plan_chunk", "content": chunk}
            elif event.get("type") == "thinking_chunk":
                yield {"type": "plan_chunk", "content": event.get("content", "")}
    except Exception as e:
        yield {"type": "plan_done", "plan": None, "error": f"LLM 调用失败: {e}"}
        return

    # 解析和校验
    parsed = _parse_response(full_text)
    if parsed is None:
        yield {"type": "plan_done", "plan": None, "error": "无法解析子代理响应为 JSON"}
        return

    if isinstance(parsed, dict) and parsed.get("plan") is None:
        yield {"type": "plan_done", "plan": None, "error": None}
        return

    plan = parsed.get("plan") if isinstance(parsed, dict) else parsed

    err = _validate_plan(plan, tools_schemas, max_steps)
    if err:
        yield {"type": "plan_done", "plan": None, "error": f"计划校验失败: {err}"}
        return

    # 补齐标准化字段
    import uuid
    plan.setdefault("id", "plan_" + uuid.uuid4().hex[:8])
    plan.setdefault("description", "")
    plan.setdefault("created_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    plan.setdefault("status", "pending")
    plan.setdefault("current_step", 0)
    for i, step in enumerate(plan.get("steps", [])):
        step.setdefault("id", f"step_{i+1}")
        step.setdefault("status", "pending")
        step.setdefault("result", None)
        step.setdefault("error", None)
        step.setdefault("critical", False)

    yield {"type": "plan_done", "plan": plan, "error": None}
