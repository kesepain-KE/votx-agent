"""核心 Agent 主循环"""
import atexit
import json
import os
import signal
import sys

from provider.openai_api import DeepSeekProvider
from run.chat import ChatManager
from run.tool import ToolRunner, load_tool_schemas
from skills import register_all

MAX_TOOL_ROUNDS = 20  # 单轮对话最大工具往返次数（复杂任务需要多轮）

# 工具图标映射
_TOOL_ICONS: dict[str, str] = {
    # file
    "read_file": "📖", "write_file": "✏️", "list_dir": "📂", "delete_file": "🗑️",
    # network
    "http_get": "🌐", "http_post": "📤",
    # shell
    "run_command": "⚡",
    # time
    "get_time": "🕐", "sleep": "⏰",
    # video
    "download_video": "🎬",
    # hotboard
    "query_hotboard": "🔥",
    # docx
    "create_docx": "📝", "read_docx": "📄",
    # search
    "tavily_search": "🔍",
    # self-improving-agent
    "log_learning": "🧠", "log_error": "🚨", "log_feature_request": "💡", "read_learnings": "📋",
    # agent-memory
    "mem_remember": "💾", "mem_recall": "🔎", "mem_learn": "📚", "mem_get_lessons": "📖",
    "mem_track_entity": "👤", "mem_get_entity": "🔍", "mem_stats": "📊",
}


def _pick_arg(name: str, args: dict) -> str:
    """提取展示用的关键参数"""
    # 文件类: 显示路径
    if name in ("read_file", "write_file", "list_dir", "delete_file", "read_docx"):
        return args.get("path", "")
    if name == "create_docx":
        return args.get("output_path", "") + ("/" + args.get("filename", "") if args.get("filename") else "")
    # 网络: 显示 URL
    if name in ("http_get", "http_post"):
        url = args.get("url", "")
        return url if len(url) <= 60 else url[:57] + "..."
    # shell: 显示命令
    if name == "run_command":
        cmd = args.get("command", "")
        return cmd if len(cmd) <= 60 else cmd[:57] + "..."
    # 下载: 显示 URL
    if name == "download_video":
        url = args.get("url", "")
        return url if len(url) <= 60 else url[:57] + "..."
    # 搜索: 显示关键词
    if name == "tavily_search":
        q = args.get("query", "")
        return q if len(q) <= 40 else q[:37] + "..."
    # 热榜: 显示区域+平台
    if name == "query_hotboard":
        area = args.get("area", "")
        plat = args.get("platforms", "")
        return f"{area}" + (f" / {plat}" if plat else "")
    # 时间: 显示秒数
    if name == "sleep":
        return f"{args.get('seconds', '')}s"
    # 学习: 显示摘要
    if name in ("log_learning", "log_feature_request"):
        s = args.get("summary", "") or args.get("capability", "")
        return s if len(s) <= 50 else s[:47] + "..."
    if name == "log_error":
        c = args.get("command", "")
        return c if len(c) <= 50 else c[:47] + "..."
    if name == "read_learnings":
        return args.get("file_name", "") or args.get("filter_area", "") or "全部"
    # 记忆: 显示内容摘要
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


def _fmt_usage(u: dict | None) -> str:
    """格式化 token 用量为短字符串"""
    if not u:
        return ""
    parts = [f"入 {u['prompt_tokens']}"]
    if u.get("cached_tokens"):
        parts.append(f"(命中 {u['cached_tokens']})")
    parts.append(f"| 出 {u['completion_tokens']}")
    parts.append(f"| 共 {u['total_tokens']}")
    return f"[{' '.join(parts)}]"


def _load_memory_context(user_dir: str) -> str:
    """从 agent-memory 数据库加载关键事实，注入 system prompt

    即使 /clear 清空对话历史，这些记忆仍然保留在 system prompt 中。
    """
    import sqlite3, json as _json
    db_path = os.path.join(user_dir, "agent_memory.db")
    if not os.path.exists(db_path):
        return ""

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # 加载最近活跃的事实（按最后访问时间排序，最多20条）
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
            tags = _json.loads(tags_str or "[]")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"- {content}{tag_str}")
        lines.append("\n请在对话中直接使用这些信息，无需再次询问用户。如果用户修改了某项信息，用 mem_remember 更新并用 mem_recall 确认。")
        return "\n".join(lines)
    except Exception:
        return ""


