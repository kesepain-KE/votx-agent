"""votx-agent Python 入口命令 — 用法: python votx.py [web|cli|help]"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def exec_python(script: str, args: list[str]):
    """用当前 Python 解释器启动目标入口。"""
    script_path = os.path.join(ROOT, script)
    argv = [sys.executable, script_path, *args]
    os.execv(sys.executable, argv)


def show_help():
    """处理 show_help 相关逻辑。"""
    print("votx-agent 命令")
    print()
    print("用法: python votx.py [子命令]")
    print()
    print("子命令:")
    print("  (无参数)    默认启动 Web UI")
    print("  web        启动 Web UI (端口 1478)")
    print("  cli        启动终端对话模式")
    print("  help       显示此帮助")
    print()
    print("自定义端口:")
    print("  python votx.py web --port=8080")
    print()
    print("更多信息: https://github.com/kesepain-KE/votx-agent")


def main():
    """执行命令行入口流程。"""
    argv = sys.argv[1:]
    cmd = argv[0] if argv else ""

    if cmd in ("help", "-h", "--help"):
        show_help()
        return

    if cmd == "cli":
        exec_python("start.py", argv[1:])
    elif cmd in ("web", ""):
        if not cmd:
            exec_python("start_web.py", argv)
        else:
            exec_python("start_web.py", argv[1:])
    else:
        print(f"未知子命令: {cmd}")
        print("请使用 'votx help' 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()
