"""task_time Skill — corn 定时任务管理工具"""
import uuid

from run.tool import register_tool
from skills._common import err, get_current_user_dir


def _get_user_dir():
    return get_current_user_dir()


def task_time_create(type: str = "daily", time: str = "09:00", command: str = "") -> str:
    """创建定时任务"""
    user_dir = _get_user_dir()
    if not user_dir:
        return err("未设置用户目录，无法创建任务")

    if type not in ("daily", "once", "recurring"):
        return err(f"无效的任务类型: {type}，可选值: daily / once / recurring")

    if not command.strip():
        return err("任务命令不能为空")

    from corn.tasks import create_task

    task = create_task(user_dir, {
        "id": uuid.uuid4().hex[:8],
        "type": type,
        "time": time,
        "command": command.strip(),
    })
    return (
        f"任务已创建:\n"
        f"  ID: {task['id']}\n"
        f"  类型: {task['type']}\n"
        f"  时间: {task['time']}\n"
        f"  命令: {task['command']}"
    )


def task_time_list() -> str:
    """列出当前用户所有定时任务"""
    user_dir = _get_user_dir()
    if not user_dir:
        return err("未设置用户目录")

    from corn.tasks import load_tasks

    tasks = load_tasks(user_dir)
    if not tasks:
        return "当前没有定时任务。"

    lines = [f"共 {len(tasks)} 个定时任务:\n"]
    for t in tasks:
        status = ""
        if t.get("last_run"):
            status = f" (上次执行: {t['last_run']})"
        lines.append(
            f"  [{t['id']}] {t['type']} {t['time']} — {t['command']}{status}"
        )
    return "\n".join(lines)


def task_time_delete(task_id: str) -> str:
    """删除指定定时任务"""
    user_dir = _get_user_dir()
    if not user_dir:
        return err("未设置用户目录")

    if not task_id.strip():
        return err("请指定要删除的任务 ID")

    from corn.tasks import delete_task, get_task

    task = get_task(user_dir, task_id.strip())
    if task is None:
        return err(f"未找到任务: {task_id}")

    delete_task(user_dir, task_id.strip())
    return f"任务已删除: [{task['id']}] {task['command']}"


def task_time_update(task_id: str, time: str = None, command: str = None, type: str = None) -> str:
    """修改定时任务的时间/命令/类型"""
    user_dir = _get_user_dir()
    if not user_dir:
        return err("未设置用户目录")

    if not task_id.strip():
        return err("请指定要修改的任务 ID")

    from corn.tasks import update_task

    updates = {}
    if time is not None:
        updates["time"] = time
    if command is not None:
        updates["command"] = command
    if type is not None:
        if type not in ("daily", "once", "recurring"):
            return err(f"无效的任务类型: {type}")
        updates["type"] = type

    if not updates:
        return err("请至少指定一项修改（time / command / type）")

    updated = update_task(user_dir, task_id.strip(), updates)
    if updated is None:
        return err(f"未找到任务: {task_id}")

    return (
        f"任务已更新:\n"
        f"  ID: {updated['id']}\n"
        f"  类型: {updated['type']}\n"
        f"  时间: {updated['time']}\n"
        f"  命令: {updated['command']}"
    )


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "task_time_create",
            "description": "创建 corn 定时任务（daily=每日执行 / once=单次执行）",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["daily", "once"],
                        "description": "任务类型: daily=每天执行, once=执行一次",
                    },
                    "time": {
                        "type": "string",
                        "description": "执行时间，HH:MM 格式（例如 09:00）",
                    },
                    "command": {
                        "type": "string",
                        "description": "任务命令/prompt，corn 执行时发送给 AI 的消息内容",
                    },
                },
                "required": ["type", "time", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_time_list",
            "description": "列出当前用户的所有 corn 定时任务",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_time_delete",
            "description": "删除指定的 corn 定时任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要删除的任务 ID",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_time_update",
            "description": "修改 corn 定时任务的时间、命令或类型",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要修改的任务 ID",
                    },
                    "time": {
                        "type": "string",
                        "description": "新的执行时间，HH:MM 格式",
                    },
                    "command": {
                        "type": "string",
                        "description": "新的任务命令/prompt",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["daily", "once"],
                        "description": "新的任务类型",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
]

HANDLERS = {
    "task_time_create": task_time_create,
    "task_time_list": task_time_list,
    "task_time_delete": task_time_delete,
    "task_time_update": task_time_update,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
