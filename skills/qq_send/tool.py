"""通用消息发送工具 — 通过 PushQueue 异步投递到 QQ/Telegram"""
from run.tool import register_tool
from skills._common import err as _err


def _load_push_queue_dir() -> str:
    try:
        from paths import get_project_root
        from message.config import load_config

        root = get_project_root()
        # Keep skill pushes aligned with the router runtime: env override,
        # config.local.json, then config.json.
        cfg = load_config(root)
        return cfg.get("push", {}).get("queue_dir", "message/push_queue")
    except Exception:
        pass
    return "message/push_queue"


def send_qq_message(target: str, chat_type: str, message: str, platform: str = "onebot") -> str:
    """向 QQ 或 Telegram 发送文本消息"""
    if not target or not str(target).strip():
        return _err("target 不能为空（QQ 号 / TG 用户 ID / 群号）")
    if not message or not message.strip():
        return _err("message 不能为空")
    if chat_type not in ("private", "group"):
        return _err(f"chat_type 必须为 private 或 group，实际: {chat_type}")
    if platform not in ("onebot", "telegram"):
        return _err(f"platform 必须为 onebot 或 telegram，实际: {platform}")

    try:
        from paths import get_project_root
        from message.push_queue import enqueue_message

        root = get_project_root()
        queue_dir = _load_push_queue_dir()

        task_id = enqueue_message(
            root=root,
            queue_dir=queue_dir,
            platform=platform,
            chat_type=chat_type,
            chat_id=str(target).strip(),
            message=message.strip(),
        )
        platform_name = "QQ" if platform == "onebot" else "Telegram"
        return f"OK: 消息已入队，ID: {task_id}\n平台: {platform_name}\n目标: {target} ({chat_type})"
    except Exception as e:
        return _err(f"发送失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "send_qq_message",
        "description": "向 QQ（OneBot）或 Telegram 发送文本消息。消息通过异步队列发送，支持私聊和群聊。",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "目标 ID：QQ 号 / TG 用户 ID / 群号"},
                "chat_type": {"type": "string", "description": "private（私聊）或 group（群聊）"},
                "message": {"type": "string", "description": "要发送的文本内容"},
                "platform": {"type": "string", "description": "平台: onebot（QQ，默认）或 telegram"},
            },
            "required": ["target", "chat_type", "message"],
        },
    },
}


def register():
    register_tool(SCHEMA, send_qq_message)
