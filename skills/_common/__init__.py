"""skills 用户技能公共模块 — err / safe_path / check_sandbox / log_tool_call

与 plugins._common 分别维护。用户技能 tool.py 从本模块导入，
内置技能 tool.py 从 plugins._common 导入。
"""
import json
import os
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path

from run.io_utils import append_jsonl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# skills/_common/__init__.py → skills/_common → skills → 项目根
_CURRENT_USER_DIR: ContextVar[str | None] = ContextVar("votx_current_user_dir_skills", default=None)


def err(msg: str) -> str:
    """返回标准错误格式。"""
    return f"ERROR: {msg}"


def truncate(text: str, max_len: int = 0) -> str:
    """截断文本到指定长度。max_len=0 表示不限制。"""
    if max_len > 0 and len(text) > max_len:
        return text[:max_len] + f"\n... (截断，共 {len(text)} 字符)"
    return text


def set_current_user_dir(user_dir: str | None) -> Token:
    """绑定当前工具执行上下文的用户目录。"""
    return _CURRENT_USER_DIR.set(user_dir)


def reset_current_user_dir(token: Token):
    """恢复 ContextVar 到上一个值。"""
    _CURRENT_USER_DIR.reset(token)


def get_current_user_dir() -> str:
    """优先返回当前工具上下文中的用户目录，兼容 VOTX_USER_DIR 环境变量。"""
    return _CURRENT_USER_DIR.get() or os.environ.get("VOTX_USER_DIR", "")


# ---- 路径安全 ----

def safe_path(raw_path: str) -> Path | None:
    """解析路径。相对路径以项目根为基准。"""
    try:
        p = Path(raw_path)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return p.resolve()
    except Exception:
        return None


def check_sandbox(p: Path, allowed_roots: list | None = None) -> Path | None:
    """检查路径是否在允许的根目录内。返回 resolved Path 或 None。

    默认允许项目根目录和当前用户目录。
    """
    try:
        resolved = p.resolve()
    except Exception:
        return None
    roots = [Path(x) for x in (allowed_roots or []) if x]
    if not roots:
        roots.append(_PROJECT_ROOT)
        user_dir = get_current_user_dir()
        if user_dir:
            roots.append(Path(user_dir))
    for root in roots:
        try:
            resolved_root = root.resolve()
        except Exception:
            continue
        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
            return resolved
    return None


# ---- 工具日志 ----

def _log_path(user_dir: str | None = None) -> str | None:
    """获取工具日志文件路径。"""
    user_dir = user_dir or get_current_user_dir()
    if not user_dir:
        return None
    log_dir = os.path.join(user_dir, "history", "log")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "tool_log.jsonl")


_TOOL_LOG_MAX_CACHE = None


def _get_tool_log_max() -> int:
    """读取 tool_log_max 配置。"""
    global _TOOL_LOG_MAX_CACHE
    if _TOOL_LOG_MAX_CACHE is not None:
        return _TOOL_LOG_MAX_CACHE
    try:
        config_path = _PROJECT_ROOT / "config" / "config_core.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            _TOOL_LOG_MAX_CACHE = config.get("tool", {}).get("tool_log_max", 1000)
        else:
            _TOOL_LOG_MAX_CACHE = 1000
    except Exception:
        _TOOL_LOG_MAX_CACHE = 1000
    return _TOOL_LOG_MAX_CACHE


def log_tool_call(name: str, args: dict, result: str, success: bool, elapsed: float,
                  user_dir: str | None = None, tool_call_id: str = "") -> str:
    """记录工具调用到 tool_log.jsonl。返回生成的 log_id。"""
    path = _log_path(user_dir)
    if not path:
        return ""
    _sensitive_keys = {"api_key", "key", "token", "secret", "password", "authorization", "auth"}
    safe_args = {}
    for k, v in args.items():
        kl = k.lower()
        if any(s in kl for s in _sensitive_keys):
            safe_args[k] = "***"
        elif isinstance(v, str) and len(v) > 200:
            safe_args[k] = v[:200] + "..."
        else:
            safe_args[k] = v
    safe_result = result
    for s in _sensitive_keys:
        if s in result.lower():
            safe_result = result[:2000]
            break
    else:
        safe_result = result[:2000]
    log_id = uuid.uuid4().hex[:8]
    entry = {
        "id": log_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": name,
        "args": safe_args,
        "result": safe_result,
        "success": success,
        "elapsed": round(elapsed, 3),
    }
    if tool_call_id:
        entry["tool_call_id"] = tool_call_id
    try:
        append_jsonl(path, entry)
    except Exception:
        pass

    max_lines = _get_tool_log_max()
    try:
        with open(path, "r+", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                f.seek(0)
                f.truncate()
                f.writelines(lines[-max_lines:])
    except Exception:
        pass

    return log_id
