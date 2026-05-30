"""核心 Agent 主循环 — CLI 模式"""
import atexit
import json
import os
import signal
import sys

from provider.factory import create_provider
from run.chat import ChatManager
from run.engine import run_chat_turn, _fmt_tool_line
from run.prompt_cache import build_cached_system_prompt
from run.summarize import summarize_and_store, sync_to_new_archives
from run.tool import ToolRunner, load_tool_schemas


def main():
    """执行命令行入口流程。"""
    user_dir = os.environ.get("VOTX_USER_DIR")
    if not user_dir:
        print("错误: 未指定用户目录")
        sys.exit(1)
    user_name = os.path.basename(user_dir)

    from paths import get_project_root
    root = get_project_root()

    # 加载配置
    with open(os.path.join(root, "config", "config_core.json"), encoding="utf-8") as f:
        core_config = json.load(f)

    # 启动 cron 后台调度
    from cron import start_cron, stop_cron
    start_cron(root, core_config)
    with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
        user_config = json.load(f)

    # 初始化 provider 和工具系统
    provider = create_provider(user_config, core_config)
    tool_runner = ToolRunner(core_config, user_config, user_dir=user_dir)
    system_prompt = build_cached_system_prompt(root, user_dir)  # 内部调用 register_all() 填充 TOOL_REGISTRY
    tools = load_tool_schemas()  # 必须在 build_system_prompt 之后，否则注册表为空

    # 初始化对话管理
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_provider(provider)
    chat.set_system_prompt(system_prompt)

    # 注入 auto_improve 上下文（供 auto_improve_review 工具使用）
    import plugins.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    # 注入 task_plan 上下文（供 task_plan_create 工具使用）
    import plugins.task_plan.tool as tp_tool
    tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    chat.load_history()

    # 退出时保存（含摘要）
    def _on_exit():
        """执行 on_exit 内部辅助逻辑。"""
        try:
            summarize_and_store(provider, chat.messages, user_dir)
            chat.save_history()
            chat.save_log(chat.build_messages())
            stop_cron()
        except Exception:
            pass

    atexit.register(_on_exit)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"\n系统已就绪，用户: {os.path.basename(user_dir)}")
    print("命令: /exit 退出  /clear 清除  /retry 重试  /history 状态  /archive 归档  /summarize 摘要  /help 帮助\n")

    # 执行一轮对话
    def _run_turn(user_text: str):
        """执行 run_turn 内部辅助逻辑。"""
        chat.add_user_message(user_text)
        tool_runner.reset_count()
        chat.refresh_system_prompt(root)
        round_usages: list[dict] = []

        for event in run_chat_turn(chat, tool_runner, provider, tools):
            if event["type"] == "tool_call":
                print(f"  {event['line']}")
            elif event["type"] == "text_chunk":
                print(event["content"], end="", flush=True)
            elif event["type"] == "text_done":
                print()
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

    # 命令分发
    def _dispatch(cmd: str) -> bool | None:
        """执行 dispatch 内部辅助逻辑。"""
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
            count = len(chat.messages)
            chat.messages = []
            try:
                if os.path.exists(chat.data_path):
                    os.remove(chat.data_path)
            except Exception:
                pass
            tl_count = 0
            try:
                if os.path.exists(chat.tool_log_path):
                    with open(chat.tool_log_path, encoding="utf-8") as f:
                        tl_count = sum(1 for _ in f)
                    os.remove(chat.tool_log_path)
            except Exception:
                pass
            extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
            print(f"已清除 {count} 条历史消息{extra}。")
            chat.save_history()
            return False
        if cmd == "/retry":
            last_user_idx = -1
            for i in range(len(chat.messages) - 1, -1, -1):
                if chat.messages[i].get("role") == "user":
                    last_user_idx = i
                    break
            if last_user_idx == -1:
                print("没有可重试的消息")
                return False
            user_msg = chat.messages[last_user_idx].get("content", "")
            chat.messages = chat.messages[:last_user_idx]
            chat.save_history()
            print(f"已移除上一条 AI 回复，重新发送…")
            _run_turn(user_msg)
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
            print("  /clear              清除当前对话历史及工具日志")
            print("  /retry              移除上一条 AI 回复并重新生成")
            print("  /history, /stats    查看历史状态")
            print("  /archive            手动归档当前历史")
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

        _run_turn(user_input)


if __name__ == "__main__":
    main()
