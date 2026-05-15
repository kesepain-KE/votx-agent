"""Shared file download helper for message routers."""
from __future__ import annotations

import asyncio
import base64
import os
import uuid
from pathlib import Path


def _user_download_dir(root: str, username: str) -> Path:
    p = Path(root) / "users" / username / "download"
    p.mkdir(parents=True, exist_ok=True)
    return p


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
    """Download a file from URL to user's download directory. Returns local path or None."""
    import urllib.request

    dest_dir = _user_download_dir(root, username)
    ext = _ext_from_url(url)
    dest_name = _safe_filename(filename, ext) if filename else f"{uuid.uuid4().hex[:8]}{ext}"
    dest = dest_dir / dest_name

    def _dl():
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "votx-agent/1.0")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
            return str(dest)
        except Exception as e:
            print(f"[download] URL 下载失败 {url}: {e}")
            return None

    return await asyncio.to_thread(_dl)


def save_base64_data(root: str, username: str, b64_data: str, filename: str = "") -> str | None:
    """Decode base64 data and save to user's download directory. Returns local path or None."""
    dest_dir = _user_download_dir(root, username)
    dest_name = _safe_filename(filename) if filename else f"{uuid.uuid4().hex[:8]}.bin"
    dest = dest_dir / dest_name

    try:
        data = base64.b64decode(b64_data)
        dest.write_bytes(data)
        print(f"[download] base64 保存成功: {dest}")
        return str(dest)
    except Exception as e:
        print(f"[download] base64 保存失败: {e}")
        return None


def _ext_from_url(url: str) -> str:
    """Guess file extension from URL path."""
    path = url.split("?")[0].split("/")[-1]
    if "." in path:
        return os.path.splitext(path)[1]
    return ""
