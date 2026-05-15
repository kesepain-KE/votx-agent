"""任务 CRUD — 每个用户的任务存储在 users/<name>/tasks/<id>.json

任务格式:
{
  "id": "abc123",
  "type": "once|daily|recurring",
  "time": "09:00",
  "command": "每日新闻摘要",
  "user": "kesepain",
  "created_at": "2026-05-12T09:00:00",
  "last_run": null
}
"""
import json
import os
import uuid
from datetime import datetime, timezone


def _tasks_dir(user_dir: str) -> str:
    """执行 tasks_dir 内部辅助逻辑。"""
    d = os.path.join(user_dir, "tasks")
    os.makedirs(d, exist_ok=True)
    return d


def _now_iso() -> str:
    """执行 now_iso 内部辅助逻辑。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def create_task(user_dir: str, task_def: dict) -> dict:
    """创建任务，返回完整任务对象"""
    task_id = task_def.get("id") or uuid.uuid4().hex[:8]
    task = {
        "id": task_id,
        "type": task_def.get("type", "daily"),
        "time": task_def.get("time", "09:00"),
        "command": task_def.get("command", ""),
        "user": task_def.get("user", os.path.basename(user_dir)),
        "created_at": task_def.get("created_at", _now_iso()),
        "last_run": task_def.get("last_run"),
    }
    if task_def.get("source"):
        task["source"] = task_def["source"]
    filepath = os.path.join(_tasks_dir(user_dir), f"{task_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    return task


def load_tasks(user_dir: str) -> list[dict]:
    """加载该用户所有任务"""
    tasks = []
    td = _tasks_dir(user_dir)
    if not os.path.isdir(td):
        return tasks
    for fn in sorted(os.listdir(td)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(td, fn), encoding="utf-8") as f:
                    tasks.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass
    return tasks


def get_task(user_dir: str, task_id: str) -> dict | None:
    """获取单个任务"""
    filepath = os.path.join(_tasks_dir(user_dir), f"{task_id}.json")
    if not os.path.isfile(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def update_task(user_dir: str, task_id: str, updates: dict) -> dict | None:
    """更新任务字段（time/command/type 等），返回更新后的任务"""
    task = get_task(user_dir, task_id)
    if task is None:
        return None
    for key in ("time", "command", "type", "source"):
        if key in updates and updates[key] is not None:
            task[key] = updates[key]
    filepath = os.path.join(_tasks_dir(user_dir), f"{task_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    return task


def delete_task(user_dir: str, task_id: str) -> bool:
    """删除任务，返回是否成功"""
    filepath = os.path.join(_tasks_dir(user_dir), f"{task_id}.json")
    if not os.path.isfile(filepath):
        return False
    os.remove(filepath)
    return True


def mark_run(user_dir: str, task_id: str) -> None:
    """标记任务已执行（更新 last_run）"""
    task = get_task(user_dir, task_id)
    if task is None:
        return
    task["last_run"] = _now_iso()
    filepath = os.path.join(_tasks_dir(user_dir), f"{task_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
