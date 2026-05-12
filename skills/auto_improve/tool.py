# -*- coding: utf-8 -*-
"""Auto Improve Skill — 用户主动触发的永久记忆/规则/知识图谱管理"""

import os
import re
from pathlib import Path

from run.tool import register_tool
from skills._common import err, truncate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_VALID_SUBS = {"memory", "self-improving", "ontology"}

# 共享上下文：因 register_all() 用 importlib 重载本模块，需通过 skills._auto_improve_ctx 共享
import skills as _skills_mod
_ctx = _skills_mod._auto_improve_ctx


def set_auto_improve_context(provider=None, chat=None, user_name: str = ""):
    """由引擎在每轮对话前调用，注入 provider / chat / user_name"""
    _ctx["provider"] = provider
    _ctx["chat"] = chat
    _ctx["user_name"] = user_name


def _improve_dir(user_id: str) -> Path:
    return _PROJECT_ROOT / "users" / user_id / "improve"


def _sanitize_key(key: str) -> str:
    safe = re.sub(r'[^\w\-.]', '_', key)
    return safe.strip("_") or "untitled"


def _find_file(user_id: str, key: str, sub: str = "memory") -> tuple[Path | None, str | None]:
    """在 permanent 和 temporary 两层查找文件。返回 (path, tier) 或 (None, None)"""
    safe_key = _sanitize_key(key)
    filename = f"{safe_key}.md"
    improve = _improve_dir(user_id)
    for tier in ("permanent", "temporary"):
        fp = improve / sub / tier / filename
        if fp.exists():
            return fp, tier
    return None, None


def auto_improve_save(user_name: str, key: str, content: str,
                       sub: str = "memory") -> str:
    """保存到永久记忆（用户主动触发）。

    Args:
        user_name: 用户名
        key: 记忆键（文件名，不含扩展名）
        content: Markdown 内容
        sub: 子目录 — memory / self-improving / ontology
    """
    if sub not in _VALID_SUBS:
        return err(f'sub 必须是 {" / ".join(sorted(_VALID_SUBS))}，当前值: {sub}')
    safe_key = _sanitize_key(key)
    dir_path = _improve_dir(user_name) / sub / "permanent"
    dir_path.mkdir(parents=True, exist_ok=True)
    fp = dir_path / f"{safe_key}.md"
    try:
        fp.write_text(content.strip() + "\n", encoding="utf-8")
        return f"OK: 已保存永久{sub} [{safe_key}] ({len(content)} 字符)"
    except Exception as e:
        return err(f"保存失败: {e}")


def auto_improve_get(user_name: str, key: str, sub: str = "memory") -> str:
    """读取记忆（先查 permanent，再查 temporary）。

    Args:
        user_name: 用户名
        key: 记忆键
        sub: 子目录（默认 memory）
    """
    if sub not in _VALID_SUBS:
        return err(f'sub 必须是 {" / ".join(sorted(_VALID_SUBS))}，当前值: {sub}')
    fp, tier = _find_file(user_name, key, sub)
    if fp is None:
        return err(f"未找到 [{sub}] {key}")
    try:
        content = fp.read_text(encoding="utf-8")
        label = "永久" if tier == "permanent" else "临时"
        return truncate(f"[{label} {sub}] {fp.name}\n\n{content}", 8000)
    except Exception as e:
        return err(f"读取失败: {e}")


