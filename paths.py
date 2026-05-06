"""路径解析 — dev / PyInstaller --onedir / --onefile 通用"""
import os
import sys


def get_project_root() -> str:
    """项目根目录，三种运行模式通用"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包：_MEIPASS 仅 --onefile 有值，--onedir 用 exe 所在目录
        if hasattr(sys, "_MEIPASS") and sys._MEIPASS:
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    # 开发模式：本文件就在项目根
    return os.path.dirname(os.path.abspath(__file__))
