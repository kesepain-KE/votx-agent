"""通用下载编排器 — 直链下载、视频下载、下载记录。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlparse
import urllib.request

from run.io_utils import append_jsonl, decode_subprocess_output, utf8_subprocess_env
from run.tool import register_tool
from plugins._common import err, get_current_user_dir, get_effective_tool_timeout
from plugins._common.artifacts import make_file_artifact, make_tool_result

_MAX_DIRECT_BYTES = 0  # 0 = 不限制
_DEFAULT_YTDLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


_DIRECT_TIMEOUT_DEFAULT = _env_int("DOWNLOAD_TIMEOUT", 30)
_VIDEO_TIMEOUT_DEFAULT = _env_int("DOWNLOAD_VIDEO_TIMEOUT", 600)


def _direct_timeout() -> int:
    return get_effective_tool_timeout(_DIRECT_TIMEOUT_DEFAULT)


def _video_timeout() -> int:
    return get_effective_tool_timeout(_VIDEO_TIMEOUT_DEFAULT)


def _default_download_dir(kind: str = "download") -> Path:
    user_dir = get_current_user_dir()
    if user_dir:
        base = Path(user_dir)
        if kind == "file":
            return base / "history" / "file"
        return base / "download"
    return Path(__file__).resolve().parent.parent.parent / "tmp" / "download"


def _resolve_output_dir(output_dir: str = "", save_to: str = "download") -> Path:
    """解析输出目录。"""
    raw = output_dir.strip() if output_dir else ""
    if not raw:
        return _default_download_dir(save_to)
    return Path(raw).expanduser().resolve()


def _safe_filename(name: str, fallback: str = "download") -> str:
    """清理文件名，避免非法字符。"""
    name = unquote(name or "").strip().replace("\\", "/")
    name = os.path.basename(name)
    name = _UNSAFE_FILENAME_RE.sub("_", name)
    name = name.strip(" .")
    if not name:
        name = fallback
    return name[:180]


def _filename_from_headers(url: str, headers) -> str:
    """从响应头或 URL 推断文件名。"""
    cd = headers.get("Content-Disposition", "") if headers else ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I)
    if match:
        return _safe_filename(match.group(1))
    match = re.search(r'filename="?([^";]+)"?', cd, re.I)
    if match:
        return _safe_filename(match.group(1))
    path_name = Path(urlparse(url).path).name
    return _safe_filename(path_name, "download")


def _unique_path(path: Path, overwrite: bool = False) -> Path:
    """目标文件存在时生成不冲突路径。"""
    if overwrite or not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(1, 1000):
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"无法生成不冲突文件名: {path}")


def _check_dependency(name: str) -> str | None:
    if shutil.which(name):
        return None
    return f"未找到 {name}，请先安装后再试"


def _download_log_path() -> Path:
    return _default_download_dir("download") / "download_manifest.jsonl"


def _write_manifest(entry: dict):
    try:
        append_jsonl(_download_log_path(), entry)
    except Exception:
        pass


def inspect_download_url(url: str) -> str:
    """检查下载链接的元信息。"""
    url = (url or "").strip()
    if not url:
        return err("URL 为空")

    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "votx-agent/1.0")
    try:
        with urllib.request.urlopen(req, timeout=_direct_timeout()) as resp:
            headers = resp.headers
            filename = _filename_from_headers(resp.geturl(), headers)
            return (
                f"URL: {resp.geturl()}\n"
                f"Status: {getattr(resp, 'status', 200)}\n"
                f"Filename: {filename}\n"
                f"Content-Type: {headers.get('Content-Type', '')}\n"
                f"Content-Length: {headers.get('Content-Length', 'unknown')}\n"
                f"Accept-Ranges: {headers.get('Accept-Ranges', '')}\n"
                f"Content-Disposition: {headers.get('Content-Disposition', '')}"
            )
    except urllib.error.HTTPError as e:
        if e.code in (403, 405):
            return _inspect_with_range_get(url)
        return err(f"检查失败: HTTP {e.code} {e.reason}")
    except Exception as e:
        return err(f"检查失败: {e}")


def _inspect_with_range_get(url: str) -> str:
    """HEAD 不可用时用 Range GET 探测。"""
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "votx-agent/1.0")
    req.add_header("Range", "bytes=0-0")
    try:
        with urllib.request.urlopen(req, timeout=_direct_timeout()) as resp:
            headers = resp.headers
            filename = _filename_from_headers(resp.geturl(), headers)
            return (
                f"URL: {resp.geturl()}\n"
                f"Status: {getattr(resp, 'status', 200)}\n"
                f"Filename: {filename}\n"
                f"Content-Type: {headers.get('Content-Type', '')}\n"
                f"Content-Length: {headers.get('Content-Length', headers.get('Content-Range', 'unknown'))}\n"
                f"Accept-Ranges: {headers.get('Accept-Ranges', '')}\n"
                f"Content-Disposition: {headers.get('Content-Disposition', '')}"
            )
    except Exception as e:
        return err(f"检查失败: {e}")


def download_direct_file(
    url: str,
    output_dir: str = "",
    filename: str = "",
    overwrite: bool = False,
    headers: str = "",
    save_to: str = "download",
) -> str:
    """下载普通 HTTP/HTTPS 直链文件。"""
    url = (url or "").strip()
    if not url:
        return err("URL 为空")

    out_dir = _resolve_output_dir(output_dir, save_to)
    out_dir.mkdir(parents=True, exist_ok=True)

    extra_headers = {}
    if headers and headers.strip():
        try:
            extra_headers = json.loads(headers)
            if not isinstance(extra_headers, dict):
                return err("headers 必须是 JSON object")
        except json.JSONDecodeError as e:
            return err(f"headers 不是合法 JSON: {e}")

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "votx-agent/1.0")
    for key, value in extra_headers.items():
        req.add_header(str(key), str(value))

    try:
        with urllib.request.urlopen(req, timeout=_direct_timeout()) as resp:
            content_type = resp.headers.get("Content-Type", "")
            final_name = _safe_filename(filename) if filename else _filename_from_headers(resp.geturl(), resp.headers)
            target = _unique_path(out_dir / final_name, overwrite=overwrite)
            total = 0
            with target.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    total += len(chunk)
                    if _MAX_DIRECT_BYTES > 0 and total > _MAX_DIRECT_BYTES:
                        return err(f"文件超过 DOWNLOAD_MAX_BYTES 限制，已中止: {target}")
                    f.write(chunk)
        _write_manifest({
            "kind": "direct",
            "url": url,
            "path": str(target),
            "bytes": total,
            "status": "ok",
        })
        artifact = make_file_artifact(
            target,
            dir=save_to,
            mime_type=content_type,
            size=total,
        )
        return make_tool_result(True, "已下载文件", [artifact], url=url)
    except Exception as e:
        return err(f"下载失败: {e}")


def download_video(
    url: str,
    output_dir: str = "",
    filename: str = "",
    format_spec: str = "",
    audio_only: bool = False,
    write_subs: bool = False,
    cookies_file: str = "",
    save_to: str = "download",
) -> str:
    """使用 yt-dlp 下载视频或音频。"""
    url = (url or "").strip()
    if not url:
        return err("URL 为空")
    dep_err = _check_dependency("yt-dlp")
    if dep_err:
        return err(dep_err)

    out_dir = _resolve_output_dir(output_dir, save_to)
    out_dir.mkdir(parents=True, exist_ok=True)

    args = ["yt-dlp"]
    if audio_only:
        args.extend(["-x", "--audio-format", "mp3"])
    else:
        args.extend(["-f", format_spec.strip() or _DEFAULT_YTDLP_FORMAT])
    if write_subs:
        args.extend(["--write-subs", "--sub-langs", "all"])

    if cookies_file.strip():
        args.extend(["--cookies", cookies_file.strip()])

    if filename.strip():
        safe_name = _safe_filename(filename.strip())
        output_template = str(out_dir / safe_name)
    else:
        output_template = str(out_dir / "%(title)s.%(ext)s")
    args.extend(["-o", output_template, url])

    timeout = _video_timeout()
    try:
        r = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            timeout=timeout,
            env=utf8_subprocess_env(),
        )
        stdout = decode_subprocess_output(r.stdout).strip()
        stderr = decode_subprocess_output(r.stderr).strip()
        lines = []
        if stdout:
            lines.append(stdout)
        if stderr:
            stderr_lines = stderr.splitlines()
            key_lines = [
                line for line in stderr_lines
                if "Destination" in line or "Merging" in line or "has already been downloaded" in line
            ]
            lines.append("\n".join((key_lines + stderr_lines[-8:])[-12:]))
        output = "\n".join(line for line in lines if line).strip()

        if r.returncode != 0:
            return err(f"yt-dlp 失败 (code={r.returncode}): {output}")

        _write_manifest({
            "kind": "video",
            "url": url,
            "output_dir": str(out_dir),
            "status": "ok",
        })
        return output or f"OK: 已下载到 {out_dir}"
    except subprocess.TimeoutExpired:
        return err(f"下载超时 ({timeout}s)")
    except Exception as e:
        return err(f"下载失败: {e}")


def list_downloads(limit: int = 20) -> str:
    """查看最近下载记录。"""
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20

    path = _download_log_path()
    if not path.exists():
        return "暂无下载记录"

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows = []
        for line in lines[-limit:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(
                f"{item.get('kind', '')}: {item.get('path') or item.get('output_dir', '')} <- {item.get('url', '')}"
            )
        return "\n".join(rows) if rows else "暂无下载记录"
    except Exception as e:
        return err(f"读取下载记录失败: {e}")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_download_url",
            "description": "检查下载链接类型、文件名、大小、Content-Type、是否支持断点续传。当用户要求查看链接是什么文件、文件多大、能不能下载、获取文件信息时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "下载 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_direct_file",
            "description": "下载普通 HTTP/HTTPS 直链文件，默认保存到用户 download 目录。当用户给出一个直链下载地址、要求下载文件、保存附件时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "直链 URL"},
                    "output_dir": {"type": "string", "description": "输出目录，可选"},
                    "filename": {"type": "string", "description": "保存文件名，可选"},
                    "overwrite": {"type": "boolean", "description": "是否覆盖已有文件"},
                    "headers": {"type": "string", "description": "JSON 格式请求头，可选"},
                    "save_to": {
                        "type": "string",
                        "enum": ["download", "file"],
                        "description": "download 保存到用户 download；file 保存到 history/file",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_video",
            "description": "使用 yt-dlp 下载视频或音频，支持 B站/YouTube/抖音等 yt-dlp 支持的平台。当用户要求下载视频、保存视频、提取音频、下载 B站/YouTube 视频时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频 URL"},
                    "output_dir": {"type": "string", "description": "输出目录，可选"},
                    "filename": {"type": "string", "description": "输出文件名模板，可选"},
                    "format_spec": {"type": "string", "description": "yt-dlp 格式选择器，可选"},
                    "audio_only": {"type": "boolean", "description": "是否仅提取 mp3 音频"},
                    "write_subs": {"type": "boolean", "description": "是否下载字幕"},
                    "cookies_file": {"type": "string", "description": "cookies.txt 文件路径"},
                    "save_to": {
                        "type": "string",
                        "enum": ["download", "file"],
                        "description": "download 保存到用户 download；file 保存到 history/file",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_downloads",
            "description": "查看最近下载记录。当用户询问下载了什么、查看下载历史、之前下载的文件在哪时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回记录数，默认 20，上限 100"},
                },
            },
        },
    },
]

HANDLERS = {
    "inspect_download_url": inspect_download_url,
    "download_direct_file": download_direct_file,
    "download_video": download_video,
    "list_downloads": list_downloads,
}


def register():
    for schema in SCHEMAS:
        name = schema["function"]["name"]
        register_tool(schema, HANDLERS[name])
