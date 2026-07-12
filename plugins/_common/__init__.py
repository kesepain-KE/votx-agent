"""skills 公共模块 — err / safe_path / log_tool_call"""
import json
import os
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path

from run.io_utils import append_jsonl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CURRENT_USER_DIR: ContextVar[str | None] = ContextVar("votx_current_user_dir", default=None)

# 多模态上下文 — session 级 provider 注入（所有 multimodal plugin 共用）
_MULTIMODAL_CTX: ContextVar = ContextVar("multimodal_ctx", default=None)


def set_multimodal_context(provider, chat=None, user_name: str = ""):
    """注入当前会话的 provider 上下文。"""
    _MULTIMODAL_CTX.set({"provider": provider, "chat": chat, "user_name": user_name})


def get_multimodal_context() -> dict | None:
    """获取当前会话的 multimodal 上下文（provider/chat/user_name）。"""
    return _MULTIMODAL_CTX.get()


def err(msg: str) -> str:
    return f"ERROR: {msg}"


def truncate(text: str, max_len: int = 0) -> str:
    """截断文本到指定长度。max_len=0 表示不限制。"""
    if max_len > 0 and len(text) > max_len:
        return text[:max_len] + f"\n... (截断，共 {len(text)} 字符)"
    return text


def set_current_user_dir(user_dir: str | None) -> Token:
    return _CURRENT_USER_DIR.set(user_dir)


def reset_current_user_dir(token: Token):
    _CURRENT_USER_DIR.reset(token)


def get_current_user_dir() -> str:
    return _CURRENT_USER_DIR.get() or os.environ.get("VOTX_USER_DIR", "")


def _positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _read_tool_timeout_config(path: Path) -> int | None:
    try:
        if not path.exists():
            return None
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return None
        tool_cfg = config.get("tool", {})
        if not isinstance(tool_cfg, dict):
            return None
        return _positive_int(tool_cfg.get("tool_timeout"))
    except Exception:
        return None


def get_effective_tool_timeout(default: int = 300) -> int:
    """获取工具内部超时。"""
    fallback = _positive_int(default) or 300
    user_dir = get_current_user_dir()
    if user_dir:
        timeout = _read_tool_timeout_config(Path(user_dir) / "config.json")
        if timeout is not None:
            return timeout
    timeout = _read_tool_timeout_config(_PROJECT_ROOT / "config" / "config_core.json")
    if timeout is not None:
        return timeout
    return fallback


# ---- 路径解析（保留：相对路径 → 绝对路径兼容）----

def safe_path(raw_path: str) -> Path | None:
    """解析路径。相对路径以项目根为基准。"""
    try:
        p = Path(raw_path)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return p.resolve()
    except Exception:
        return None


# ---- 工具日志 ----

def _log_path(user_dir: str | None = None) -> str | None:
    user_dir = user_dir or get_current_user_dir()
    if not user_dir:
        return None
    log_dir = os.path.join(user_dir, "history", "log")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "tool_log.jsonl")


_TOOL_LOG_MAX_CACHE = None


def _get_tool_log_max() -> int:
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


def log_tool_call(name: str, args: dict, result: str, success: bool, elapsed: float, user_dir: str | None = None, tool_call_id: str = ""):
    """记录工具调用日志。返回生成的 log_id。"""
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
