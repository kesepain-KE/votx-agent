# -*- coding: utf-8 -*-
"""Multi-User Long-Term Memory 工具 — mem_save / mem_get / mem_append / mem_search"""
import os
import re
from pathlib import Path

from run.tool import register_tool
from skills._common import err, truncate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _memory_dir(user_id: str) -> Path:
    """获取用户的 memory 目录路径"""
    return _PROJECT_ROOT / "users" / user_id / "memory"


def _memory_path(user_id: str, key: str) -> Path:
    """获取某个记忆文件的路径"""
    safe_key = _sanitize_key(key)
    return _memory_dir(user_id) / f"{safe_key}.md"


def _sanitize_key(key: str) -> str:
    """清理 key，只保留安全字符"""
    safe = re.sub(r'[^\w\-.]', '_', key)
    return safe or "untitled"


def mem_save(user_id: str, key: str, content: str) -> str:
    """保存一段记忆内容到用户的 memory 文件（覆盖写入）"""
    safe_key = _sanitize_key(key)
    mem_path = _memory_path(user_id, key)
    try:
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        mem_path.write_text(content.strip() + "\n", encoding="utf-8")
        return f"OK: 已保存记忆 [{safe_key}] 给用户 {user_id} ({len(content)} 字符)"
    except Exception as e:
        return err(f"保存记忆失败: {e}")


def mem_get(user_id: str, key: str) -> str:
    """读取一条记忆内容"""
    safe_key = _sanitize_key(key)
    mem_path = _memory_path(user_id, key)
    if not mem_path.exists():
        return err(f"用户 {user_id} 没有名为 [{safe_key}] 的记忆")
    try:
        content = mem_path.read_text(encoding="utf-8")
        return truncate(content, 8000)
    except Exception as e:
        return err(f"读取记忆失败: {e}")


def mem_append(user_id: str, key: str, content: str) -> str:
    """在一条记忆末尾追加内容"""
    safe_key = _sanitize_key(key)
    mem_path = _memory_path(user_id, key)
    try:
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        if mem_path.exists():
            old = mem_path.read_text(encoding="utf-8")
        else:
            old = ""
        new = (old.rstrip() + "\n\n" + content.strip() + "\n").lstrip()
        mem_path.write_text(new, encoding="utf-8")
        added = len(content)
        total = len(new)
        return f"OK: 已追加 {added} 字符到 [{safe_key}] (共 {total} 字符)"
    except Exception as e:
        return err(f"追加记忆失败: {e}")


def mem_search(user_id: str, query: str) -> str:
    """在用户的所有记忆文件中搜索关键词"""
    mem_dir = _memory_dir(user_id)
    if not mem_dir.exists():
        return err(f"用户 {user_id} 没有记忆文件")

    try:
        results = []
        for f in sorted(mem_dir.glob("*.md")):
            key = f.stem
            content = f.read_text(encoding="utf-8")
            # 简单关键词匹配（大小写不敏感）
            if query.lower() in content.lower():
                # 只显示匹配的上下文片段
                idx = content.lower().find(query.lower())
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 40)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                results.append(f"[{key}]: {snippet.strip()}")

        if not results:
            return f"用户 {user_id} 的记忆中未找到包含「{query}」的内容"
        summary = f"在 {len(results)} 个记忆文件中找到匹配:\n\n"
        return summary + "\n---\n".join(results)
    except Exception as e:
        return err(f"搜索记忆失败: {e}")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "mem_save",
            "description": "保存一段记忆内容到用户的 memory 文件。当用户说「记住」「保存」「记录」时使用。覆盖写入同名 key。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户名/用户 ID"},
                    "key": {"type": "string", "description": "记忆的键名，如 hobbies, preferences, tasks 等"},
                    "content": {"type": "string", "description": "记忆内容（Markdown 格式）"},
                },
                "required": ["user_id", "key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mem_get",
            "description": "读取一条记忆内容。当用户问「我之前说过什么」「帮我回忆」时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户名/用户 ID"},
                    "key": {"type": "string", "description": "记忆的键名"},
                },
                "required": ["user_id", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mem_append",
            "description": "在一条现有记忆末尾追加新内容，不覆盖已有内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户名/用户 ID"},
                    "key": {"type": "string", "description": "记忆的键名"},
                    "content": {"type": "string", "description": "要追加的内容"},
                },
                "required": ["user_id", "key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mem_search",
            "description": "在用户的所有记忆文件中搜索关键词，返回匹配的文件名和上下文片段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户名/用户 ID"},
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["user_id", "query"],
            },
        },
    },
]

HANDLERS = {
    "mem_save": mem_save,
    "mem_get": mem_get,
    "mem_append": mem_append,
    "mem_search": mem_search,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
