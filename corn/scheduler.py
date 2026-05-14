"""后台调度循环 — 心跳 5s，扫描任务、匹配时间、执行、清理"""
import json
import os
import subprocess
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from corn.tasks import mark_run, delete_task
from corn.forget import run_forget, run_auto_improve_trigger


def _parse_task_time(task: dict) -> tuple[int, int] | None:
    """解析任务时间，返回 (hour, minute) 或 None（非 HH:MM 格式）"""
    t = task.get("time", "")
    try:
        parts = t.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def _now() -> datetime:
    return datetime.now()


def _match_task(task: dict) -> bool:
    """检查任务是否应该当前这轮执行。

    规则:
    - once 任务: 到达时间后执行一次（时间窗口 ±30s）
    - daily 任务: 每天对应时间执行
    - recurring 任务: 同 daily（后续可扩展间隔）
    """
    now = _now()
    parsed = _parse_task_time(task)
    if parsed is None:
        return False
    h, m = parsed
    target_minutes = h * 60 + m
    current_minutes = now.hour * 60 + now.minute

    task_type = task.get("type", "daily")

    if task_type == "once":
        # once 任务仅在创建日期的对应时间窗口内匹配
        created = task.get("created_at", "")
        try:
            created_date = created[:10]  # YYYY-MM-DD
            today = now.strftime("%Y-%m-%d")
            if created_date != today:
                # 也接受今天还没到时间的情况（宽松：只要日期 <= 今天）
                if created_date > today:
                    return False
        except Exception:
            pass

    if current_minutes == target_minutes:
        return True

    # ±30 秒窗口防止恰好整分钟时错过
    if current_minutes == target_minutes - 1 and now.second >= 30:
        return True
    if current_minutes == target_minutes + 1 and now.second <= 30:
        return True

    return False


def _is_expired(task: dict) -> bool:
    """once 任务超过目标时间 +60s 且已执行过，标记为过期可删除"""
    if task.get("type") != "once":
        return False
    parsed = _parse_task_time(task)
    if parsed is None:
        return True  # 格式错误视为过期
    h, m = parsed
    now = _now()
    target_minutes = h * 60 + m
    current_minutes = now.hour * 60 + now.minute
    # 超过目标时间 2 分钟以上
    if current_minutes > target_minutes + 2:
        return True
    if current_minutes == target_minutes + 2 and now.second > 30:
        return True
    return False


def _run_task(root: str, task: dict):
    """CLI 模式：通过 subprocess 执行任务"""
    user_name = task.get("user", "")
    command = task.get("command", "")
    start_py = os.path.join(root, "start.py")
    try:
        subprocess.run(
            [sys.executable, start_py, "--user", user_name, "--prompt", command, "--once"],
            timeout=300,
            cwd=root,
        )
    except subprocess.TimeoutExpired:
        print(f"[corn] 任务超时: {task['id']} — {command}")
    except Exception as e:
        print(f"[corn] 任务执行失败: {task['id']} — {e}")


