"""votx-agent Web UI"""
import os as _os
import sys as _sys

# 确保项目根在 path（用于 web 模块被直接导入的场景）
_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _root not in _sys.path:
    _sys.path.insert(0, _root)
