"""系统信息路由 — messages/system-prompt/export-markdown/stats/tool-logs/reload"""
import json
import os
import re
import traceback

from flask import Response, jsonify, request, session as flask_session

from web.server import app
from web.session import _root, get_session, get_active_user
from run.prompt_cache import invalidate_prompt_cache


@app.route("/api/messages")
def api_messages():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400
    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400
    return jsonify(chat.messages)


@app.route("/api/system-prompt")
def api_system_prompt():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400
    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data.get("user_dir", "")
    root = session_data.get("root", _root)

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
    agent_md = os.path.join(root, "AGENTS.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            agent = f.read()

    # 每次请求重建 system prompt — 自改进记忆/纠正记录可能已被其他会话更新
    try:
        from run.engine import build_system_prompt
        full = build_system_prompt(root, user_dir)
        chat.set_system_prompt(full)  # 同步更新内存中的 prompt
    except Exception:
        full = chat.system_prompt

    # 从 web 显示中剥离临时 improve（LLM 可见，web 不显示）
    import re
    display_full = re.sub(
        r'\n\n## 临时(?:记忆|规则|知识图谱)（待审阅）\n.*?(?=\n\n## |\Z)',
        '',
        full,
        flags=re.DOTALL,
    )

    other_parts = []

    # ── 顺序与 engine.py build_system_prompt() 保持一致 ──

    # 1. Skill 目录
    skill_lines = []
    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        for dirpath, dirnames, filenames in os.walk(skills_dir):
            if "SKILL.md" in filenames:
                skmd_path = os.path.join(dirpath, "SKILL.md")
                skill_dir = os.path.basename(dirpath)
                if skill_dir.startswith("_") or skill_dir == "__pycache__":
                    continue
                try:
                    text = open(skmd_path, encoding="utf-8").read()
                except Exception:
                    continue
                desc = ""
                if text.startswith("---"):
                    parts = text.split("---\n", 2)
                    if len(parts) >= 3:
                        m = re.search(r"^description:\s*(.+)$", parts[1], re.MULTILINE)
                        if m:
                            desc = m.group(1).strip().strip('"')
                has_tools = os.path.exists(os.path.join(dirpath, "tool.py"))
                skill_type = "🔧 工具型" if has_tools else "📋 指令型"
                skill_lines.append(f"- **{skill_dir}** ({skill_type}): {desc}")
    if skill_lines:
        other_parts.append("## Skill 目录（共 {} 个）\n\n{}".format(
            len(skill_lines), "\n".join(sorted(skill_lines))))

    # 2. 知识库索引（双层架构，data_structure.md）
    user_kb = os.path.join(user_dir, "knowledge")
    global_kb = os.path.join(root, "knowledge")
    has_user_kb = os.path.isdir(user_kb)
    has_global_kb = os.path.isdir(global_kb)

    if has_user_kb or has_global_kb:
        user_kb_rel = os.path.relpath(user_kb, root).replace("\\", "/")
        kb_parts = ["## 知识库（双层架构）\n"]
        kb_parts.append(f"- **用户级知识库（默认读写）**: `{user_kb_rel}/`")
        if has_user_kb:
            user_ds = os.path.join(user_kb, "data_structure.md")
            if os.path.isfile(user_ds):
                try:
                    ds = open(user_ds, encoding="utf-8").read().strip()
                    if ds:
                        kb_parts.append(f"\n### 用户知识库索引 (data_structure.md)\n{ds}")
                except Exception:
                    pass
        global_kb_rel = os.path.relpath(global_kb, root).replace("\\", "/")
        kb_parts.append(f"- **全局知识库（只读）**: `{global_kb_rel}/`")
        if has_global_kb:
            global_ds = os.path.join(global_kb, "data_structure.md")
            if os.path.isfile(global_ds):
                try:
                    ds = open(global_ds, encoding="utf-8").read().strip()
                    if ds:
                        kb_parts.append(f"\n### 全局知识库索引 (data_structure.md)\n{ds}")
                except Exception:
                    pass
        kb_parts.append("- **规则**: 检索同时搜索两层，用户级优先；默认写入用户级，明确说\"写入全局\"才写全局")
        other_parts.append("\n".join(kb_parts))

    # 3. 改善记忆 (permanent 层)
    improve_dir = os.path.join(user_dir, "improve")
    if os.path.isdir(improve_dir):
        # 永久记忆 (improve/memory/permanent/*.md)
        perm_mem_dir = os.path.join(improve_dir, "memory", "permanent")
        if os.path.isdir(perm_mem_dir):
            mem_files = sorted(
                f for f in os.listdir(perm_mem_dir) if f.endswith(".md") and not f.startswith(".")
            )
            if mem_files:
                mem_lines = ["## 永久记忆\n"]
                for fn in mem_files:
                    mem_lines.append(f"\n### {fn}\n")
                    try:
                        c = open(os.path.join(perm_mem_dir, fn), encoding="utf-8").read()
                        if len(c) > 3000:
                            c = c[:3000] + "\n\n…(截断)"
                        mem_lines.append(c)
                    except Exception:
                        mem_lines.append("(无法读取)")
                other_parts.append("\n".join(mem_lines))

        # 永久规则 (improve/self-improving/permanent/)
        perm_si_dir = os.path.join(improve_dir, "self-improving", "permanent")
        if os.path.isdir(perm_si_dir):
            for fn in ["memory.md", "corrections.md"]:
                fp = os.path.join(perm_si_dir, fn)
                if os.path.exists(fp):
                    try:
                        content = open(fp, encoding="utf-8").read().strip()
                        if content:
                            title = "自改进记忆 (HOT Tier)" if fn == "memory.md" else "纠正记录 (Corrections)"
                            if len(content) > 3000:
                                content = content[:3000] + "\n\n…(截断)"
                            other_parts.append(f"## {title}\n\n{content}")
                    except Exception:
                        pass

        # 永久知识图谱 (improve/ontology/permanent/*.md)
        perm_ont_dir = os.path.join(improve_dir, "ontology", "permanent")
        if os.path.isdir(perm_ont_dir):
            ont_files = sorted(
                f for f in os.listdir(perm_ont_dir) if f.endswith(".md") and not f.startswith(".")
            )
            if ont_files:
                ont_lines = ["## 永久知识图谱\n"]
                for fn in ont_files:
                    ont_lines.append(f"\n### {fn}\n")
                    try:
                        c = open(os.path.join(perm_ont_dir, fn), encoding="utf-8").read()
                        if len(c) > 3000:
                            c = c[:3000] + "\n\n…(截断)"
                        ont_lines.append(c)
                    except Exception:
                        ont_lines.append("(无法读取)")
                other_parts.append("\n".join(ont_lines))

    # 4. 会话状态 (SESSION-STATE.md) — 最后叠加
    session_state = os.path.join(root, "SESSION-STATE.md")
    if os.path.exists(session_state):
        try:
            content = open(session_state, encoding="utf-8").read().strip()
            if content:
                other_parts.append("## 会话状态 (SESSION-STATE.md)\n\n" + content)
        except Exception:
            pass

    other = "\n\n".join(other_parts) if other_parts else "（无额外注入内容）"

    return jsonify({
        "content": display_full,
        "soul": soul,
        "agent": agent,
        "other": other,
    })


@app.route("/api/export-markdown")
def api_export_markdown():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data:
        return jsonify({"error": "未选择用户"}), 400
    chat = session_data.get("chat")
    if not chat:
        return jsonify({"error": "未选择用户"}), 400

    lines = ["# votx-agent 对话导出", ""]
    user_name_val = session_data.get("user_name", "unknown")
    from datetime import datetime, timezone
    lines.append("**用户**: {}  |  **导出时间**: {}".format(
        user_name_val,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ))
    lines.append("")
    lines.append("---")
    lines.append("")

    for m in chat.messages:
        role = m.get("role", "")
        content = m.get("content", "")
        tool_calls = m.get("tool_calls")

        if role == "user":
            lines.append("### 🧑 用户")
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
                    lines.append("### 🔧 工具调用: `{}`".format(name))
                    lines.append("")
                    lines.append("```json")
                    lines.append(args_str)
                    lines.append("```")
                    lines.append("")
            if content:
                lines.append("### 🤖 助手")
                lines.append("")
                lines.append(content)
                lines.append("")
        elif role == "tool":
            tid = m.get("tool_call_id", "")[:16]
            lines.append("📋 工具结果 `{}...`:".format(tid))
            lines.append("")
            lines.append("```")
            lines.append(content[:2000] if len(content) > 2000 else content)
            if len(content) > 2000:
                lines.append("...[截断: 原始 {} 字符]".format(len(content)))
            lines.append("```")
            lines.append("")

    md = "\n".join(lines)
    return Response(md, mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=conversation.md"})


@app.route("/api/stats")
def api_stats():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    chat = session_data["chat"]
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

    # 累计 Token 统计
    token_stats = getattr(chat, 'token_stats', {})

    return jsonify({
        "msg_count": len(chat.messages),
        "tool_count": tool_count,
        "file_size": file_size,
        "token_stats": token_stats,
    })


@app.route("/api/tool-logs")
def api_tool_logs():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400
    user_dir = session_data["user_dir"]
    logs = []
    new_log_path = os.path.join(user_dir, "history", "log", "tool_log.jsonl")
    old_log_path = os.path.join(user_dir, "history", "log", "tool_log.json")
    for log_path in (new_log_path, old_log_path):
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


@app.route("/api/reload", methods=["POST"])
def api_reload_dynamic():
    """动态重载 system prompt + tools + ToolRunner，无需重启或重选用户"""
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    root = session_data["root"]
    chat = session_data["chat"]
    user_config = session_data.get("user_config", {})
    core_config = session_data.get("core_config", {})

    result = {"ok": True, "reloaded": []}
    warnings = []

    # 1. 重载 TOOL_REGISTRY + tool schemas
    try:
        from run.tool import TOOL_REGISTRY, load_tool_schemas
        import skills
        TOOL_REGISTRY.clear()
        skills.register_all()
        tools = load_tool_schemas()
        session_data["tools"] = tools
        result["reloaded"].append(f"tools ({len(tools)})")
    except Exception as e:
        warnings.append(f"tools: {e}")

    # 2. 重建 system prompt
    try:
        invalidate_prompt_cache(user_dir)
        from run.engine import build_system_prompt
        new_prompt = build_system_prompt(root, user_dir)
        chat.set_system_prompt(new_prompt)
        result["reloaded"].append("system_prompt")
    except Exception as e:
        warnings.append(f"system_prompt: {e}")

    # 3. 重建 ToolRunner
    try:
        from run.tool import ToolRunner
        session_data["tool_runner"] = ToolRunner(core_config, user_config)
        result["reloaded"].append("tool_runner")
    except Exception as e:
        warnings.append(f"tool_runner: {e}")

    if warnings:
        result["warnings"] = warnings

    return jsonify(result)
