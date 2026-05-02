"""对话引擎 — 可复用的 chat turn 生成器

CLI (main.py) 和 Web (web/server.py) 共用此模块。
每个 turn 的 tool calling 循环在这里统一处理，调用方只需消费事件流。
"""
import json
import os
import sqlite3

from run.tool import load_tool_schemas
from skills import register_all

MAX_TOOL_ROUNDS = 20

_TOOL_ICONS: dict[str, str] = {
    "read_file": "📖", "write_file": "✏️", "list_dir": "📂", "delete_file": "🗑️",
    "http_get": "🌐", "http_post": "📤",
    "run_command": "⚡",
    "get_time": "🕐", "sleep": "⏰",
    "download_video": "🎬",
    "query_hotboard": "🔥",
    "create_docx": "📝", "read_docx": "📄",
    "tavily_search": "🔍",
    "log_learning": "🧠", "log_error": "🚨", "log_feature_request": "💡", "read_learnings": "📋",
    "mem_remember": "💾", "mem_recall": "🔎", "mem_learn": "📚", "mem_get_lessons": "📖",
    "mem_track_entity": "👤", "mem_get_entity": "🔍", "mem_stats": "📊",
}


def _pick_arg(name: str, args: dict) -> str:
    """提取展示用的关键参数"""
    if name in ("read_file", "write_file", "list_dir", "delete_file", "read_docx"):
        return args.get("path", "")
    if name == "create_docx":
        return args.get("output_path", "") + ("/" + args.get("filename", "") if args.get("filename") else "")
    if name in ("http_get", "http_post"):
        url = args.get("url", "")
        return url if len(url) <= 60 else url[:57] + "..."
    if name == "run_command":
        cmd = args.get("command", "")
        return cmd if len(cmd) <= 60 else cmd[:57] + "..."
    if name == "download_video":
        url = args.get("url", "")
        return url if len(url) <= 60 else url[:57] + "..."
    if name == "tavily_search":
        q = args.get("query", "")
        return q if len(q) <= 40 else q[:37] + "..."
    if name == "query_hotboard":
        area = args.get("area", "")
        plat = args.get("platforms", "")
        return f"{area}" + (f" / {plat}" if plat else "")
    if name == "sleep":
        return f"{args.get('seconds', '')}s"
    if name in ("log_learning", "log_feature_request"):
        s = args.get("summary", "") or args.get("capability", "")
        return s if len(s) <= 50 else s[:47] + "..."
    if name == "log_error":
        c = args.get("command", "")
        return c if len(c) <= 50 else c[:47] + "..."
    if name == "read_learnings":
        return args.get("file_name", "") or args.get("filter_area", "") or "全部"
    if name == "mem_remember":
        c = args.get("content", "")
        return c if len(c) <= 40 else c[:37] + "..."
    if name in ("mem_recall",):
        return args.get("query", "")
    if name == "mem_track_entity":
        return f"{args.get('name','')} ({args.get('entity_type','person')})"
    if name == "mem_get_entity":
        return args.get("name", "")
    return ""


def _fmt_tool_line(name: str, args: dict, elapsed: float, success: bool) -> str:
    """格式化单行工具调用: 📖 read_file  /path/to/file  0.9s"""
    icon = _TOOL_ICONS.get(name, "🔧")
    param = _pick_arg(name, args)
    status = "" if success else " ❌"
    time_str = f"{elapsed:.1f}s" if elapsed > 0 else ""
    parts = [icon, f"{name:18s}"]
    if param:
        parts.append(f" {param}")
    if time_str:
        parts.append(f"  {time_str}")
    parts.append(status)
    return "".join(parts)


def _load_memory_context(user_dir: str) -> str:
    """从 agent-memory 数据库加载关键事实，注入 system prompt"""
    db_path = os.path.join(user_dir, "agent_memory.db")
    if not os.path.exists(db_path):
        return ""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT content, tags FROM facts
            WHERE superseded_by IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY last_accessed DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return ""
        lines = ["以下是从持久记忆中加载的已知信息："]
        for content, tags_str in rows:
            tags = json.loads(tags_str or "[]")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"- {content}{tag_str}")
        lines.append("\n请在对话中直接使用这些信息，无需再次询问用户。如果用户修改了某项信息，用 mem_remember 更新并用 mem_recall 确认。")
        return "\n".join(lines)
    except Exception:
        return ""


