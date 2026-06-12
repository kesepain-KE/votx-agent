"""通用下载编排器 — 直链下载、视频下载、下载记录。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlparse
import urllib.error
import urllib.request

from run.io_utils import append_jsonl, decode_subprocess_output, utf8_subprocess_env
from run.tool import register_tool
from plugins._common import (
    err,
    get_current_user_dir,
    get_effective_tool_timeout,
    safe_path,
    check_sandbox,
    validate_url,
)

_MAX_DIRECT_BYTES = int(os.environ.get("DOWNLOAD_MAX_BYTES", str(1024 * 1024 * 1024)))
_DEFAULT_YTDLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _env_int(name: str, default: int) -> int:
    """读取正整数环境变量，失败时返回默认值。"""
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


_DIRECT_TIMEOUT_DEFAULT = _env_int("DOWNLOAD_TIMEOUT", 30)
_VIDEO_TIMEOUT_DEFAULT = _env_int("DOWNLOAD_VIDEO_TIMEOUT", 600)


def _direct_timeout() -> int:
    """直链/探测请求的有效超时。"""
    return get_effective_tool_timeout(_DIRECT_TIMEOUT_DEFAULT)


def _video_timeout() -> int:
    """yt-dlp 下载的有效超时。"""
    return get_effective_tool_timeout(_VIDEO_TIMEOUT_DEFAULT)


def _env_enabled(name: str) -> bool:
    """判断环境变量是否开启。"""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _default_download_dir(kind: str = "download") -> Path:
    """返回默认下载目录。"""
    user_dir = get_current_user_dir()
    if user_dir:
        base = Path(user_dir)
        if kind == "file":
            return base / "history" / "file"
        return base / "download"
    return Path(__file__).resolve().parent.parent.parent / "tmp" / "download"


def _resolve_output_dir(output_dir: str = "", save_to: str = "download") -> Path | None:
    """解析输出目录。默认限定在项目/用户目录，环境变量可放开。"""
    raw = output_dir.strip() if output_dir else ""
    if not raw:
        return _default_download_dir(save_to)

    p = safe_path(raw)
    if p is None:
        return None
    resolved = check_sandbox(p)
    if resolved:
        return resolved
    if _env_enabled("VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX"):
        return Path(raw).expanduser().resolve()
    return None


def _safe_filename(name: str, fallback: str = "download") -> str:
    """清理文件名，避免路径穿越和非法字符。"""
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
    """检查命令是否存在。"""
    if shutil.which(name):
        return None
    return f"未找到 {name}，请先安装后再试"


def _download_log_path() -> Path:
    """下载记录路径。"""
    return _default_download_dir("download") / "download_manifest.jsonl"


def _write_manifest(entry: dict):
    """记录下载结果。"""
    try:
        append_jsonl(_download_log_path(), entry)
    except Exception:
        pass


def _url_error(url: str, network_scope: str = "public") -> str | None:
    """下载 URL 校验。"""
    return validate_url(url, network_scope or "public")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """跟随重定向前重新校验目标 URL。"""

    def __init__(self, network_scope: str = "public"):
        super().__init__()
        self.network_scope = network_scope

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url_err = _url_error(newurl, self.network_scope)
        if url_err:
            raise urllib.error.URLError(f"重定向目标不安全: {url_err}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(req, network_scope: str = "public", timeout: int | None = None):
    """打开 URL，并在重定向时保持 network_scope 校验。"""
    opener = urllib.request.build_opener(_SafeRedirectHandler(network_scope))
    return opener.open(req, timeout=timeout or _direct_timeout())


def inspect_download_url(url: str, network_scope: str = "public") -> str:
    """检查下载 URL 元信息。"""
    url = (url or "").strip()
    if not url:
        return err("URL 为空")
    url_err = _url_error(url, network_scope)
    if url_err:
        return err(url_err)

    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "votx-agent/1.0")
    try:
        with _open_url(req, network_scope) as resp:
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
            return _inspect_with_range_get(url, network_scope)
        return err(f"检查失败: HTTP {e.code} {e.reason}")
    except Exception as e:
        return err(f"检查失败: {e}")


def _inspect_with_range_get(url: str, network_scope: str = "public") -> str:
    """HEAD 不可用时用 Range GET 探测。"""
    url_err = _url_error(url, network_scope)
    if url_err:
        return err(url_err)
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "votx-agent/1.0")
    req.add_header("Range", "bytes=0-0")
    try:
        with _open_url(req, network_scope) as resp:
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
    network_scope: str = "public",
    save_to: str = "download",
) -> str:
    """下载普通 HTTP/HTTPS 直链文件。"""
    url = (url or "").strip()
    if not url:
        return err("URL 为空")
    url_err = _url_error(url, network_scope)
    if url_err:
        return err(url_err)

    out_dir = _resolve_output_dir(output_dir, save_to)
    if not out_dir:
        return err("输出目录越权或无效。设置 VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1 可输出到任意目录。")
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
        with _open_url(req, network_scope) as resp:
            cl = resp.headers.get("Content-Length")
            if cl:
                try:
                    if int(cl) > _MAX_DIRECT_BYTES:
                        return err(f"文件过大 ({cl} bytes)，超过 DOWNLOAD_MAX_BYTES 限制")
                except ValueError:
                    pass
            final_name = _safe_filename(filename) if filename else _filename_from_headers(resp.geturl(), resp.headers)
            target = _unique_path(out_dir / final_name, overwrite=overwrite)
            total = 0
            with target.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > _MAX_DIRECT_BYTES:
                        return err(f"文件超过 DOWNLOAD_MAX_BYTES 限制，已中止: {target}")
                    f.write(chunk)
        _write_manifest({
            "kind": "direct",
            "url": url,
            "path": str(target),
            "bytes": total,
            "status": "ok",
        })
        return f"OK: 已下载 {target} ({total} bytes)"
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
    if not out_dir:
        return err("输出目录越权或无效。设置 VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1 可输出到任意目录。")
    out_dir.mkdir(parents=True, exist_ok=True)

    args = ["yt-dlp"]
    if audio_only:
        args.extend(["-x", "--audio-format", "mp3"])
    else:
        args.extend(["-f", format_spec.strip() or _DEFAULT_YTDLP_FORMAT])
    if write_subs:
        args.extend(["--write-subs", "--sub-langs", "all"])

    if cookies_file.strip():
        cookies = safe_path(cookies_file.strip())
        if cookies is None or not check_sandbox(cookies):
            return err("cookies_file 路径无效或越权")
        args.extend(["--cookies", str(cookies)])

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
            "description": "检查下载链接类型、文件名、大小、Content-Type、是否支持断点续传。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "下载 URL"},
                    "network_scope": {
                        "type": "string",
                        "enum": ["public", "local", "private", "all"],
                        "description": "允许访问的网络范围，默认 public",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_direct_file",
            "description": "下载普通 HTTP/HTTPS 直链文件，默认保存到用户 download 目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "直链 URL"},
                    "output_dir": {"type": "string", "description": "输出目录，可选"},
                    "filename": {"type": "string", "description": "保存文件名，可选"},
                    "overwrite": {"type": "boolean", "description": "是否覆盖已有文件"},
                    "headers": {"type": "string", "description": "JSON 格式请求头，可选"},
                    "network_scope": {
                        "type": "string",
                        "enum": ["public", "local", "private", "all"],
                        "description": "允许访问的网络范围，默认 public",
                    },
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
            "description": "使用 yt-dlp 下载视频或音频，支持 B站/YouTube/抖音等 yt-dlp 支持的平台。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频 URL"},
                    "output_dir": {"type": "string", "description": "输出目录，可选"},
                    "filename": {"type": "string", "description": "输出文件名模板，可选"},
                    "format_spec": {"type": "string", "description": "yt-dlp 格式选择器，可选"},
                    "audio_only": {"type": "boolean", "description": "是否仅提取 mp3 音频"},
                    "write_subs": {"type": "boolean", "description": "是否下载字幕"},
                    "cookies_file": {"type": "string", "description": "cookies.txt 文件路径，仅限用户自己的账号"},
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
            "description": "查看最近下载记录。",
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
    """注册 download_anything 工具。"""
    for schema in SCHEMAS:
        name = schema["function"]["name"]
        register_tool(schema, HANDLERS[name])
