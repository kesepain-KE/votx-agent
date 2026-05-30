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

    # SSRF 防护
    from plugins._common import validate_url as _validate_url
    err = _validate_url(url)
    if err:
        print(f"[download] URL 校验失败 {url}: {err}")
        return None

    dest_dir = _user_download_dir(root, username)
    ext = _ext_from_url(url)
    dest_name = _safe_filename(filename, ext) if filename else f"{uuid.uuid4().hex[:8]}{ext}"
    dest = dest_dir / dest_name

    MAX_SIZE = 100 * 1024 * 1024  # 100 MB

    def _dl():
        # 自定义 redirect handler：每次重定向前校验新地址
        class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                err = _validate_url(newurl)
                if err:
                    raise urllib.request.HTTPError(newurl, 403, f"重定向目标被拒绝: {err}", headers, None)
                return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)

        try:
            opener = urllib.request.build_opener(_SafeRedirectHandler())
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "votx-agent/1.0")
            with opener.open(req, timeout=60) as resp:
                # 检查 Content-Length 防止 OOM
                cl = resp.headers.get("Content-Length")
                if cl:
                    try:
                        if int(cl) > MAX_SIZE:
                            print(f"[download] 文件过大 {url}: {cl} bytes")
                            return None
                    except ValueError:
                        pass
                # 流式读取，分块写入
                with open(dest, "wb") as f:
                    total = 0
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_SIZE:
                            f.close()
                            try:
                                os.remove(dest)
                            except OSError:
                                pass
                            print(f"[download] 下载超出大小限制 {url}")
                            return None
                        f.write(chunk)
            return str(dest)
        except Exception as e:
            print(f"[download] URL 下载失败 {url}: {e}")
            return None

    return await asyncio.to_thread(_dl)


def save_base64_data(root: str, username: str, b64_data: str, filename: str = "") -> str | None:
    """Decode base64 data and save to user's download directory. Returns local path or None."""
    # 输入大小限制：base64 编码 ~1.37x，限制解码后最大 100 MB
    MAX_BASE64_LEN = 140 * 1024 * 1024  # ~140 MB base64 ≈ 100 MB decoded
    if len(b64_data) > MAX_BASE64_LEN:
        print(f"[download] base64 数据过大: {len(b64_data)} 字符")
        return None

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