def build_system_prompt(root: str, user_dir: str) -> str:
    """组装完整 system prompt（与 main.py 保持一致）"""
    with open(os.path.join(user_dir, "self_soul.md"), encoding="utf-8") as f:
        system_prompt = f.read()

    global_soul = os.path.join(root, "config", "soul.md")
    if os.path.exists(global_soul) and os.path.getsize(global_soul) > 0:
        with open(global_soul, encoding="utf-8") as f:
            content = f.read().strip()
            if content and not content.startswith("<!--"):
                system_prompt += "\n\n" + content

    agent_md = os.path.join(root, "AGENT.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            system_prompt += "\n\n" + f.read()

    skill_instructions = register_all()
    if skill_instructions:
        tool_skills = [si for si in skill_instructions if si["has_tools"]]
        guide_skills = [si for si in skill_instructions if not si["has_tools"]]
        lines = ["\n\n## 可用 Skill 目录（详细指令用 read_file 读取 SKILL.md）"]
        if tool_skills:
            lines.append("\n### 工具型 Skill（可 function call）")
            for si in tool_skills:
                lines.append(si["summary"])
        if guide_skills:
            lines.append("\n### 指令型 Skill（正文引导）")
            for si in guide_skills:
                lines.append(si["summary"])
        system_prompt += "\n".join(lines)

    mem_ctx = _load_memory_context(user_dir)
    if mem_ctx:
        system_prompt += "\n\n## 持久记忆（跨会话保留，/clear 不清除）\n" + mem_ctx

    return system_prompt


def run_chat_turn(chat, tool_runner, provider, tools: list[dict]):
    """执行一轮对话的工具调用循环，生成事件 dict。

    chat.add_user_message() 必须在调用前完成，
    tool_runner.reset_count() 必须在调用前完成。

    Yields:
        {"type": "tool_call", "name": str, "icon": str, "args": dict,
         "elapsed": float, "success": bool, "line": str}
        {"type": "text", "content": str}
        {"type": "usage", "data": {"prompt_tokens": int, ...}}
        {"type": "error", "content": str}
        {"type": "max_rounds"}
        {"type": "deadlock_warning"}
    """
    tool_round = 0
    _fail_streak = 0
    _last_fail_key = ""

    while tool_round < MAX_TOOL_ROUNDS:
        messages = chat.build_messages()

        # 流式路径：逐 chunk yield 文本，完成后再处理 tool_calls
        if getattr(provider, "stream", False):
            import time as _time
            try:
                full_text = ""
                for delta in provider.chat_stream(messages, tools):
                    full_text += delta
                    if delta:
                        yield {"type": "text_chunk", "content": delta}
                response = provider._stream_result
                if provider.last_usage:
                    yield {"type": "usage", "data": provider.last_usage}
            except RuntimeError as e:
                yield {"type": "error", "content": str(e)}
                chat.add_assistant_message(f"ERROR: {e}")
                return
        else:
            try:
                response = provider.chat(messages, tools)
            except RuntimeError as e:
                yield {"type": "error", "content": str(e)}
                chat.add_assistant_message(f"ERROR: {e}")
                return

            if provider.last_usage:
                yield {"type": "usage", "data": provider.last_usage}

        if tool_runner.has_tool_calls(response):
            chat.add_tool_call_message(response.tool_calls)
            results, details = tool_runner.execute(response)
            chat.add_tool_results(results)
            tool_round += 1

            for d in details:
                line = _fmt_tool_line(d["name"], d["args"], d["elapsed"], d["success"])
                yield {
                    "type": "tool_call",
                    "name": d["name"],
                    "icon": _TOOL_ICONS.get(d["name"], "🔧"),
                    "args": d["args"],
                    "elapsed": d["elapsed"],
                    "success": d["success"],
                    "line": line,
                }

                # 死循环检测：同一命令连续失败 3 次就警告
                fail_key = f"{d['name']}|{_pick_arg(d['name'], d['args'])}"
                if d["success"]:
                    if fail_key == _last_fail_key:
                        _fail_streak = 0
                elif fail_key == _last_fail_key:
                    _fail_streak += 1
                else:
                    _fail_streak = 1
                    _last_fail_key = fail_key

            if _fail_streak >= 3:
                hint = (
                    "已连续失败 3 次相同操作。请立即停止重试，告诉用户: "
                    "1) 操作目标是什么 2) 遇到了什么错误 3) 需要用户提供什么帮助。不要继续调用工具。"
                )
                chat.add_user_message(hint)
                yield {"type": "deadlock_warning"}
                _fail_streak = 0
        else:
            reply = response.content or ""
            chat.add_assistant_message(reply)
            if getattr(provider, "stream", False):
                yield {"type": "text_done"}
            else:
                yield {"type": "text", "content": reply}
            return
    else:
        chat.add_assistant_message("已达到最大工具调用轮数，请重新描述需求。")
        yield {"type": "max_rounds"}
