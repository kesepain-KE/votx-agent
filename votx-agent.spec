# -*- mode: python ; coding: utf-8 -*-
"""votx-agent PyInstaller spec — Web UI + CLI 双模式"""
import os
from pathlib import Path

_root = Path(SPECPATH)  # spec 文件所在即项目根

# ── 收集数据目录 ──
def _collect_tree(rel: str) -> list[tuple[str, str]]:
    """返回 [(src_abs, dest_rel), ...] 保持目录结构"""
    src = _root / rel
    if not src.is_dir():
        return []
    result = []
    for f in src.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts and "node_modules" not in f.parts and ".pyc" not in f.suffix:
            result.append((str(f), str(f.relative_to(_root))))
    return result

# 数据文件：（源路径, 目标相对路径）
datas = []
for d in ["web", "config", "skills", "plugins", "provider", "run", "cron", "agents", "message", "knowledge"]:
    datas.extend(_collect_tree(d))
datas.append((str(_root / "paths.py"), "paths.py"))
datas.append((str(_root / "AGENTS.md"), "AGENTS.md"))
datas.append((str(_root / ".env.example"), ".env.example"))
datas.append((str(_root / "version.json"), "version.json"))

# ── 隐藏导入（动态 importlib / __import__ 加载的模块） ──
hiddenimports = [
    # 调度器
    "cron",
    "cron.scheduler",
    "cron.tasks",
    "cron.forget",
    # 外部消息路由
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
    # Provider — Kemo LLM Adapter（唯一活跃 provider）
    "provider.factory",
    "provider.kemo_adapter",
    "provider.schema",
    # Skill tool.py 公共依赖
    "plugins._common",
    # 内置工具依赖（部分工具通过动态加载发现）
    "yaml",
    "yt_dlp",
    "tavily",
    "PIL",
    "pdf2image",
    # Web 框架内部
    "flask",
    "flask.app",
    "werkzeug",
]

a = Analysis(
    ["start_web.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6", "PyQt6.*", "PySide6", "PySide6.*", "PyQt5", "PyQt5.*", "PySide2", "PySide2.*"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="votx-agent",
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="votx-agent",
)
