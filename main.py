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

    # System prompt
    with open(os.path.join(user_dir, "self_soul.md"), encoding="utf-8") as f:
        system_prompt = f.read()
    global_soul = os.path.join(root, "config", "soul.md")
    if os.path.exists(global_soul) and os.path.getsize(global_soul) > 0:
        with open(global_soul, encoding="utf-8") as f:
            content = f.read().strip()
            if content and not content.startswith("<!--"):
                system_prompt += "\n\n" + content

    # 注入项目 AGENT.md（让 LLM 了解自身能力、工具用法和项目结构）
    agent_md = os.path.join(root, "AGENT.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as f:
            system_prompt += "\n\n" + f.read()

    # 初始化
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_system_prompt(system_prompt)
    chat.load_history()

    provider = DeepSeekProvider(user_config)
    tool_runner = ToolRunner(core_config, user_config)
    register_all()
    tools = load_tool_schemas()

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
