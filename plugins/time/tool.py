"""时间工具 — 获取当前 UTC/本地时间、可控延时"""
import time as _time
from datetime import datetime, timezone
from run.tool import register_tool
from plugins._common import err

MAX_SLEEP_SECONDS = 30 * 60


def get_time() -> str:
    """获取当前 UTC 和本地时间"""
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    utc_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    local_ts = now_local.strftime("%Y-%m-%dT%H:%M:%S")
    offset = now_local.strftime("%z") or "未知"
    return f"UTC: {utc_ts}\n本地: {local_ts} (UTC{offset})"


def sleep(seconds: float) -> str:
    """休眠指定秒数（上限 30 分钟），不受全局 tool_timeout 截断。"""
    try:
        s = float(seconds)
    except (ValueError, TypeError):
        return err(f"无效的秒数: {seconds}")
    if s <= 0:
        return err("秒数必须大于 0")
    if s > MAX_SLEEP_SECONDS:
        return err(f"单次休眠上限 {MAX_SLEEP_SECONDS} 秒（30 分钟）")
    _time.sleep(s)
    return f"OK: 已休眠 {s:.1f} 秒"


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前 UTC 和本地时间（含时区偏移）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep",
            "description": "休眠指定秒数（上限 30 分钟）。该工具不受全局 tool.tool_timeout 截断，但自身保留 1800 秒硬上限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "休眠秒数（1-1800）"},
                },
                "required": ["seconds"],
            },
        },
    },
]

HANDLERS = {"get_time": get_time, "sleep": sleep}


def register():
    """处理 register 相关逻辑。"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        meta = {"skip_tool_timeout": True} if name == "sleep" else None
        register_tool(s, HANDLERS[name], meta=meta)