def _run_task_web(root: str, core_config: dict, task: dict):
    """Web 模式：进程内执行，输出保存为独立归档文件"""
    user_name = task.get("user", "")
    command = task.get("command", "")
    user_dir = os.path.join(root, "users", user_name)

    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    # 加载配置
    with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
        user_config = _json.load(f)

    # 创建 provider
    try:
        from provider.factory import create_provider
        provider = create_provider(user_config, core_config)
    except Exception as e:
        print(f"[corn:web] 创建 provider 失败: {e}")
        return

    # 创建 ChatManager，加载历史
    from run.chat import ChatManager
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_provider(provider)
    try:
        chat.load_history()
    except Exception:
        pass

    # 发送消息并执行
    from run.engine import run_chat_turn, build_system_prompt
    from run.prompt_cache import build_cached_system_prompt
    from run.tool import ToolRunner, load_tool_schemas

    system_prompt = build_cached_system_prompt(root, user_dir)
    tools = load_tool_schemas()
    tool_runner = ToolRunner(core_config, user_config, user_dir=user_dir)
    chat.set_system_prompt(system_prompt)

    import skills.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)

    chat.add_user_message(command)
    tool_runner.reset_count()

    response_text = ""
    for event in run_chat_turn(chat, tool_runner, provider, tools):
        if event["type"] == "tool_call":
            print(f"  [corn:web] {event['line']}")
        elif event["type"] == "text_chunk":
            response_text += event["content"]
        elif event["type"] == "text":
            response_text = event["content"]
        elif event["type"] == "error":
            print(f"  [corn:web] Provider 错误: {event['content']}")

    # 生成摘要
    from run.summarize import generate_summary, load_index, save_index
    summary = generate_summary(provider, chat.messages)
    if not summary:
        summary = f"corn: {command}"[:50]

    # 保存为归档文件
    ts = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%S")
    archive_dir = os.path.join(user_dir, "history", "archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_name = f"corn_{ts}_{task['id']}.json"
    archive_path = os.path.join(archive_dir, archive_name)

    from run.io_utils import atomic_write_json
    # 构建完整消息（含 system prompt）
    full_messages = chat.build_messages()
    atomic_write_json(archive_path, full_messages, indent=2)

    # 更新索引
    index = load_index(user_dir)
    index[archive_name] = {
        "summary": summary,
        "msg_count": len(chat.messages),
    }
    save_index(user_dir, index)

    print(f"[corn:web] 任务 {task['id']} 完成 → {archive_name} ({summary})")


def _scan_users(root: str) -> list[str]:
    """返回所有用户目录"""
    users_dir = os.path.join(root, "users")
    if not os.path.isdir(users_dir):
        return []
    return [
        os.path.join(users_dir, d)
        for d in os.listdir(users_dir)
        if os.path.isdir(os.path.join(users_dir, d)) and not d.startswith(".")
    ]


def _scheduler_loop(root: str, core_config: dict, stop_event, web_mode: bool = False):
    """主调度循环（运行在后台 daemon 线程）"""
    heartbeat = 5
    # 首次启动后等一轮让主进程完全就绪
    _time.sleep(3)
    run_task = _run_task_web if web_mode else _run_task

    while not stop_event.is_set():
        try:
            improve_cfg = core_config.get("improve", {})
            forget_time = improve_cfg.get("forget_time", 604800)
            auto_improve_time = improve_cfg.get("auto_improve_time", 3600)

            for user_dir in _scan_users(root):
                # ── 扫描任务 ──
                tasks_dir = os.path.join(user_dir, "tasks")
                if os.path.isdir(tasks_dir):
                    for fn in sorted(os.listdir(tasks_dir)):
                        if stop_event.is_set():
                            break
                        if not fn.endswith(".json"):
                            continue
                        filepath = os.path.join(tasks_dir, fn)
                        try:
                            with open(filepath, encoding="utf-8") as f:
                                task = json.load(f)
                        except (json.JSONDecodeError, IOError):
                            continue

                        if _match_task(task):
                            # 重新从磁盘读取，防止心跳间隔内重复执行
                            try:
                                with open(filepath, encoding="utf-8") as f:
                                    task = json.load(f)
                            except (json.JSONDecodeError, IOError):
                                continue

                            last_run = task.get("last_run")
                            task_type = task.get("type", "daily")

                            # 去重：once 任务执行过就跳过，daily/recurring 今天执行过就跳过
                            if last_run:
                                if task_type == "once":
                                    continue  # once 任务只执行一次
                                if task_type in ("daily", "recurring"):
                                    try:
                                        if last_run[:10] == _time.strftime("%Y-%m-%d"):
                                            continue
                                    except Exception:
                                        pass

                            print(f"[corn] 执行任务: {task['id']} — {task['command']}")
                            if web_mode:
                                run_task(root, core_config, task)
                            else:
                                run_task(root, task)
                            mark_run(user_dir, task["id"])

                        if _is_expired(task):
                            os.remove(filepath)
                            print(f"[corn] 过期任务已删除: {task['id']}")

                # ── 清理临时记忆 ──
                run_forget(user_dir, forget_time)

                # ── 定期 auto_improve ──
                run_auto_improve_trigger(root, user_dir, core_config)

        except Exception as e:
            print(f"[corn] 调度循环异常: {e}")

        stop_event.wait(heartbeat)
