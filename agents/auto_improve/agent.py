# -*- coding: utf-8 -*-
"""Auto Improve 子代理 — 对话记忆提取与管理

两种触发模式：

1. 被动触发 (消息达上限) — run_auto_improve()
   读: improve/*/permanent/  (已知的永久内容)
   写: improve/*/temporary/  (新发现的临时内容)
   逻辑: 对比永久记忆，发现新事实/偏好/模式 → 暂存临时层

2. 主动触发 (用户调用) — run_auto_improve_active()
   读: improve/*/temporary/  (待审阅的临时内容)
   写: improve/*/permanent/  (确认晋升为永久)
   逻辑: 审阅临时记忆 → 去重/合并/提炼 → 晋升到永久层
"""

import json
import os
import re
from pathlib import Path

from run.io_utils import atomic_write_text

_VALID_SUBS = ("memory", "self-improving", "ontology")


def _improve_dir(user_dir: str) -> str:
    return os.path.join(user_dir, "improve")


def _safe_filename(name: str) -> str:
    safe = re.sub(r'[^\w\-.]', '_', name)
    return safe.strip("_") or "untitled"


def _extract_conversation_text(messages: list[dict], user_focused: bool = False) -> list[dict]:
    """提取纯对话（用户 + 助手回复，去除 tool_calls 和思考）

    Args:
        messages: 完整消息列表
        user_focused: True 时只提取用户消息（被动触发用）
    """
    core = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if user_focused:
            if role == "user" and content:
                core.append({"role": role, "content": content[:500]})
        else:
            if role in ("user", "assistant") and content and not m.get("tool_calls"):
                core.append({"role": role, "content": content[:500]})
    return core


def _read_files_by_tier(user_dir: str, tier: str) -> dict[str, str]:
    """读取指定 tier 下的所有记忆文件"""
    result = {}
    for sub in _VALID_SUBS:
        d = os.path.join(_improve_dir(user_dir), sub, tier)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".md"):
                fp = os.path.join(d, name)
                try:
                    content = Path(fp).read_text(encoding="utf-8")
                    result[f"{sub}/{tier}/{name}"] = content
                except Exception:
                    pass
    return result


def _ensure_dirs(user_dir: str):
    for sub in _VALID_SUBS:
        for tier in ("temporary", "permanent"):
            os.makedirs(os.path.join(_improve_dir(user_dir), sub, tier), exist_ok=True)


def _load_agent_md() -> str:
    root = Path(__file__).resolve().parent.parent.parent
    agent_md_path = root / "agents" / "auto_improve" / "AGENT.md"
    if agent_md_path.exists():
        return agent_md_path.read_text(encoding="utf-8")
    return ""


