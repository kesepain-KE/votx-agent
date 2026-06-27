"""Shared helpers for structured tool artifacts."""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "ico"}
_VALID_DIRS = {"file", "download", "knowledge", "global-knowledge"}


def _safe_name(value: str | None) -> str:
    name = (value or "").strip().replace("\\", "/")
    return Path(name).name


def _to_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def project_relative_path(path: str | Path) -> str:
    resolved = _to_path(path).expanduser().resolve()
    try:
        return resolved.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def infer_artifact_dir(path: str | Path | None) -> str | None:
    if not path:
        return None
    normalized = project_relative_path(path).replace("\\", "/")
    if normalized.startswith("knowledge/"):
        return "global-knowledge"
    if "/download/" in normalized:
        return "download"
    if "/knowledge/" in normalized:
        return "knowledge"
    if "/history/file/" in normalized:
        return "file"
    return None


def build_view_url(name: str, dir: str | None = None) -> str:
    q = f"?dir={quote(dir, safe='')}" if dir else ""
    return f"/api/files/view/{quote(name, safe='')}{q}"


def build_download_url(name: str, dir: str | None = None) -> str:
    q = f"?dir={quote(dir, safe='')}" if dir else ""
    return f"/api/files/download/{quote(name, safe='')}{q}"


def _guess_mime_type(name: str, mime_type: str | None = None) -> str | None:
    mime = (mime_type or "").strip().lower()
    if mime:
        mime = mime.split(";", 1)[0].strip()
        return mime
    guessed, _ = mimetypes.guess_type(name)
    return guessed


def _infer_kind(name: str, mime_type: str | None, explicit: str | None = None) -> str:
    if explicit in ("file", "image"):
        return explicit
    mime = _guess_mime_type(name, mime_type)
    if mime and mime.startswith("image/"):
        return "image"
    ext = Path(name).suffix.lower().lstrip(".")
    if ext in _IMAGE_EXTS:
        return "image"
    return "file"


def _stat_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _read_image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
    except Exception:
        return None, None

    try:
        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None, None


def make_file_artifact(
    path: str | Path,
    *,
    kind: str | None = None,
    dir: str | None = None,
    name: str | None = None,
    mime_type: str | None = None,
    size: int | None = None,
    preview_url: str | None = None,
    download_url: str | None = None,
    width: int | None = None,
    height: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    resolved = _to_path(path).expanduser().resolve()
    artifact_name = _safe_name(name or resolved.name)
    artifact_path = project_relative_path(resolved)
    artifact_dir = dir if dir in _VALID_DIRS else infer_artifact_dir(artifact_path)
    artifact_mime = _guess_mime_type(artifact_name, mime_type)
    artifact_kind = _infer_kind(artifact_name, artifact_mime, kind)

    if size is None:
        size = _stat_size(resolved)
    if artifact_kind == "image" and (width is None or height is None):
        inferred_width, inferred_height = _read_image_dimensions(resolved)
        width = width if width is not None else inferred_width
        height = height if height is not None else inferred_height

    artifact: dict[str, Any] = {
        "kind": artifact_kind,
        "name": artifact_name,
        "path": artifact_path,
        "dir": artifact_dir,
    }
    if artifact_mime:
        artifact["mimeType"] = artifact_mime
    if size is not None:
        artifact["size"] = size
    if width is not None:
        artifact["width"] = width
    if height is not None:
        artifact["height"] = height
    if preview_url is None and artifact_dir:
        preview_url = build_view_url(artifact_name, artifact_dir)
    if download_url is None and artifact_dir:
        download_url = build_download_url(artifact_name, artifact_dir)
    if preview_url:
        artifact["previewUrl"] = preview_url
    if download_url:
        artifact["downloadUrl"] = download_url
    if extra:
        artifact.update(extra)
    return artifact


def make_image_artifact(
    path: str | Path,
    *,
    dir: str | None = None,
    name: str | None = None,
    mime_type: str | None = None,
    size: int | None = None,
    preview_url: str | None = None,
    download_url: str | None = None,
    width: int | None = None,
    height: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return make_file_artifact(
        path,
        kind="image",
        dir=dir,
        name=name,
        mime_type=mime_type,
        size=size,
        preview_url=preview_url,
        download_url=download_url,
        width=width,
        height=height,
        **extra,
    )


def make_tool_result(
    success: bool,
    message: str,
    artifacts: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> str:
    payload: dict[str, Any] = {
        "success": bool(success),
        "message": message,
    }
    if artifacts is not None:
        payload["artifacts"] = artifacts
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, indent=2)
