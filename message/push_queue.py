"""File-backed push queue consumed by the in-process message router."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PushQueue:
    def __init__(self, root: str, queue_dir: str):
        path = Path(queue_dir)
        if not path.is_absolute():
            path = Path(root) / path
        self.queue_dir = path
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, task: dict[str, Any]) -> str:
        task_id = task.get("id") or f"push_{uuid.uuid4().hex[:12]}"
        if not str(task_id).startswith("push_"):
            task_id = f"push_{task_id}"
        item = {
            **task,
            "id": task_id,
            "status": "pending",
            "attempts": int(task.get("attempts", 0)),
            "created_at": task.get("created_at") or utc_now(),
            "updated_at": utc_now(),
        }
        self._write(task_id, item)
        return task_id

    def pending(self) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for path in sorted(self.queue_dir.glob("push_*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if item.get("status") == "pending":
                tasks.append(item)
        return tasks

    def complete(self, task_id: str, result: dict[str, Any] | None = None):
        item = self._read(task_id)
        if not item:
            return
        item["status"] = "completed"
        item["result"] = result or {}
        item["completed_at"] = utc_now()
        item["updated_at"] = utc_now()
        self._write(task_id, item)

    def fail(self, task_id: str, error: str, retry_times: int):
        item = self._read(task_id)
        if not item:
            return
        item["attempts"] = int(item.get("attempts", 0)) + 1
        item["error"] = error
        item["updated_at"] = utc_now()
        if item["attempts"] >= retry_times:
            item["status"] = "failed"
            item["failed_at"] = utc_now()
        self._write(task_id, item)

    def _read(self, task_id: str) -> dict[str, Any] | None:
        path = self.queue_dir / f"{task_id}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write(self, task_id: str, item: dict[str, Any]):
        final = self.queue_dir / f"{task_id}.json"
        tmp = self.queue_dir / f".{task_id}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, final)


def enqueue_message(root: str, queue_dir: str, platform: str, chat_type: str,
                    chat_id: str | int, message: str, source: dict[str, Any] | None = None) -> str:
    queue = PushQueue(root, queue_dir)
    return queue.enqueue({
        "type": "message",
        "platform": platform,
        "chat_type": chat_type,
        "chat_id": str(chat_id),
        "message": message,
        "source": source or {},
    })
