"""统一附件模块 — 外部消息路由 (OneBot/Telegram) 附件接收的统一入口。

职责：
- 定义 AttachmentRecord 结构化记录
- 保存到统一目录 users/<user>/history/file（与 Web 上传同池，右侧文件栏可见）
- prompt 格式化：format_external_message()
- 附件日志：external_attachments.jsonl
"""
from __future__ import annotations

import asyncio
import base64
import os
import shutil
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


# ── AttachmentRecord ──

class AttachmentRecord(TypedDict):
    """外部消息附件结构化记录"""
    kind: str          # "image" | "audio" | "voice" | "video" | "file"
    path: str          # 绝对路径
    rel_path: str      # 相对路径 (users/<user>/history/file/xxx.jpg)
    name: str          # 文件名
    size: int          # 字节数
    mime: str          # MIME 类型 (如 "image/jpeg")
    platform: str      # "onebot" | "telegram"
    message_id: str    # 平台消息 ID
    source_id: str     # 发送者 ID (QQ号 / Telegram user_id)


# ── 附件类型 → MIME 映射 ──

_KIND_MIME: dict[str, str] = {
    "image": "image/jpeg",
    "audio": "audio/mpeg",
    "voice": "audio/ogg",
    "video": "video/mp4",
    "file": "application/octet-stream",
}

# 附件类型 → 轻提示
_KIND_HINT: dict[str, str] = {
    "image": "如需识别图片内容，请调用 vision_analyze",
    "audio": "如需转写音频内容，请调用 audio_transcribe",
    "voice": "如需转写语音内容，请调用 audio_transcribe",
    "video": "如需分析视频内容，可先用 ffmpeg 提取帧再调用 vision_analyze",
    "file": "如需读取文件内容，请调用 read_file 或 markdown_converter",
}


# ── 内部辅助 ──

def _user_file_dir(root: str, username: str) -> Path:
    """返回并确保 users/<username>/history/file 目录存在。"""
    p = Path(root) / "users" / username / "history" / "file"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_filename(name: str, fallback_ext: str = "", add_uuid_prefix: bool = True) -> str:
    """清洗文件名：仅保留安全字符，可选 UUID 前缀防冲突。

    add_uuid_prefix=False 时只清洗不添加前缀，适合本地文件复制场景，
    此时冲突由调用方的 _unique_dest() 处理，产生 PID.py → PID_1.py 行为。
    """
    safe = "".join(c for c in name if c.isalnum() or c in "._- ()（）").strip()
    if not safe:
        safe = f"file_{uuid.uuid4().hex[:6]}"
    if fallback_ext and "." not in safe.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]:
        safe += fallback_ext
    if add_uuid_prefix:
        return f"{uuid.uuid4().hex[:6]}_{safe}"
    return safe


def _ext_from_url(url: str) -> str:
    """从 URL 路径提取扩展名。"""
    path = url.split("?")[0].split("/")[-1]
    if "." in path:
        return os.path.splitext(path)[1]
    return ""


def _guess_mime(kind: str, name: str = "") -> str:
    """根据 kind 和文件名推测 MIME 类型。"""
    ext = os.path.splitext(name)[1].lower() if name else ""
    ext_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
        ".opus": "audio/opus", ".aac": "audio/aac", ".flac": "audio/flac",
        ".mp4": "video/mp4", ".webm": "video/webm", ".avi": "video/x-msvideo",
        ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain", ".json": "application/json",
    }
    if ext in ext_map:
        return ext_map[ext]
    return _KIND_MIME.get(kind, "application/octet-stream")


def _make_record(
    root: str,
    username: str,
    dest: Path,
    kind: str,
    platform: str,
    message_id: str = "",
    source_id: str = "",
    original_name: str = "",
) -> AttachmentRecord:
    """从文件路径构建 AttachmentRecord。"""
    name = dest.name
    size = dest.stat().st_size if dest.exists() else 0
    abs_path = str(dest.resolve())
    rel_path = os.path.join("users", username, "history", "file", name).replace("\\", "/")
    return AttachmentRecord(
        kind=kind,
        path=abs_path,
        rel_path=rel_path,
        name=name,
        size=size,
        mime=_guess_mime(kind, original_name or name),
        platform=platform,
        message_id=str(message_id),
        source_id=str(source_id),
    )


