# -*- mode: python ; coding: utf-8 -*-
"""votx-agent PyInstaller spec — Web UI + CLI 双模式"""
import os
from pathlib import Path

_root = Path(__file__).parent  # spec 文件所在即项目根

# ── 收集数据目录 ──
def _collect_tree(rel: str) -> list[tuple[str, str]]:
    """返回 [(src_abs, dest_rel), ...] 保持目录结构"""
    src = _root / rel
    if not src.is_dir():
        return []
    result = []
    for f in src.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts and ".pyc" not in f.suffix:
            result.append((str(f), str(f.relative_to(_root))))
    return result

# 数据文件：（源路径, 目标相对路径）
datas = []
datas.extend(_collect_tree("web/templates"))
datas.extend(_collect_tree("config"))
datas.extend(_collect_tree("skills"))
datas.append((str(_root / "paths.py"), "paths.py"))
datas.append((str(_root / "AGENTS.md"), "AGENTS.md"))

# ── 隐藏导入（动态 importlib / __import__ 加载的模块） ──
hiddenimports = [
    # Skill tool.py 动态依赖
    "skills._common",
    # 可选工具包
    "yaml",
    "docx",
    "yt_dlp",
    "tavily",
    "PIL",
    "pypdf",
    "reportlab",
    "pdfplumber",
    # Web 框架内部
    "flask",
    "flask.app",
    "openai",
    "anthropic",
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
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="votx-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_root / "votx-agent.png") if (_root / "votx-agent.png").is_file() else None,
)