def auto_improve_search(user_name: str, query: str) -> str:
    """关键词搜索全部记忆（三层子目录 + 两层 tier）。

    Args:
        user_name: 用户名
        query: 搜索关键词
    """
    improve = _improve_dir(user_name)
    if not improve.exists():
        return err(f"用户 {user_name} 没有 improve 目录")

    results = []
    for sub in sorted(_VALID_SUBS):
        for tier in ("permanent", "temporary"):
            d = improve / sub / tier
            if not d.exists():
                continue
            for fp in sorted(d.glob("*.md")):
                try:
                    content = fp.read_text(encoding="utf-8")
                    if query.lower() in content.lower():
                        idx = content.lower().find(query.lower())
                        start = max(0, idx - 40)
                        end = min(len(content), idx + len(query) + 40)
                        snippet = content[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(content):
                            snippet = snippet + "..."
                        results.append(
                            f"[{tier}/{sub}] {fp.name}: {snippet.strip()}"
                        )
                except Exception:
                    pass

    if not results:
        return f"未找到包含「{query}」的记忆"
    return f"在 {len(results)} 处找到匹配:\n\n" + "\n---\n".join(results)


def auto_improve_delete(user_name: str, key: str, sub: str = "memory") -> str:
    """删除记忆（两层都可以删）。

    Args:
        user_name: 用户名
        key: 记忆键
        sub: 子目录
    """
    if sub not in _VALID_SUBS:
        return err(f'sub 必须是 {" / ".join(sorted(_VALID_SUBS))}，当前值: {sub}')
    fp, tier = _find_file(user_name, key, sub)
    if fp is None:
        return err(f"未找到 [{sub}] {key}")
    try:
        fp.unlink()
        return f"OK: 已删除{'永久' if tier == 'permanent' else '临时'}{sub} [{key}]"
    except Exception as e:
        return err(f"删除失败: {e}")


def auto_improve_review(user_name: str) -> str:
    """主动触发记忆审阅：读临时记忆 + 当前对话 → 分析 → 晋升到永久记忆。
    需要 engine 预先调用 set_auto_improve_context() 注入 provider 和 chat。
    """
    provider = _ctx.get("provider")
    chat = _ctx.get("chat")
    if not provider or not chat:
        return err("auto_improve_review 需要 provider/chat 上下文，请重启会话")
    messages = getattr(chat, "messages", [])
    if not messages:
        return err("当前无对话消息")

    user_dir = str(_PROJECT_ROOT / "users" / user_name)

    try:
        from agents.auto_improve.agent import run_auto_improve_active
        result = run_auto_improve_active(provider, messages, user_dir)
        return result.get("summary", "完成")
    except Exception as e:
        return err(f"审阅失败: {e}")


# ---- Schema ----

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "auto_improve_save",
            "description": "Save permanent memory/rule/ontology. Use when user says remember/save/记住/保存.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string", "description": "Username / user ID"},
                    "key": {
                        "type": "string",
                        "description": "记忆键（文件名不含扩展名），如 python_preferences, correction_001",
                    },
                    "content": {"type": "string", "description": "Markdown 格式记忆内容"},
                    "sub": {
                        "type": "string",
                        "description": "子目录: memory(事实/偏好), self-improving(规则/纠正), ontology(实体/关系)",
                        "enum": ["memory", "self-improving", "ontology"],
                    },
                },
                "required": ["user_name", "key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_improve_get",
            "description": "Read a memory entry. Checks permanent first, then temporary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string", "description": "Username / user ID"},
                    "key": {"type": "string", "description": "记忆键"},
                    "sub": {
                        "type": "string",
                        "description": "子目录",
                        "enum": ["memory", "self-improving", "ontology"],
                    },
                },
                "required": ["user_name", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_improve_search",
            "description": "Search all memory (all subs, both tiers) for a keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string", "description": "Username / user ID"},
                    "query": {"type": "string", "description": "Search keyword"},
                },
                "required": ["user_name", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_improve_delete",
            "description": "Delete a memory entry. Use when user says forget/remove/删除/忘记.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string", "description": "Username / user ID"},
                    "key": {"type": "string", "description": "记忆键"},
                    "sub": {
                        "type": "string",
                        "description": "子目录",
                        "enum": ["memory", "self-improving", "ontology"],
                    },
                },
                "required": ["user_name", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_improve_review",
            "description": "Active review: read temporary memory + current conversation → promote valuable content to permanent memory/rules/ontology. Use when user says review/审阅/整理记忆/检查记忆.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string", "description": "Username / user ID"},
                },
                "required": ["user_name"],
            },
        },
    },
]

HANDLERS = {
    "auto_improve_save": auto_improve_save,
    "auto_improve_get": auto_improve_get,
    "auto_improve_search": auto_improve_search,
    "auto_improve_delete": auto_improve_delete,
    "auto_improve_review": auto_improve_review,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
