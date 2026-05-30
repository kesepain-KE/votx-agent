"""系统信息路由 — messages/system-prompt/export-markdown/stats/tool-logs/reload"""
import json
import os
import re
import traceback

from flask import Response, jsonify, request, session as flask_session

from web.server import app
from web.session import _root, require_session
from run.prompt_cache import invalidate_prompt_cache


@app.route("/api/messages")
def api_messages():
    """处理 api_messages 相关逻辑。返回消息列表，role:tool 消息已过滤，tool_calls 装饰 log_id。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    chat = session_data["chat"]
    messages = [m for m in chat.messages if m.get("role") != "tool"]

    # 构建 {tool_call_id: log_id} 映射表
    tc_to_log: dict[str, str] = {}
    user_dir = session_data.get("user_dir", "")
    log_path = os.path.join(user_dir, "history", "log", "tool_log.jsonl")
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        tcid = entry.get("tool_call_id", "")
                        lid = entry.get("id", "")
                        if tcid and lid:
                            tc_to_log[tcid] = lid
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    # 给 assistant 消息的 tool_calls 装饰 log_id
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tc_id = tc.get("id", "")
                if tc_id in tc_to_log:
                    tc["log_id"] = tc_to_log[tc_id]

    return jsonify(messages)


@app.route("/api/system-prompt")
def api_system_prompt():
    """处理 api_system_prompt 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    chat = session_data["chat"]

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
    # 不能用 .*? 遇到 ## 就停 —— 临时记忆文件内容里可能含 ## 子标题
    # 临时章节之后只会出现「会话状态」或「活跃任务计划」这两个顶层 section
    import re
    display_full = re.sub(
        r'\n\n## 临时(?:记忆|规则|知识图谱)（待审阅）\n.*?(?=\n\n## (?:会话状态|活跃任务计划)|\Z)',
        '',
        full,
        flags=re.DOTALL,
    )

    other_parts = []

    # ── 顺序与 engine.py build_system_prompt() 保持一致 ──

    # 1. Skill 目录 — 复用 skills 模块缓存的扫描结果（按用户过滤禁用）
    try:
        from skills import get_filtered_skills_info
        all_skills = get_filtered_skills_info(user_dir)
    except Exception:
        all_skills = []
    if all_skills:
        builtin = [s for s in all_skills if s.get("origin") == "builtin"]
        user = [s for s in all_skills if s.get("origin") == "user"]
        if builtin:
            lines = [s.get("summary", f"- **{s['name']}**") for s in builtin]
            other_parts.append("## 内置技能（共 {} 个）\n\n{}".format(len(builtin), "\n".join(lines)))
        if user:
            lines = [s.get("summary", f"- **{s['name']}**") for s in user]
            other_parts.append("## 拓展技能（共 {} 个）\n\n{}".format(len(user), "\n".join(lines)))

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
                        mem_lines.append(c)
                    except Exception:
                        mem_lines.append("(无法读取)")
                other_parts.append("\n".join(mem_lines))

        # 永久规则 (improve/self-improving/permanent/*.md)
        perm_si_dir = os.path.join(improve_dir, "self-improving", "permanent")
        if os.path.isdir(perm_si_dir):
            si_files = sorted(
                f for f in os.listdir(perm_si_dir) if f.endswith(".md") and not f.startswith(".")
            )
            if si_files:
                si_lines = ["## 自改进规则（永久）\n"]
                for fn in si_files:
                    si_lines.append(f"\n### {fn}\n")
                    try:
                        c = open(os.path.join(perm_si_dir, fn), encoding="utf-8").read()
                        si_lines.append(c)
                    except Exception:
                        si_lines.append("(无法读取)")
                other_parts.append("\n".join(si_lines))

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
    """处理 api_export_markdown 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    chat = session_data["chat"]

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
    """处理 api_stats 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code
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
    """处理 api_tool_logs 相关逻辑。返回摘要，不含 result/elapsed。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    user_dir = session_data["user_dir"]
    logs = []
    skip_keys = {"result", "elapsed"}
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
                                entry = json.loads(line)
                                logs.append({k: v for k, v in entry.items() if k not in skip_keys})
                            except json.JSONDecodeError:
                                pass
            except Exception:
                pass

    return jsonify(logs)


@app.route("/api/tool-results/<log_id>")
def api_tool_result(log_id):
    """根据 log_id 返回单条工具调用的结果。"""
    session_data, err, code = require_session()
    if err:
        return err, code
    user_dir = session_data["user_dir"]
    log_path = os.path.join(user_dir, "history", "log", "tool_log.jsonl")
    if not os.path.exists(log_path):
        return jsonify({"error": "日志不存在"}), 404
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("id") == log_id:
                        return jsonify({
                            "result": entry.get("result", ""),
                            "tool": entry.get("tool", ""),
                            "success": entry.get("success", False),
                        })
                except json.JSONDecodeError:
                    pass
    except Exception:
        return jsonify({"error": "读取日志失败"}), 500
    return jsonify({"error": "未找到"}), 404


@app.route("/api/reload", methods=["POST"])
def api_reload_dynamic():
    """动态重载 system prompt + tools + ToolRunner，无需重启或重选用户"""
    session_data, err, code = require_session()
    if err:
        return err, code

    user_dir = session_data["user_dir"]
    root = session_data["root"]
    chat = session_data["chat"]
    user_config = session_data.get("user_config", {})
    core_config = session_data.get("core_config", {})

    result = {"ok": True, "reloaded": []}
    warnings = []
    disabled_skills = set()

    # 1. 重载 TOOL_REGISTRY + tool schemas
    try:
        from run.tool import TOOL_REGISTRY, load_tool_schemas
        from skills import load_disabled_skills
        import skills
        TOOL_REGISTRY.clear()
        skills.register_all()
        disabled_skills = load_disabled_skills(user_dir)
        tools = load_tool_schemas(disabled_skills=disabled_skills)
        session_data["tools"] = tools
        session_data["disabled_skills"] = disabled_skills
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
        if not disabled_skills:
            from skills import load_disabled_skills
            disabled_skills = load_disabled_skills(user_dir)
        session_data["tool_runner"] = ToolRunner(
            core_config,
            user_config,
            user_dir=user_dir,
            disabled_skills=disabled_skills,
        )
        try:
            from plugins._common import set_multimodal_context
            set_multimodal_context(
                provider=session_data.get("provider"),
                chat=chat,
                user_name=session_data.get("user_name", ""),
            )
        except Exception:
            pass
        result["reloaded"].append("tool_runner")
    except Exception as e:
        warnings.append(f"tool_runner: {e}")

    if warnings:
        result["warnings"] = warnings

    return jsonify(result)
