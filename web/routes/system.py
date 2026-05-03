"""系统信息路由 — messages/system-prompt/export-markdown/stats/tool-logs"""
import json
import os

from flask import Response, jsonify

from web.server import app
from web.session import _session, _root


@app.route("/api/messages")
def api_messages():
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400
    return jsonify(chat.messages)


@app.route("/api/system-prompt")
def api_system_prompt():
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session.get("user_dir", "")
    root = _session.get("root", _root)

    soul = ""
    soul_path = os.path.join(user_dir, "self_soul.md")
    if os.path.exists(soul_path):
        with open(soul_path, encoding="utf-8") as f:
            soul = f.read()
    global_soul = os.path.join(root, "config", "soul.md")
    if os.path.exists(global_soul) and os.path.getsize(global_soul) > 0:
        with open(global_soul, encoding="utf-8") as f:
            gs = f.read().strip()
            if gs and not gs.startswith("<!--"):
                soul += "\n\n" + gs

    agent = ""
    agent_md = os.path.join(root, "AGENT.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            agent = f.read()

    full = chat.system_prompt
    other_lines = []

    # 持久记忆
    mem_db = os.path.join(user_dir, "agent_memory.db")
    if os.path.exists(mem_db):
        try:
            import sqlite3
            conn = sqlite3.connect(mem_db)
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
            if rows:
                other_lines.append("## 持久记忆")
                for content, tags_str in rows:
                    try:
                        tags = json.loads(tags_str or "[]")
                    except Exception:
                        tags = []
                    tag_str = f" [{', '.join(tags)}]" if tags else ""
                    other_lines.append(f"- {content}{tag_str}")
        except Exception:
            pass

    # .learnings 摘要
    learnings_dir = os.path.join(user_dir, ".learnings")
    if os.path.isdir(learnings_dir):
        import re
        imported = False
        for fname, flabel in [("LEARNINGS.md", "学习"), ("ERRORS.md", "错误"), ("FEATURE_REQUESTS.md", "功能请求")]:
            fp = os.path.join(learnings_dir, fname)
            if os.path.exists(fp):
                if not imported:
                    other_lines.append("")
                    other_lines.append("## .learnings 记录")
                    imported = True
                try:
                    content = open(fp, encoding="utf-8").read()
                    # 按分隔符拆条目
                    entries = [e.strip() for e in content.split("\n---\n") if e.strip()]
                    # 过滤掉纯头部（第一个条目通常以 # 开头且不含 ## [）
                    real_entries = [e for e in entries if e.startswith("## [")]
                    total = len(real_entries)
                    pending = sum(1 for e in real_entries if "**Status**: pending" in e)
                    other_lines.append(f"- {flabel}: {total} 条 / {pending} 待处理")
                    # 列最近 3 条标题
                    for e in real_entries[:3]:
                        m = re.search(r"^## \[([^\]]+)\]\s*(.+)", e, re.MULTILINE)
                        if m:
                            sid = m.group(1)
                            title = m.group(2).strip()[:50]
                            st = "⏳" if "**Status**: pending" in e else "✅"
                            other_lines.append(f"  {st} [{sid}] {title}")
                except Exception:
                    other_lines.append(f"- {flabel}: 读取失败")

    other = "\n".join(other_lines) if other_lines else "暂无持久记忆或学习记录"

    return jsonify({
        "content": full,
        "soul": soul,
        "agent": agent,
        "other": other,
    })


@app.route("/api/export-markdown")
def api_export_markdown():
    chat = _session.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    lines = [f"# votx-agent 对话导出", ""]
    user_name = _session.get("user_name", "unknown")
    from datetime import datetime, timezone
    lines.append(f"**用户**: {user_name}  |  **导出时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for m in chat.messages:
        role = m.get("role", "")
        content = m.get("content", "")
        tool_calls = m.get("tool_calls")

        if role == "user":
            lines.append(f"### 🧑 用户")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            if tool_calls:
                for tc in tool_calls:
                    name = tc.get("function", {}).get("name", "unknown")
                    args = tc.get("function", {}).get("arguments", "{}")
                    try:
                        args_obj = json.loads(args)
                        args_str = json.dumps(args_obj, ensure_ascii=False)
                    except Exception:
                        args_str = args
                    lines.append(f"### 🔧 工具调用: `{name}`")
                    lines.append("")
                    lines.append(f"```json")
                    lines.append(args_str)
                    lines.append(f"```")
                    lines.append("")
            if content:
                lines.append(f"### 🤖 助手")
                lines.append("")
                lines.append(content)
                lines.append("")
        elif role == "tool":
            tid = m.get("tool_call_id", "")[:16]
            lines.append(f"📋 工具结果 `{tid}...`:")
            lines.append("")
            lines.append(f"```")
            lines.append(content[:2000] if len(content) > 2000 else content)
            if len(content) > 2000:
                lines.append(f"...[截断: 原始 {len(content)} 字符]")
            lines.append(f"```")
            lines.append("")

    md = "\n".join(lines)
    return Response(md, mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=conversation.md"})


@app.route("/api/stats")
def api_stats():
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    chat = _session["chat"]
    tool_count = 0
    if os.path.exists(chat.tool_log_path):
        try:
            with open(chat.tool_log_path, encoding="utf-8") as f:
                tool_count = sum(1 for _ in f)
        except Exception:
            pass
    file_size = 0
    if os.path.exists(chat.data_path):
        try:
            file_size = os.path.getsize(chat.data_path)
        except Exception:
            pass
    return jsonify({
        "msg_count": len(chat.messages),
        "tool_count": tool_count,
        "file_size": file_size,
    })


@app.route("/api/tool-logs")
def api_tool_logs():
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = _session["user_dir"]
    log_path = os.path.join(user_dir, "history", "log", "tool_log.json")

    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

    return jsonify(logs)
