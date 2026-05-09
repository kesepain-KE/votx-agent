"""对话引擎 — 可复用的 chat turn 生成器

CLI (main.py) 和 Web (web/server.py) 共用此模块。
每个 turn 的 tool calling 循环在这里统一处理，调用方只需消费事件流。
"""
import json
import os
import time as _time

from run.tool import load_tool_schemas
from skills import register_all


def _load_max_tool_rounds():
    try:
        from paths import get_project_root
        config_path = os.path.join(get_project_root(), "config", "config_core.json")
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("tool", {}).get("tool_max_per_type", 80)
    except Exception:
        return 80

MAX_TOOL_ROUNDS = _load_max_tool_rounds()

_TOOL_ICONS: dict[str, str] = {
    "read_file": "📖", "write_file": "✏️", "list_dir": "📂", "delete_file": "🗑️",
    "http_get": "🌐", "http_post": "📤",
    "run_command": "⚡",
    "get_time": "🕐", "sleep": "⏰",
    "download_video": "🎬",
    "query_hotboard": "🔥",
    "create_docx": "📝", "read_docx": "📄",
    "tavily_search": "🔍",
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

    agent_md = os.path.join(root, "AGENTS.md")
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

    # ── 知识库（双层架构，注入 data_structure.md 索引） ──
    user_kb = os.path.join(user_dir, "knowledge")
    global_kb = os.path.join(root, "knowledge")
    has_user_kb = os.path.isdir(user_kb)
    has_global_kb = os.path.isdir(global_kb)

    if has_user_kb or has_global_kb:
        kb_lines = ["\n\n## 知识库（双层架构）"]

        # 用户级
        user_kb_rel = os.path.relpath(user_kb, root).replace("\\", "/")
        if has_user_kb:
            kb_lines.append(f"- **用户级知识库（默认读写）**: `{user_kb_rel}/`")
            user_ds = os.path.join(user_kb, "data_structure.md")
            if os.path.isfile(user_ds):
                try:
                    ds_content = open(user_ds, encoding="utf-8").read().strip()
                    if ds_content:
                        kb_lines.append(f"\n### 用户知识库索引\n{ds_content}")
                except Exception:
                    pass
        else:
            kb_lines.append(f"- **用户级知识库**: `{user_kb_rel}/` 尚不存在，可手动创建并放入文档")

        # 全局级
        if has_global_kb:
            global_kb_rel = os.path.relpath(global_kb, root).replace("\\", "/")
            kb_lines.append(f"- **全局知识库（只读，除非用户明确指示写入）**: `{global_kb_rel}/`")
            global_ds = os.path.join(global_kb, "data_structure.md")
            if os.path.isfile(global_ds):
                try:
                    ds_content = open(global_ds, encoding="utf-8").read().strip()
                    if ds_content:
                        kb_lines.append(f"\n### 全局知识库索引\n{ds_content}")
                except Exception:
                    pass

        kb_lines.append("- **规则**: 检索时同时搜索两层，用户级结果优先；默认写入用户级，只有用户明确说\"写入全局\"时才写入全局知识库")
        system_prompt += "\n".join(kb_lines)

    # ── 自改进记忆 (HOT Tier) ──
    si_mem = os.path.join(user_dir, "self-improving", "memory.md")
    if os.path.exists(si_mem) and os.path.getsize(si_mem) > 0:
        try:
            content = open(si_mem, encoding="utf-8").read().strip()
            if content:
                system_prompt += "\n\n## 自改进记忆（HOT Tier — 用户偏好、模式、规则）\n" + content
        except Exception:
            pass

    # ── 纠正记录 ──
    si_corr = os.path.join(user_dir, "self-improving", "corrections.md")
    if os.path.exists(si_corr) and os.path.getsize(si_corr) > 0:
        try:
            content = open(si_corr, encoding="utf-8").read().strip()
            if content:
                system_prompt += "\n\n## 纠正记录（Corrections — 过往被纠正的错误）\n" + content
        except Exception:
            pass

    # ── 长期记忆 (mem_* 文件) ──
    mem_dir = os.path.join(user_dir, "memory")
    if os.path.isdir(mem_dir):
        mem_files = sorted(
            f for f in os.listdir(mem_dir) if f.endswith(".md") and not f.startswith(".")
        )
        if mem_files:
            system_prompt += "\n\n## 长期记忆（跨会话持久化）"
            for fn in mem_files:
                try:
                    c = open(os.path.join(mem_dir, fn), encoding="utf-8").read().strip()
                    if c:
                        # 单文件限制 2000 字符，避免 prompt 膨胀
                        if len(c) > 2000:
                            c = c[:2000] + "\n\n...(截断)"
                        system_prompt += f"\n\n[{fn}]\n{c}"
                except Exception:
                    pass

    session_state = os.path.join(root, "SESSION-STATE.md")
    if os.path.exists(session_state):
        try:
            content = open(session_state, encoding="utf-8").read().strip()
            if content:
                system_prompt += "\n\n## 会话状态（SESSION-STATE.md — Hot RAM）\n" + content
        except Exception:
            pass

    return system_prompt


def run_chat_turn(chat, tool_runner, provider, tools: list[dict]):
    """执行一轮对话的工具调用循环，生成事件 dict (生成器模式)。

    调用方必须先调用 chat.add_user_message() 和 tool_runner.reset_count()。

    循环逻辑:
    1. 发送 messages + tools → LLM 返回 response
    2. 如果 response 含 tool_calls → 执行工具 → 将结果追加到消息 → 回到步骤 1
    3. 如果 response 无 tool_calls → 这是最终文本回复 → 结束
    4. 达到 MAX_TOOL_ROUNDS → 强制终止，防止无限循环

    Yields:
        {"type": "tool_call", "name": str, "icon": str, "args": dict,
         "elapsed": float, "success": bool, "line": str}
        {"type": "text", "content": str} / {"type": "text_chunk", "content": str}
        {"type": "thinking_chunk"/"thinking"/"thinking_done"}
        {"type": "usage", "data": {"prompt_tokens": int, ..., "elapsed": int}}
        {"type": "error", "content": str}
        {"type": "max_rounds"}
        {"type": "deadlock_warning"}
    """
    tool_round = 0
    _fail_streak = 0        # 连续失败计数器
    _last_fail_key = ""      # 上次失败的工具+参数签名
    _turn_start = _time.time()

    while tool_round < MAX_TOOL_ROUNDS:
        messages = chat.build_messages()

        # 流式路径：思考先于正文，逐 chunk yield
        if getattr(provider, "stream", False):
            try:
                full_text = ""
                full_thinking = ""
                for item in provider.respond_stream(messages, tools):
                    if isinstance(item, dict):
                        if item.get("type") == "thinking_chunk":
                            full_thinking += item["content"]
                            yield {"type": "thinking_chunk", "content": item["content"]}
                        elif item.get("type") == "text_chunk":
                            full_text += item["content"]
                            yield {"type": "text_chunk", "content": item["content"]}
                    else:
                        # 兼容旧版（纯字符串）
                        full_text += str(item)
                        yield {"type": "text_chunk", "content": item}
                response = provider.last_response
                if full_thinking:
                    yield {"type": "thinking_done"}
                if provider.last_usage:
                    _elapsed = int((_time.time() - _turn_start) * 1000)
                    _has_tools = tool_runner.has_tool_calls(response)
                    chat.accumulate_usage(provider.last_usage, _has_tools, _elapsed)
                    yield {"type": "usage", "data": {**provider.last_usage, "elapsed": _elapsed}}
            except RuntimeError as e:
                yield {"type": "error", "content": str(e)}
                chat.add_assistant_message(f"ERROR: {e}")
                return
        else:
            try:
                response = provider.respond(messages, tools)
            except RuntimeError as e:
                yield {"type": "error", "content": str(e)}
                chat.add_assistant_message(f"ERROR: {e}")
                return

            # 非流式下的思考内容
            thinking_text = response.reasoning
            if thinking_text:
                yield {"type": "thinking", "content": thinking_text}

            if provider.last_usage:
                _elapsed = int((_time.time() - _turn_start) * 1000)
                _has_tools = tool_runner.has_tool_calls(response)
                chat.accumulate_usage(provider.last_usage, _has_tools, _elapsed)
                yield {"type": "usage", "data": {**provider.last_usage, "elapsed": _elapsed}}

        if tool_runner.has_tool_calls(response):
            reasoning = response.reasoning
            chat.add_tool_call_message(response.tool_calls, reasoning)
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
            # 无 tool_calls → 这是最终回复
            if getattr(provider, "stream", False):
                reasoning = provider.last_response.reasoning if provider.last_response else ""
                chat.add_assistant_message(full_text, reasoning)
                yield {"type": "text_done"}
            else:
                reasoning = response.reasoning
                reply = response.text
                chat.add_assistant_message(reply, reasoning)
                yield {"type": "text", "content": reply}
            return
    else:
        chat.add_assistant_message("已达到最大工具调用轮数，请重新描述需求。")
        yield {"type": "max_rounds"}
