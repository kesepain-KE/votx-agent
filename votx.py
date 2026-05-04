#!/usr/bin/env python3
"""votx-agent 入口命令 — 用法: votx [web|cli|help]"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def show_help():
    print("votx-agent 命令")
    print()
    print("用法: votx [子命令]")
    print()
    print("子命令:")
    print("  (无参数)    默认启动 Web UI")
    print("  web        启动 Web UI (端口 1478)")
    print("  cli        启动终端对话模式")
    print("  help       显示此帮助")
    print()
    print("自定义端口:")
    print("  votx web --port=8080")
    print()
    print("更多信息: https://github.com/kesepain-KE/votx-agent")


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else ""

    if cmd in ("help", "-h", "--help"):
        show_help()
        return

    if cmd == "cli":
        subprocess.run([sys.executable, os.path.join(ROOT, "start.py")] + argv[1:])
    elif cmd in ("web", ""):
        if not cmd:
            subprocess.run([sys.executable, os.path.join(ROOT, "start_web.py")] + argv)
        else:
            subprocess.run([sys.executable, os.path.join(ROOT, "start_web.py")] + argv[1:])
    else:
        print(f"未知子命令: {cmd}")
        print("请使用 'votx help' 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()
