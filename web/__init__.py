"""votx-agent Web UI"""
import sys as _sys

from paths import get_project_root

# 确保项目根在 path（dev / PyInstaller 通用）
_root = get_project_root()
if _root not in _sys.path:
    _sys.path.insert(0, _root)
