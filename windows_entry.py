"""PyInstaller Windows 双入口启动器。

同一套 onedir 运行时生成两个 EXE：
- votx-agent-web.exe -> start_web.py
- votx-agent-cli.exe -> start.py

实际入口文件位于 EXE 同级目录，便于随框架更新并保持路径一致。
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

from paths import get_project_root


def main() -> None:
    root = Path(get_project_root())
    exe_name = Path(sys.executable).stem.lower()
    entry = "start.py" if exe_name.endswith("-cli") else "start_web.py"
    entry_path = root / entry
    if not entry_path.is_file():
        raise SystemExit(f"ERROR: Windows 发布包缺少入口文件: {entry_path}")
    runpy.run_path(str(entry_path), run_name="__main__")


if __name__ == "__main__":
    main()
