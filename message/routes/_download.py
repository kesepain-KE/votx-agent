"""Shared file download helper for message routers.

兼容说明:
- 旧函数 download_url() / save_base64_data() 保留，返回 str | None
- 新代码建议用 message.attachments.save_url_attachment() / save_base64_attachment()
  获取 AttachmentRecord（含类型/来源/路径等完整元数据）
- 保存目录已统一为 users/<user>/history/file（与 Web 上传同池）
"""
from __future__ import annotations

import asyncio
import base64
import os
import uuid
from pathlib import Path


def _user_file_dir(root: str, username: str) -> Path:
    """返回并确保 users/<username>/history/file 目录存在。"""
    p = Path(root) / "users" / username / "history" / "file"
    p.mkdir(parents=True, exist_ok=True)
    return p


# 兼容别名: 旧代码引用的 _user_download_dir
def _user_download_dir(root: str, username: str) -> Path:
    return _user_file_dir(root, username)


def _safe_filename(name: str, fallback_ext: str = "") -> str:
    """Sanitize filename: keep only safe chars, add UUID prefix to avoid collision."""
    safe = "".join(c for c in name if c.isalnum() or c in "._- ()（）").strip()
    if not safe:
        safe = f"file_{uuid.uuid4().hex[:6]}"
    # Ensure extension
    if fallback_ext and "." not in safe.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]:
        safe += fallback_ext
    return f"{uuid.uuid4().hex[:6]}_{safe}"


async def download_url(root: str, username: str, url: str, filename: str = "") -> str | None:
    """Download a file from URL to user's history/file directory. Returns local path or None.

    此函数保持向后兼容 (返回 str | None)。
    新代码如需结构化 AttachmentRecord，请用 message.attachments.save_url_attachment()。
    """
    from message.attachments import save_url_attachment

    record = await save_url_attachment(
        root=root, username=username, url=url,
        kind="file", platform="legacy", filename=filename,
    )
    return record["path"] if record else None


def save_base64_data(root: str, username: str, b64_data: str, filename: str = "") -> str | None:
    """Decode base64 data and save to user's history/file directory. Returns local path or None.

    此函数保持向后兼容 (返回 str | None)。
    新代码如需结构化 AttachmentRecord，请用 message.attachments.save_base64_attachment()。
    """
    from message.attachments import save_base64_attachment

    record = save_base64_attachment(
        root=root, username=username, b64_data=b64_data,
        kind="file", platform="legacy", filename=filename,
    )
    return record["path"] if record else None


def _ext_from_url(url: str) -> str:
    """Guess file extension from URL path."""
    path = url.split("?")[0].split("/")[-1]
    if "." in path:
        return os.path.splitext(path)[1]
    return ""