def _build_agent_messages(
    conv_core: list[dict],
    reference_memory: dict[str, str],
    mode: str,
    reference_label: str,
    target_label: str,
) -> list[dict]:
    """构建子代理 LLM 调用 messages"""
    system_prompt = _load_agent_md()

    conv_text = "\n".join(
        f"[{m['role']}]: {m['content']}" for m in conv_core
    )

    ref_text = f"（无已有{reference_label}）\n"
    if reference_memory:
        parts = [f"## 已有{reference_label}\n"]
        for path, content in reference_memory.items():
            parts.append(f"### {path}\n{content}\n")
        ref_text = "\n".join(parts)

    user_message = (
        f"模式: {mode}\n"
        f"参考层: {reference_label}（已固化内容，避免重复）\n"
        f"写入层: {target_label}\n\n"
        f"## 当前对话\n\n{conv_text}\n\n"
        f"{ref_text}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


def _parse_response(response_text: str) -> list[dict]:
    """从 LLM 响应中解析 JSON 操作列表"""
    try:
        text = response_text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        ops = json.loads(text)
        if isinstance(ops, list):
            return ops
        return []
    except json.JSONDecodeError:
        return []


def _apply_operations(ops: list[dict], user_dir: str, target_tier: str) -> tuple[int, list]:
    """执行记忆操作列表，返回 (执行数, 错误列表)"""
    executed = 0
    errors = []

    for op in ops:
        action = op.get("action", "")
        sub = op.get("sub", "memory")
        filename = _safe_filename(op.get("filename", "untitled"))
        content = op.get("content", "")

        if sub not in _VALID_SUBS:
            errors.append(f"无效 sub: {sub}")
            continue
        if not content and action != "delete":
            continue

        target_dir = os.path.join(_improve_dir(user_dir), sub, target_tier)
        filepath = os.path.join(target_dir, f"{filename}.md")

        try:
            if action in ("create", "update"):
                atomic_write_text(filepath, content.strip() + "\n")
                executed += 1
            elif action == "delete":
                if os.path.exists(filepath):
                    os.remove(filepath)
                    executed += 1
            elif action == "append":
                existing = ""
                if os.path.exists(filepath):
                    existing = Path(filepath).read_text(encoding="utf-8")
                new_content = existing.rstrip() + "\n\n" + content.strip() + "\n"
                atomic_write_text(filepath, new_content)
                executed += 1
        except Exception as e:
            errors.append(f"{action} {filepath}: {e}")

    if executed > 0:
        from run.prompt_cache import invalidate_prompt_cache
        invalidate_prompt_cache(os.path.basename(user_dir))

    return executed, errors


# ──── 入口函数 ────


def run_auto_improve(provider, messages: list[dict], user_dir: str) -> dict:
    """被动触发 — 消息达上限时调用。

    读 permanent（已知内容，避免重复）→ 分析对话 → 写 temporary（新发现）

    Args:
        provider: LLM provider
        messages: 被裁剪的旧消息
        user_dir: 用户目录
    """
    _ensure_dirs(user_dir)

    conv_core = _extract_conversation_text(messages, user_focused=True)
    if len(conv_core) < 2:
        return {"operations": 0, "errors": [], "summary": "用户消息太少，跳过记忆提取"}

    reference = _read_files_by_tier(user_dir, "permanent")
    agent_messages = _build_agent_messages(
        conv_core, reference,
        mode="被动触发（消息达上限）",
        reference_label="永久记忆/规则/知识图谱",
        target_label="临时记忆/规则/知识图谱",
    )

    try:
        response = provider.respond(agent_messages, tools=None)
        response_text = response.text
    except Exception as e:
        return {"operations": 0, "errors": [str(e)], "summary": f"LLM 调用失败: {e}"}

    ops = _parse_response(response_text)
    if not ops:
        return {"operations": 0, "errors": [], "summary": "未解析出记忆操作"}

    executed, errors = _apply_operations(ops, user_dir, "temporary")
    summary = f"[被动] 已执行 {executed} 个临时记忆操作"
    if errors:
        summary += f"，{len(errors)} 个失败"
    return {"operations": executed, "errors": errors, "summary": summary}


def run_auto_improve_active(provider, messages: list[dict], user_dir: str) -> dict:
    """主动触发 — 用户调用 auto_improve_review 时调用。

    读 temporary（待审阅内容）→ 分析对话 → 写 permanent（确认晋升）

    Args:
        provider: LLM provider
        messages: 当前全部消息
        user_dir: 用户目录
    """
    _ensure_dirs(user_dir)

    conv_core = _extract_conversation_text(messages, user_focused=False)
    if len(conv_core) < 2:
        return {"operations": 0, "errors": [], "summary": "对话太短，跳过记忆审阅"}

    reference = _read_files_by_tier(user_dir, "temporary")
    agent_messages = _build_agent_messages(
        conv_core, reference,
        mode="主动触发（用户调用审阅）",
        reference_label="临时记忆/规则/知识图谱（待审阅）",
        target_label="永久记忆/规则/知识图谱",
    )

    try:
        response = provider.respond(agent_messages, tools=None)
        response_text = response.text
    except Exception as e:
        return {"operations": 0, "errors": [str(e)], "summary": f"LLM 调用失败: {e}"}

    ops = _parse_response(response_text)
    if not ops:
        return {"operations": 0, "errors": [], "summary": "未解析出记忆操作"}

    executed, errors = _apply_operations(ops, user_dir, "permanent")
    summary = f"[主动] 已执行 {executed} 个永久记忆操作"
    if errors:
        summary += f"，{len(errors)} 个失败"
    return {"operations": executed, "errors": errors, "summary": summary}
