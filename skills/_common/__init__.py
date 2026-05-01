"""skills 公共模块 — err / truncate / safe_path / log_tool_call"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


MAX_OUTPUT = 8000


def err(msg: str) -> str:
    return f"ERROR: {msg}"


def truncate(text: str, max_len: int = MAX_OUTPUT) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n...[截断: 原始 {len(text)} 字符]"


def _allowed_roots() -> list[Path]:
    roots = []
    user_dir = os.environ.get("KESEPAIN_USER_DIR")
    if user_dir:
        try:
            roots.append(Path(user_dir).resolve())
        except Exception:
            pass
    try:
        roots.append(Path(__file__).resolve().parent.parent.parent)
    except Exception:
        pass
    return roots


def safe_path(raw_path: str) -> Path | None:
    try:
        p = Path(raw_path).resolve()
        for root in _allowed_roots():
            try:
                p.relative_to(root)
                return p
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _log_path() -> str | None:
    user_dir = os.environ.get("KESEPAIN_USER_DIR")
    if not user_dir:
        return None
    log_dir = os.path.join(user_dir, "history", "log")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "tool_log.json")


def log_tool_call(name: str, args: dict, result: str, success: bool, elapsed: float):
    path = _log_path()
    if not path:
        return
    # 过滤敏感参数
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
    # 结果也脱敏
    safe_result = result
    for s in _sensitive_keys:
        if s in result.lower():
            safe_result = result[:2000]
            break
    else:
        safe_result = result[:2000]
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": name,
        "args": safe_args,
        "result": safe_result,
        "success": success,
        "elapsed": round(elapsed, 3),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
