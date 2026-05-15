"""Small permission and OneBot message helpers."""
from __future__ import annotations

import re
from typing import Any

_AT_RE = re.compile(r"\[CQ:at,qq=(?:\d+|all)[^\]]*\]\s*")
_CQ_RE = re.compile(r"\[CQ:[^\]]+\]")


def is_admin(identity: dict[str, Any]) -> bool:
    return identity.get("role") == "admin"


def message_mentions_bot(message: dict[str, Any], self_id: str | None = None) -> bool:
    segments = message.get("message")
    if isinstance(segments, list):
        for seg in segments:
            if not isinstance(seg, dict) or seg.get("type") != "at":
                continue
            qq = str(seg.get("data", {}).get("qq", ""))
            if qq == "all" or not self_id or qq == str(self_id):
                return True

    raw = message.get("raw_message", "")
    if not isinstance(raw, str):
        return False
    if self_id and f"[CQ:at,qq={self_id}" in raw:
        return True
    return "[CQ:at" in raw if not self_id else False


def onebot_text(message: dict[str, Any], self_id: str | None = None) -> str:
    segments = message.get("message")
    if isinstance(segments, list):
        parts: list[str] = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type")
            data = seg.get("data", {})
            if seg_type == "text":
                parts.append(str(data.get("text", "")))
            elif seg_type == "at":
                qq = str(data.get("qq", ""))
                if qq != "all" and (not self_id or qq == str(self_id)):
                    continue
                parts.append(f"@{qq}")
            elif seg_type in ("image", "record", "video", "file"):
                file_name = data.get("file") or data.get("url") or ""
                parts.append(f"[{seg_type}:{file_name}]")
        return " ".join(p for p in parts if p).strip()

    raw = str(message.get("raw_message", ""))
    raw = _AT_RE.sub("", raw)
    raw = _CQ_RE.sub(lambda m: _cq_placeholder(m.group(0)), raw)
    return raw.strip()


def _cq_placeholder(cq_code: str) -> str:
    if cq_code.startswith("[CQ:image"):
        return "[image]"
    if cq_code.startswith("[CQ:record"):
        return "[voice]"
    if cq_code.startswith("[CQ:video"):
        return "[video]"
    if cq_code.startswith("[CQ:file"):
        return "[file]"
    return ""


def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit and current:
            chunks.append(current)
            current = ""
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current += line
    if current:
        chunks.append(current)
    return chunks or [text[:limit]]
