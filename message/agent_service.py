"""Sessionless Agent facade used by external message routers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from run.user_locks import get_user_lock


class AgentService:
    def __init__(self, root: str, core_config: dict[str, Any]):
        self.root = root
        self.core_config = core_config

    def chat(self, username: str, text: str, source: dict[str, Any] | None = None) -> str:
        lock = get_user_lock(username)
        with lock:
            session = self._ensure_session(username)
            chat = session["chat"]
            provider = session["provider"]
            tools = session["tools"]
            tool_runner = session["tool_runner"]

            if text.startswith("/") and not text.startswith(("/cron", "/plan")):
                from web.commands import _dispatch
                result = _dispatch(text, session)
                if result:
                    return str(result.get("content") or result.get("message") or result)

            from run.engine import run_chat_turn

            # External platform turns reuse the normal Web/CLI session state.
            # The source prefix gives the model enough context without creating
            # a second conversation stack for each transport.
            prompt = self._with_source(text, source)
            # 每轮工具执行前重新绑定用户上下文（防治消息路由单线程串号）
            import skills.auto_improve.tool as ai_tool
            import skills.task_plan.tool as tp_tool
            ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=username)
            tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=username)

            chat.add_user_message(prompt)
            tool_runner.reset_count()
            chat.refresh_system_prompt(self.root)

            chunks: list[str] = []
            final_text = ""
            error_text = ""
            tool_lines: list[str] = []
            try:
                for event in run_chat_turn(chat, tool_runner, provider, tools):
                    event_type = event.get("type")
                    if event_type == "text_chunk":
                        chunks.append(event.get("content", ""))
                    elif event_type == "text":
                        final_text = event.get("content", "")
                    elif event_type == "tool_call":
                        tool_lines.append(event.get("line", ""))
                    elif event_type == "error":
                        error_text = event.get("content", "")
                    elif event_type == "max_rounds":
                        error_text = "已达到工具调用上限，请稍后重试或缩小请求范围。"
            finally:
                try:
                    chat.save_history()
                    chat.save_log(chat.build_messages())
                except Exception as e:
                    print(f"[message] 保存对话失败: {username} — {e}")

            result = ""
            if final_text:
                result = final_text
            elif chunks:
                result = "".join(chunks).strip()
            elif error_text:
                result = f"处理失败: {error_text}"
            else:
                result = "已处理，但没有生成文本回复。"

            if tool_lines:
                tc = "\n".join(tool_lines[-12:])  # 最多显示最近 12 次工具调用
                return f"{tc}\n\n{result}"
            return result

    def list_tasks(self, username: str) -> list[dict[str, Any]]:
        user_dir = self._user_dir(username)
        with get_user_lock(username):
            from cron.tasks import load_tasks
            return load_tasks(user_dir)

    def create_task(self, username: str, task_type: str, time_text: str,
                    command: str, source: dict[str, Any] | None = None) -> dict[str, Any]:
        user_dir = self._user_dir(username)
        with get_user_lock(username):
            from cron.tasks import create_task
            return create_task(user_dir, {
                "type": task_type,
                "time": time_text,
                "command": command,
                "user": username,
                "source": source or {},
            })

    def update_task(self, username: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        user_dir = self._user_dir(username)
        with get_user_lock(username):
            from cron.tasks import update_task
            return update_task(user_dir, task_id, updates)

    def delete_task(self, username: str, task_id: str) -> bool:
        user_dir = self._user_dir(username)
        with get_user_lock(username):
            from cron.tasks import delete_task
            return delete_task(user_dir, task_id)

    def list_plans(self, username: str) -> list[dict[str, Any]]:
        plans_dir = Path(self._user_dir(username)) / "task-plan"
        with get_user_lock(username):
            plans: list[dict[str, Any]] = []
            if plans_dir.is_dir():
                for path in sorted(plans_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                    try:
                        plan = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    plan.setdefault("id", path.stem)
                    plans.append(plan)
            return plans

    def view_plan(self, username: str, plan_id: str) -> dict[str, Any] | None:
        with get_user_lock(username):
            path = self._plan_path(username, plan_id)
            if not path or not path.is_file():
                return None
            try:
                plan = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
            plan.setdefault("id", path.stem)
            return plan

    def approve_plan(self, username: str, plan_id: str) -> bool:
        return self._set_plan_status(username, plan_id, "in_progress")

    def abort_plan(self, username: str, plan_id: str) -> bool:
        with get_user_lock(username):
            path = self._plan_path(username, plan_id)
            if not path or not path.is_file():
                return False
            try:
                plan = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return False
            plan["status"] = "aborted"
            for step in plan.get("steps", []):
                if step.get("status") in ("pending", "in_progress"):
                    step["status"] = "skipped"
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            self._invalidate_prompt(username)
            return True

    def _set_plan_status(self, username: str, plan_id: str, status: str) -> bool:
        with get_user_lock(username):
            path = self._plan_path(username, plan_id)
            if not path or not path.is_file():
                return False
            try:
                plan = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return False
            plan["status"] = status
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            self._invalidate_prompt(username)
            return True

    def _ensure_session(self, username: str) -> dict[str, Any]:
        from web.session import get_session, init_user_session

        session = get_session(username)
        if session and session.get("chat"):
            return session

        user_dir = self._user_dir(username)
        user_config = self._load_json(os.path.join(user_dir, "config.json"))
        init_user_session(self.root, user_dir, username, user_config, self.core_config)
        session = get_session(username)
        if not session:
            raise RuntimeError(f"无法初始化用户会话: {username}")
        return session

    def _user_dir(self, username: str) -> str:
        safe = username.strip()
        if not safe or "/" in safe or "\\" in safe or safe in (".", ".."):
            raise ValueError(f"非法用户名: {username}")
        user_dir = os.path.realpath(os.path.join(self.root, "users", safe))
        users_root = os.path.realpath(os.path.join(self.root, "users"))
        # 使用 commonpath 判断路径包含关系，兼容 Windows 大小写和斜杠差异
        try:
            common = os.path.commonpath([user_dir, users_root])
        except ValueError:
            raise ValueError("用户路径越权")
        if common != users_root:
            raise ValueError("用户路径越权")
        if not os.path.isdir(user_dir):
            raise ValueError(f"用户不存在: {username}")
        return user_dir

    def _plan_path(self, username: str, plan_id: str) -> Path | None:
        plan_name = plan_id.strip()
        if plan_name.endswith(".json"):
            plan_name = plan_name[:-5]
        if not plan_name.startswith("plan_") or "/" in plan_name or "\\" in plan_name or ".." in plan_name:
            return None
        return Path(self._user_dir(username)) / "task-plan" / f"{plan_name}.json"

    @staticmethod
    def _load_json(path: str) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _with_source(text: str, source: dict[str, Any] | None) -> str:
        if not source:
            return text
        platform = source.get("platform", "")
        chat_type = source.get("chat_type", "")
        chat_id = source.get("chat_id", "")
        return f"[来自 {platform} {chat_type} chat_id={chat_id}]\n{text}"

    def _invalidate_prompt(self, username: str):
        try:
            from run.prompt_cache import invalidate_prompt_cache
            invalidate_prompt_cache(self._user_dir(username))
        except Exception:
            pass
        try:
            from web.session import get_session
            session = get_session(username)
            if session and session.get("chat"):
                session["chat"].invalidate_prompt()
        except Exception:
            pass
