"""通用文件上传工具 — 通过 PushQueue 异步投递到 QQ/Telegram"""
from pathlib import Path

from run.tool import register_tool
from skills._common import err as _err, safe_path, check_sandbox, get_current_user_dir


def _load_push_queue_dir() -> str:
    try:
        from paths import get_project_root
        from message.config import load_config

        root = get_project_root()
        # Match the router's config resolution so Docker's VOTX_MESSAGE_CONFIG
        # and local config.local.json both affect outbound file pushes.
        cfg = load_config(root)
        return cfg.get("push", {}).get("queue_dir", "message/push_queue")
    except Exception:
        pass
    return "message/push_queue"


def upload_qq_file(target: str, chat_type: str, file_path: str, platform: str = "onebot") -> str:
    """向 QQ 或 Telegram 上传文件"""
    if not target or not str(target).strip():
        return _err("target 不能为空（QQ 号 / TG 用户 ID / 群号）")
    if not file_path or not file_path.strip():
        return _err("file_path 不能为空")
    if chat_type not in ("private", "group"):
        return _err(f"chat_type 必须为 private 或 group，实际: {chat_type}")
    if platform not in ("onebot", "telegram"):
        return _err(f"platform 必须为 onebot 或 telegram，实际: {platform}")

    # 路径安全校验
    resolved = safe_path(file_path)
    if resolved is None:
        return _err(f"无效的文件路径: {file_path}")
    if not resolved.is_file():
        return _err(f"文件不存在: {resolved}")

    # 沙箱校验：允许项目根和用户目录
    from paths import get_project_root
    allowed_roots = [get_project_root()]
    user_dir = get_current_user_dir()
    if user_dir:
        allowed_roots.append(user_dir)
    if check_sandbox(resolved, allowed_roots) is None:
        return _err(f"文件路径越权: {resolved}（不在允许的目录内）")

    try:
        from message.push_queue import enqueue_file

        root = get_project_root()
        queue_dir = _load_push_queue_dir()

        task_id = enqueue_file(
            root=root,
            queue_dir=queue_dir,
            platform=platform,
            chat_type=chat_type,
            chat_id=str(target).strip(),
            file_path=str(resolved),
            name=resolved.name,
        )
        platform_name = "QQ" if platform == "onebot" else "Telegram"
        return f"OK: 文件上传任务已入队，ID: {task_id}\n平台: {platform_name}\n文件: {resolved}\n目标: {target} ({chat_type})"
    except Exception as e:
        return _err(f"上传失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "upload_qq_file",
        "description": "向 QQ（OneBot）或 Telegram 上传文件。文件通过异步队列发送，支持私聊和群聊。",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "目标 ID：QQ 号 / TG 用户 ID / 群号"},
                "chat_type": {"type": "string", "description": "private（私聊）或 group（群聊）"},
                "file_path": {"type": "string", "description": "要上传的本地文件绝对路径"},
                "platform": {"type": "string", "description": "平台: onebot（QQ，默认）或 telegram"},
            },
            "required": ["target", "chat_type", "file_path"],
        },
    },
}


def register():
    register_tool(SCHEMA, upload_qq_file)
