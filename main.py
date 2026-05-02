"""核心 Agent 主循环 — CLI 模式"""
import atexit
import json
import os
import signal
import sys

from provider.openai_api import DeepSeekProvider
from run.chat import ChatManager
from run.engine import build_system_prompt, run_chat_turn, _fmt_tool_line
from run.summarize import summarize_and_store, sync_to_new_archives
from run.tool import ToolRunner, load_tool_schemas


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

    # 初始化 provider 和工具系统
    provider = DeepSeekProvider(user_config, core_config)
    tool_runner = ToolRunner(core_config, user_config)
    system_prompt = build_system_prompt(root, user_dir)  # 内部调用 register_all() 填充 TOOL_REGISTRY
    tools = load_tool_schemas()  # 必须在 build_system_prompt 之后，否则注册表为空

    # 初始化对话管理
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_system_prompt(system_prompt)
    chat.load_history()

    # 退出时保存（含摘要）
    def _on_exit():
        try:
            summarize_and_store(provider, chat.messages, user_dir)
            chat.save_history()
            chat.save_log(chat.build_messages())
        except Exception:
            pass

    atexit.register(_on_exit)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"\n系统已就绪，用户: {os.path.basename(user_dir)}")
    print("命令: /exit 退出  /clear 清除历史  /history 状态  /archive 归档  /summarize 摘要  /help 帮助\n")

    # 命令分发
    def _dispatch(cmd: str) -> bool | None:
        cmd = cmd.strip().lower()
        if cmd in ("/exit", "/quit", "/q"):
            print("正在生成摘要…")
            s = summarize_and_store(provider, chat.messages, user_dir)
            if s:
                print(f"对话摘要: {s}")
            chat.save_history()
            chat.save_log(chat.build_messages())
            print("再见！")
            return True
        if cmd == "/clear":
            summarize_and_store(provider, chat.messages, user_dir)
            msg = chat.clear_history()
            sync_to_new_archives(user_dir)
            print(msg)
            chat.save_history()
            return False
        if cmd in ("/history", "/stats"):
            print(chat.history_stats())
            return False
        if cmd == "/archive":
            summarize_and_store(provider, chat.messages, user_dir)
            archive_dir = os.path.join(user_dir, "history", "archive")
            before = set(os.listdir(archive_dir)) if os.path.isdir(archive_dir) else set()
            msg = chat.archive_now()
            sync_to_new_archives(user_dir, before)
            print(msg)
            return False
        if cmd in ("/summarize", "/summary", "/总结"):
            s = summarize_and_store(provider, chat.messages, user_dir)
            print(f"对话摘要: {s}" if s else "对话为空，无法摘要")
            return False
        if cmd == "/help":
            print("  /exit, /quit, /q    退出（自动摘要 + 保存）")
            print("  /clear              清除当前对话历史（自动摘要 + 归档备份）")
            print("  /history, /stats    查看历史状态")
            print("  /archive            手动归档当前历史（自动摘要）")
            print("  /summarize          生成对话摘要")
            print("  /help               显示此帮助")
            return False
        return None

    # 对话循环
    while True:
        try:
            user_input = input("您: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n正在生成摘要…")
            s = summarize_and_store(provider, chat.messages, user_dir)
            if s:
                print(f"对话摘要: {s}")
            print("再见！")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            result = _dispatch(user_input)
            if result is True:
                break
            if result is False:
                continue

        chat.add_user_message(user_input)
        tool_runner.reset_count()
        round_usages: list[dict] = []

        for event in run_chat_turn(chat, tool_runner, provider, tools):
            if event["type"] == "tool_call":
                print(f"  {event['line']}")
            elif event["type"] == "text_chunk":
                print(event["content"], end="", flush=True)
            elif event["type"] == "text_done":
                print()  # 流式结束换行
            elif event["type"] == "text":
                print(f"助手: {event['content']}")
            elif event["type"] == "usage":
                round_usages.append(event["data"])
            elif event["type"] == "error":
                print(f"\n[Provider 错误: {event['content']}]")
            elif event["type"] == "deadlock_warning":
                print("  ⚠ 同命令连败 3 次，已提示 LLM 换思路")
            elif event["type"] == "max_rounds":
                print("[已达到工具调用上限]")

        if round_usages:
            total_in = sum(u["prompt_tokens"] for u in round_usages)
            total_out = sum(u["completion_tokens"] for u in round_usages)
            total_cached = sum(u["cached_tokens"] for u in round_usages)
            print(f"[Token: 输入 {total_in} (缓存命中 {total_cached}) | 输出 {total_out} | 总计 {total_in + total_out}]\n")

        chat.save_history()
        chat.save_log(chat.build_messages())


if __name__ == "__main__":
    main()
