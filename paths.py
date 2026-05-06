"""路径解析 — dev / PyInstaller --onedir / --onefile 通用"""
import os
import sys


def get_project_root() -> str:
    """项目根目录，三种运行模式通用"""
    if getattr(sys, "frozen", False):
        # 无论 --onefile 还是 --onedir，如果是外部框架暴露模型，
        # 我们总是希望获取 exe 所在的最外层目录，因为 config/web 在 exe 旁边
        # 在 pyinstaller 6 中，_MEIPASS 可能是 _internal 文件夹
        # sys.executable 就是 votx-agent.exe，所在目录正好是 dist/votx-agent/
        return os.path.dirname(sys.executable)
    # 开发模式：本文件就在项目根
    return os.path.dirname(os.path.abspath(__file__))