# ── 公开 API ──

def _get_proxy_handler(proxy: str = ""):
    """构建 urllib ProxyHandler。

    优先级：
    1. 传入的 proxy 字符串（如 "http://127.0.0.1:7890"）
    2. 环境变量 HTTPS_PROXY / https_proxy / HTTP_PROXY / http_proxy
    返回 ProxyHandler 或 None（无代理）。
    """
    if not proxy:
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            proxy = os.environ.get(key, "")
            if proxy:
                break
    if not proxy:
        return None
    return urllib.request.ProxyHandler({"http": proxy, "https": proxy})


async def save_url_attachment(
    root: str,
    username: str,
    url: str,
    kind: str = "file",
    platform: str = "unknown",
    message_id: str = "",
    source_id: str = "",
    filename: str = "",
    proxy: str = "",
) -> AttachmentRecord | None:
    """从 URL 下载附件并保存到 users/<user>/history/file，返回 AttachmentRecord。

    proxy 可选：传入代理地址（如 "http://127.0.0.1:7890"），或通过环境变量
    HTTPS_PROXY/http_proxy 自动检测。 Telegram 等需要代理的网络可传入。
    """
    # attach 下载

    dest_dir = _user_file_dir(root, username)
    ext = _ext_from_url(url)
    dest_name = _safe_filename(filename, ext) if filename else f"{uuid.uuid4().hex[:8]}{ext}"
    dest = dest_dir / dest_name

    MAX_SIZE = 100 * 1024 * 1024  # 100 MB
    _proxy_handler = _get_proxy_handler(proxy)

    def _dl():
        class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)

        try:
            handlers = [_SafeRedirectHandler()]
            if _proxy_handler:
                handlers.append(_proxy_handler)
            opener = urllib.request.build_opener(*handlers)
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "votx-agent/1.0")
            with opener.open(req, timeout=60) as resp:
                cl = resp.headers.get("Content-Length")
                if cl:
                    try:
                        if int(cl) > MAX_SIZE:
                            print(f"[attachments] 文件过大 {url}: {cl} bytes")
                            return None
                    except ValueError:
                        pass
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
                            print(f"[attachments] 下载超出大小限制 {url}")
                            return None
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"[attachments] URL 下载失败 {url}: {e}")
            # 清理部分下载的残留文件
            try:
                if dest.exists():
                    os.remove(dest)
            except OSError:
                pass
            return None

    ok = await asyncio.to_thread(_dl)
    if not ok:
        return None

    record = _make_record(root, username, dest, kind, platform, message_id, source_id, filename)
    # 自动写日志（日志写入失败不影响附件保存）
    try:
        _log_attachment(record, root, username)
    except Exception as e:
        print(f"[attachments] 日志写入失败: {e}")
    return record


def save_base64_attachment(
    root: str,
    username: str,
    b64_data: str,
    kind: str = "file",
    platform: str = "unknown",
    message_id: str = "",
    source_id: str = "",
    filename: str = "",
) -> AttachmentRecord | None:
    """解码 base64 数据并保存到 users/<user>/history/file，返回 AttachmentRecord。"""
    MAX_BASE64_LEN = 140 * 1024 * 1024
    if len(b64_data) > MAX_BASE64_LEN:
        print(f"[attachments] base64 数据过大: {len(b64_data)} 字符")
        return None

    dest_dir = _user_file_dir(root, username)
    dest_name = _safe_filename(filename) if filename else f"{uuid.uuid4().hex[:8]}.bin"
    dest = dest_dir / dest_name

    try:
        data = base64.b64decode(b64_data)
        MAX_SIZE = 100 * 1024 * 1024  # 100 MB
        if len(data) > MAX_SIZE:
            print(f"[attachments] base64 解码后过大: {len(data)} bytes")
            return None
        dest.write_bytes(data)
    except Exception as e:
        print(f"[attachments] base64 保存失败: {e}")
        return None

    record = _make_record(root, username, dest, kind, platform, message_id, source_id, filename)
    try:
        _log_attachment(record, root, username)
    except Exception as e:
        print(f"[attachments] 日志写入失败: {e}")
    return record


