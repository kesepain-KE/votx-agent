# -*- mode: python ; coding: utf-8 -*-
"""votx-agent Windows onedir 双入口：Web 与 CLI 共用一套运行时。"""
from pathlib import Path

_root = Path(SPECPATH)

hiddenimports = [
    "cron",
    "cron.scheduler",
    "cron.tasks",
    "cron.forget",
    "message",
    "message.runtime",
    "message.agent_service",
    "message.config",
    "message.identity",
    "message.permissions",
    "message.push_queue",
    "message.routes",
    "message.routes._download",
    "message.routes.onebot",
    "message.routes.telegram",
    "websockets",
    "provider.factory",
    "provider.votx_adapter",
    "provider.schema",
    "plugins._common",
    "yaml",
    "yt_dlp",
    "tavily",
    "PIL",
    "pdf2image",
    "flask",
    "flask.app",
    "werkzeug",
]

# Python 代码和依赖进入共享 _internal；可编辑框架资源由 build_windows.bat
# 复制到两个 EXE 同级目录，运行时统一通过 paths.get_project_root() 访问。
a = Analysis(
    [str(_root / "windows_entry.py")],
    pathex=[str(_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6", "PyQt6.*", "PySide6", "PySide6.*", "PyQt5", "PyQt5.*", "PySide2", "PySide2.*"],
    noarchive=False,
)

pyz = PYZ(a.pure)

_common_exe = dict(
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_root / "votx-agent.png") if (_root / "votx-agent.png").is_file() else None,
)

web_exe = EXE(pyz, a.scripts, [], name="votx-agent-web", **_common_exe)
cli_exe = EXE(pyz, a.scripts, [], name="votx-agent-cli", **_common_exe)

coll = COLLECT(
    web_exe,
    cli_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="votx-agent",
)
