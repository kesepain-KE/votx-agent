"""后台调度循环 — 心跳 5s，扫描任务、匹配时间、执行、清理

所有时间计算统一使用北京时间 (UTC+8)。
"""
import json
import os
import subprocess
import sys
import time as _time
from datetime import datetime, timezone, timedelta

from cron.tasks import mark_run, delete_task
from cron.forget import run_forget, run_auto_improve_trigger

BEIJING_TZ = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(BEIJING_TZ)


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
        created = task.get("created_at", "")
        try:
            # created_at 已是北京时间，与 now 同基准
            created_date = created[:10]
            today = now.strftime("%Y-%m-%d")
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
    """once 任务超过目标时间 +120s 且未曾执行，或已执行且过期，则标记为可删除"""
    if task.get("type") != "once":
        return False
    parsed = _parse_task_time(task)
    if parsed is None:
        # 格式错误：保留文件但跳过，避免静默删除
        return False
    h, m = parsed
    now = _now()
    target_minutes = h * 60 + m
    current_minutes = now.hour * 60 + now.minute

    # 未超出目标时间 +2 分钟窗口，保留
    if current_minutes < target_minutes + 2:
        return False
    if current_minutes == target_minutes + 2 and now.second <= 30:
        return False

    # 超出时间窗口：仅当任务已执行过才删除；未执行的保留并记录
    if task.get("last_run") is None:
        print(f"[cron] once 任务已过期但未执行，保留等待手动处理: {task['id']} — {task.get('command', '')}")
        return False

    return True


def _run_task(root: str, task: dict):
    """CLI 模式：通过 subprocess 执行任务"""
    user_name = task.get("user", "")
    command = task.get("command", "")
    start_py = os.path.join(root, "start.py")
    try:
        result = subprocess.run(
            [sys.executable, start_py, "--user", user_name, "--prompt", command, "--once"],
            timeout=300,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return (result.stdout or result.stderr or "").strip()
    except subprocess.TimeoutExpired:
        print(f"[cron] 任务超时: {task['id']} — {command}")
    except Exception as e:
        print(f"[cron] 任务执行失败: {task['id']} — {e}")
    return ""


def _run_task_web(root: str, core_config: dict, task: dict):
    """Web 模式：进程内执行，输出保存为独立归档文件"""
    user_name = task.get("user", "")
    command = task.get("command", "")
    user_dir = os.path.join(root, "users", user_name)

    import json as _json
    from datetime import datetime as _dt

    # 加载配置
    with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
        user_config = _json.load(f)

    # 创建 provider
    try:
        from provider.factory import create_provider
        provider = create_provider(user_config, core_config)
    except Exception as e:
        print(f"[cron:web] 创建 provider 失败: {e}")
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
    from skills import load_disabled_skills

    system_prompt = build_cached_system_prompt(root, user_dir)
    disabled_skills = load_disabled_skills(user_dir)
    tools = load_tool_schemas(disabled_skills=disabled_skills)
    tool_runner = ToolRunner(core_config, user_config, user_dir=user_dir, disabled_skills=disabled_skills)
    chat.set_system_prompt(system_prompt)

    import plugins.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    import plugins.task_plan.tool as tp_tool
    tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    import plugins.vision_universal.tool as vu_tool
    vu_tool.set_vision_context(provider=provider, chat=chat, user_name=user_name)

    chat.add_user_message(command)
    tool_runner.reset_count()

    response_text = ""
    for event in run_chat_turn(chat, tool_runner, provider, tools):
        if event["type"] == "tool_call":
            print(f"  [cron:web] {event['line']}")
        elif event["type"] == "text_chunk":
            response_text += event["content"]
        elif event["type"] == "text":
            response_text = event["content"]
        elif event["type"] == "error":
            print(f"  [cron:web] Provider 错误: {event['content']}")

    # 生成摘要
    from run.summarize import generate_summary, load_index, save_index
    summary = generate_summary(provider, chat.messages)
    if not summary:
        summary = f"cron: {command}"[:50]

    # 保存为归档文件
    ts = _dt.now(BEIJING_TZ).strftime("%Y%m%dT%H%M%S")
    archive_dir = os.path.join(user_dir, "history", "archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_name = f"cron_{ts}_{task['id']}.json"
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

    print(f"[cron:web] 任务 {task['id']} 完成 → {archive_name} ({summary})")
    return response_text.strip()


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

    tick = 0

    while not stop_event.is_set():
        try:
            improve_cfg = core_config.get("improve", {})
            forget_time = improve_cfg.get("forget_time", 604800)

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
                            last_run = task.get("last_run")
                            task_type = task.get("type", "daily")

                            # 去重：once 任务执行过就跳过，daily/recurring 今天执行过就跳过
                            if last_run:
                                if task_type == "once":
                                    continue
                                if task_type in ("daily", "recurring"):
                                    try:
                                        today_str = _now().strftime("%Y-%m-%d")
                                        if last_run[:10] == today_str:
                                            continue
                                    except Exception:
                                        pass

                            print(f"[cron] 执行任务: {task['id']} — {task['command']}")
                            from run.user_locks import get_user_lock
                            with get_user_lock(task.get("user", "")):
                                if web_mode:
                                    result_text = run_task(root, core_config, task)
                                else:
                                    result_text = run_task(root, task)
                                mark_run(user_dir, task["id"])
                            _enqueue_task_result(root, task, result_text or "")

                        if _is_expired(task):
                            os.remove(filepath)
                            print(f"[cron] 过期任务已删除: {task['id']}")

                # ── 清理临时记忆（每 12 个心跳 = 60s 执行一次）──
                if tick % 12 == 0:
                    run_forget(user_dir, forget_time)

                # ── 定期 auto_improve ──
                run_auto_improve_trigger(root, user_dir, core_config)

            tick += 1

        except Exception as e:
            print(f"[cron] 调度循环异常: {e}")

        stop_event.wait(heartbeat)


def _enqueue_task_result(root: str, task: dict, result_text: str):
    """If a task came from an external router, enqueue its completion notice."""
    source = task.get("source") or {}
    if not source:
        return
    try:
        from message.config import load_config
        cfg = load_config(root)
        if not cfg.get("enabled"):
            return
        integration = cfg.get("task_integration", {})
        if not integration.get("notify_on_task_complete", True):
            return
        push_cfg = cfg.get("push", {})
        if not push_cfg.get("enabled", True):
            return

        message = (
            "定时任务执行完成\n\n"
            f"任务: {task.get('command', '')}\n\n"
            f"结果:\n{result_text or '任务已完成，但没有生成文本输出。'}"
        )
        from message.push_queue import enqueue_message
        enqueue_message(
            root,
            push_cfg.get("queue_dir", "message/push_queue"),
            source.get("platform", "onebot"),
            source.get("chat_type", "private"),
            source.get("chat_id") or source.get("external_id"),
            message,
            source=source,
        )
    except Exception as e:
        print(f"[cron] 推送任务结果入队失败: {task.get('id')} — {e}")