def main():
    user_dir = os.environ.get("KESEPAIN_USER_DIR")
    if not user_dir:
        print("错误: 未指定用户目录")
        sys.exit(1)

    root = os.path.dirname(__file__)

    # 加载配置
    with open(os.path.join(root, "config", "config_core.json"), encoding="utf-8") as f:
        core_config = json.load(f)
    with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
        user_config = json.load(f)

    # System prompt 基础：角色人设 + 运行纪律
    with open(os.path.join(user_dir, "self_soul.md"), encoding="utf-8") as f:
        system_prompt = f.read()
    global_soul = os.path.join(root, "config", "soul.md")
    if os.path.exists(global_soul) and os.path.getsize(global_soul) > 0:
        with open(global_soul, encoding="utf-8") as f:
            content = f.read().strip()
            if content and not content.startswith("<!--"):
                system_prompt += "\n\n" + content

    # 初始化 provider 和工具系统
    provider = DeepSeekProvider(user_config)
    tool_runner = ToolRunner(core_config, user_config)

    # 注册所有 Skill（agentskills.io 标准：扫描 SKILL.md → 加载 tool.py）
    skill_instructions = register_all()
    tools = load_tool_schemas()

    # 注入项目 AGENT.md（项目结构 + 工具列表 + 安全机制）
    agent_md = os.path.join(root, "AGENT.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            system_prompt += "\n\n" + f.read()

    # 注入 Skill 目录摘要（agentskills.io 渐进披露：仅 name+description，正文 on-demand）
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

    # 注入持久记忆上下文（/clear 后也不会丢失）
    mem_ctx = _load_memory_context(user_dir)
    if mem_ctx:
        system_prompt += "\n\n## 持久记忆（跨会话保留，/clear 不清除）\n" + mem_ctx

    # 初始化对话管理
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_system_prompt(system_prompt)
    chat.load_history()

    # 退出时保存
    def _on_exit():
        try:
            chat.save_history()
            chat.save_log(chat.build_messages())
        except Exception:
            pass

    atexit.register(_on_exit)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"\n系统已就绪，用户: {os.path.basename(user_dir)}")
    print("命令: /exit 退出  /clear 清除历史  /history 状态  /archive 归档\n")

    # 命令分发
    def _dispatch(cmd: str) -> bool | None:
        """返回 True=退出, False=已处理(跳过LLM), None=不是命令(交给LLM)"""
        cmd = cmd.strip().lower()
        if cmd in ("/exit", "/quit", "/q"):
            print("再见！")
            return True
        if cmd == "/clear":
            msg = chat.clear_history()
            print(msg)
            chat.save_history()
            return False
        if cmd in ("/history", "/stats"):
            print(chat.history_stats())
            return False
        if cmd == "/archive":
            msg = chat.archive_now()
            print(msg)
            return False
        if cmd == "/help":
            print("  /exit, /quit, /q    退出")
            print("  /clear              清除当前对话历史（自动归档备份）")
            print("  /history, /stats    查看历史状态")
            print("  /archive            手动归档当前历史")
            print("  /help               显示此帮助")
            return False
        return None  # 不是命令，交给 LLM

    # 对话循环
    while True:
        try:
            user_input = input("您: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        # 检查是否为斜杠命令
        if user_input.startswith("/"):
            result = _dispatch(user_input)
            if result is True:
                break
            if result is False:
                continue
            # None → 不是已知命令，交给 LLM 处理

        chat.add_user_message(user_input)
        tool_runner.reset_count()
        tool_round = 0
        round_usages: list[dict] = []
        # 死循环检测：跟踪连续失败
        _fail_streak = 0
        _last_fail_key = ""

        # 工具调用往返（上限 MAX_TOOL_ROUNDS）
        while tool_round < MAX_TOOL_ROUNDS:
            messages = chat.build_messages()
            try:
                response = provider.chat(messages, tools)
            except RuntimeError as e:
                print(f"[Provider 错误: {e}]")
                chat.add_assistant_message(f"ERROR: {e}")
                break

            # 记录本轮 token 用量
            if provider.last_usage:
                round_usages.append(provider.last_usage)

            if tool_runner.has_tool_calls(response):
                chat.add_tool_call_message(response.tool_calls)
                results, details = tool_runner.execute(response)
                chat.add_tool_results(results)
                tool_round += 1
                # 逐行展示每个工具调用（不显示 token）
                for d in details:
                    print(f"  {_fmt_tool_line(d['name'], d['args'], d['elapsed'], d['success'])}")
                    # 死循环检测：同一命令连续失败 3 次就警告 LLM
                    fail_key = f"{d['name']}|{_pick_arg(d['name'], d['args'])}"
                    if d['success']:
                        if fail_key == _last_fail_key:
                            _fail_streak = 0
                    elif fail_key == _last_fail_key:
                        _fail_streak += 1
                    else:
                        _fail_streak = 1
                        _last_fail_key = fail_key
                # 同命令连败 3 次：插入提示让 LLM 换思路
                if _fail_streak >= 3:
                    hint = (
                        "已连续失败 3 次相同操作。请立即停止重试，告诉用户: "
                        "1) 操作目标是什么 2) 遇到了什么错误 3) 需要用户提供什么帮助。不要继续调用工具。"
                    )
                    chat.add_user_message(hint)
                    print(f"  ⚠ 同命令连败 3 次，已提示 LLM 换思路")
                    _fail_streak = 0
            else:
                reply = response.content or ""
                print(f"助手: {reply}")
                chat.add_assistant_message(reply)
                break
        else:
            # 超过最大轮数
            chat.add_assistant_message("已达到最大工具调用轮数，请重新描述需求。")
            print("[已达到工具调用上限]")

        # 本轮对话结束，输出累计 token
        if round_usages:
            total_in = sum(u["prompt_tokens"] for u in round_usages)
            total_out = sum(u["completion_tokens"] for u in round_usages)
            total_cached = sum(u["cached_tokens"] for u in round_usages)
            print(f"[Token: 输入 {total_in} (缓存命中 {total_cached}) | 输出 {total_out} | 总计 {total_in + total_out}]\n")

        chat.save_history()
        chat.save_log(chat.build_messages())


if __name__ == "__main__":
    main()