def _resolve_local_path(source_path: str) -> str | None:
    """返回可直接读取的本地文件路径。"""
    if os.path.exists(source_path):
        return source_path
    return None


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    """在 dest_dir 下生成不冲突的文件名（PID.py → PID_1.py → PID_2.py ...）。"""
    base, ext = os.path.splitext(filename)
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        new_name = f"{base}_{n}{ext}"
        candidate = dest_dir / new_name
        if not candidate.exists():
            return candidate
        n += 1


def save_local_attachment(
    root: str,
    username: str,
    source_path: str,
    kind: str = "file",
    platform: str = "onebot",
    message_id: str = "",
    source_id: str = "",
    filename: str = "",
) -> AttachmentRecord | None:
    """保存本地文件到 users/<user>/history/file，返回 AttachmentRecord。"""
    resolved = _resolve_local_path(source_path)
    if not resolved:
        print(f"[attachments] 无法解析文件路径: {source_path}")
        return None

    dest_dir = _user_file_dir(root, username)
    if filename:
        dest_name = _safe_filename(filename, add_uuid_prefix=False)
    else:
        dest_name = _safe_filename(os.path.basename(resolved), add_uuid_prefix=False)
    dest = _unique_dest(dest_dir, dest_name)

    try:
        shutil.copy2(resolved, dest)
    except Exception as e:
        print(f"[attachments] 文件复制失败 {resolved} → {dest}: {e}")
        return None

    record = _make_record(root, username, dest, kind, platform, message_id, source_id, filename or os.path.basename(resolved))
    try:
        _log_attachment(record, root, username)
    except Exception as e:
        print(f"[attachments] 日志写入失败: {e}")
    return record


# ── Prompt 格式化 ──

def format_external_message(
    text: str,
    attachments: list[AttachmentRecord],
    source: dict | None = None,
) -> str:
    r"""将外部消息文本 + 附件 + 来源组装为结构化 Agent prompt。

    输出格式:
        [外部消息附件]
        - image: /root/.../users/<user>/history/file/xxx.jpg （如需识别，请调用 vision_analyze）
        - voice: /root/.../users/<user>/history/file/yyy.ogg （如需转写语音内容，请调用 audio_transcribe）

        用户消息:
        用户文本
    """
    parts: list[str] = []

    if source:
        platform = source.get("platform", "")
        chat_type = source.get("chat_type", "")
        chat_id = source.get("chat_id", "")
        message_id = source.get("message_id", "")
        parts.append(f"[来自 {platform} {chat_type} chat_id={chat_id} message_id={message_id}]")
        parts.append("")

    # 附件块
    if attachments:
        parts.append("[外部消息附件]")
        for a in attachments:
            kind = a.get("kind", "file")
            hint = _KIND_HINT.get(kind, "")
            hint_text = f" （{hint}）" if hint else ""
            parts.append(f"- {kind}: {a['path']}{hint_text}")
        parts.append("")

    # 用户消息
    parts.append("用户消息:")
    parts.append(text.strip() if text and text.strip() else "（无文本）")

    return "\n".join(parts)


# ── 附件日志 ──

def _log_attachment(record: AttachmentRecord, root: str, username: str):
    """将附件记录写入 users/<user>/history/log/external_attachments.jsonl。"""
    from run.io_utils import append_jsonl

    log_dir = Path(root) / "users" / username / "history" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "external_attachments.jsonl"

    entry = {
        "platform": record["platform"],
        "kind": record["kind"],
        "path": record["rel_path"],
        "original_name": record["name"],
        "size": record["size"],
        "mime": record["mime"],
        "message_id": record["message_id"],
        "source_id": record["source_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    append_jsonl(str(log_path), entry)


def log_attachment(record: AttachmentRecord, user_dir: str):
    """Public helper for writing an attachment record to a user's history log."""
    from run.io_utils import append_jsonl

    log_dir = Path(user_dir) / "history" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "external_attachments.jsonl"
    entry = {
        "platform": record["platform"],
        "kind": record["kind"],
        "path": record["rel_path"],
        "original_name": record["name"],
        "size": record["size"],
        "mime": record["mime"],
        "message_id": record["message_id"],
        "source_id": record["source_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    append_jsonl(str(log_path), entry)
