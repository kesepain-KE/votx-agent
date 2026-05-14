"""votx-agent 启动入口

用法:
    python start.py           # CLI 模式（选择用户 → subprocess main.py）
    python start.py --web     # Web UI 模式（端口 13579）
    python start.py --web --port=8080   # Web UI 自定义端口
    python start.py --user <name> --prompt "<text>" --once  # 非交互单轮执行（cron 用）
"""
import os
import subprocess
import sys

from paths import get_project_root
root = get_project_root()


def main_cli():
    """CLI 模式：列出用户 → 选择 → 子进程 main.py"""
    users_dir = os.path.join(root, "users")
    user_list = sorted(os.listdir(users_dir))
    print("请选择当前用户:")
    for i, name in enumerate(user_list, 1):
        print(f"{i}: {name}")

    try:
        idx = int(input("请输入选择: ")) - 1
        selected = user_list[idx]
    except (ValueError, IndexError):
        print("无效选择")
        sys.exit(1)

    user_dir = os.path.join(users_dir, selected)
    print(f"已加载用户: {selected}")

    subprocess.run(
        [sys.executable, os.path.join(root, "main.py")],
        env={**os.environ, "VOTX_USER_DIR": user_dir},
    )


def main_web():
    """Web UI 模式"""
    port = 13579
    for arg in sys.argv:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
            break
    try:
        from web.server import run_server
    except ModuleNotFoundError as e:
        if e.name == "flask":
            print("ERROR: Web UI 依赖 Flask 未安装")
            print("请在当前 Python 环境执行:")
            print("  python -m pip install -r requirements.txt")
            print("或仅安装 Web 依赖:")
            print("  python -m pip install flask")
            sys.exit(1)
        raise
    run_server(port=port)


def main_once(user_name: str, prompt: str):
    """非交互模式：发送一条消息，执行一轮 tool calling，保存后退出。供 cron scheduler 调用。"""
    import json

    users_dir = os.path.join(root, "users")
    user_dir = os.path.join(users_dir, user_name)
    if not os.path.isdir(user_dir):
        print(f"错误: 用户不存在: {user_name}")
        sys.exit(1)

    os.environ["VOTX_USER_DIR"] = user_dir

    # 加载配置
    with open(os.path.join(root, "config", "config_core.json"), encoding="utf-8") as f:
        core_config = json.load(f)
    with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
        user_config = json.load(f)

    # 初始化 provider 和工具
    from provider.factory import create_provider
    provider = create_provider(user_config, core_config)

    from run.prompt_cache import build_cached_system_prompt
    system_prompt = build_cached_system_prompt(root, user_dir)
    from run.tool import load_tool_schemas, ToolRunner
    tools = load_tool_schemas()
    tool_runner = ToolRunner(core_config, user_config, user_dir=user_dir)

    # 初始化对话
    from run.chat import ChatManager
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_provider(provider)
    chat.set_system_prompt(system_prompt)

    import skills.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    try:
        chat.load_history()
    except Exception:
        pass

    # 执行一轮对话
    from run.engine import run_chat_turn
    chat.add_user_message(prompt)
    tool_runner.reset_count()

    for event in run_chat_turn(chat, tool_runner, provider, tools):
        if event["type"] == "tool_call":
            print(f"  {event['line']}")
        elif event["type"] in ("text_chunk",):
            print(event["content"], end="", flush=True)
        elif event["type"] == "text_done":
            print()
        elif event["type"] == "text":
            print(f"助手: {event['content']}")
        elif event["type"] == "error":
            print(f"\n[Provider 错误: {event['content']}]")
        elif event["type"] == "deadlock_warning":
            print("  ⚠ 同命令连败 3 次，已提示 LLM 换思路")
        elif event["type"] == "max_rounds":
            print("[已达到工具调用上限]")

    # 保存
    from run.summarize import summarize_and_store
    summarize_and_store(provider, chat.messages, user_dir)
    chat.save_history()
    chat.save_log(chat.build_messages())


if __name__ == "__main__":
    if "--web" in sys.argv:
        main_web()
    elif "--once" in sys.argv:
        user_name = None
        prompt = None
        for i, arg in enumerate(sys.argv):
            if arg == "--user" and i + 1 < len(sys.argv):
                user_name = sys.argv[i + 1]
            elif arg == "--prompt" and i + 1 < len(sys.argv):
                prompt = sys.argv[i + 1]
        if not user_name or not prompt:
            print("错误: --once 需要 --user <name> 和 --prompt <text>")
            sys.exit(1)
        main_once(user_name, prompt)
    else:
        main_cli()
