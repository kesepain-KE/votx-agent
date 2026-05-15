"""Telegram Bot API 长轮询路由 (getUpdates)."""
from __future__ import annotations

import asyncio
import json
import re
import urllib.request
from typing import Any

from message.identity import IdentityStore
from message.permissions import is_admin, split_message

CRON_RE = re.compile(r"^/cron\s+(list|add|update|delete)\s*(.*)$", re.IGNORECASE | re.DOTALL)
CRON_ADD_RE = re.compile(r"^(daily|once)\s+(\d{2}:\d{2})\s+(.+)$", re.IGNORECASE | re.DOTALL)
CRON_UPDATE_RE = re.compile(r"^(\S+)\s+(time|command|type)\s+(.+)$", re.IGNORECASE | re.DOTALL)
PLAN_RE = re.compile(r"^/plan\s+(list|view|approve|abort)\s*(.*)$", re.IGNORECASE | re.DOTALL)
MENTION_RE = re.compile(r"@(\w+)")


class TelegramRouter:
    def __init__(self, root: str, app_config: dict[str, Any], config: dict[str, Any], agent_service):
        self.root = root
        self.app_config = app_config
        self.config = config
        self.agent = agent_service
        self.bot_token = str(config.get("bot_token", "")).strip()
        self.poll_interval = int(config.get("poll_interval", 2))
        self.api_timeout = int(config.get("api_timeout", 30))
        self.running = False
        self.identity = IdentityStore(root, app_config)
        self._me: dict[str, Any] = {}
        self._bot_username = ""

    async def start(self):
        if not self.bot_token:
            print("[message:telegram] bot_token 未配置，跳过启动")
            return
        self.running = True
        # 获取 bot 信息
        try:
            result = await self._api("getMe", {})
            self._me = result.get("result", {})
            self._bot_username = self._me.get("username", "")
            print(f"[message:telegram] bot @{self._bot_username} 已就绪")
        except Exception as e:
            print(f"[message:telegram] getMe 失败: {e}，请检查 bot_token")
            self.running = False
            return

        # 清除 webhook（getUpdates 和 webhook 互斥）
        try:
            await self._api("deleteWebhook", {"drop_pending_updates": False})
        except Exception:
            pass

        print(f"[message:telegram] 开始长轮询（间隔 {self.poll_interval}s）")
        await self._poll_loop()

    def stop(self):
        self.running = False

    def is_ready(self) -> bool:
        return self.running and bool(self._bot_username)

    # ── 轮询 ───────────────────────────────────────

    async def _poll_loop(self):
        offset = 0
        while self.running:
            try:
                result = await self._api("getUpdates", {
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                })
                if result.get("ok"):
                    for update in result.get("result", []):
                        # Advancing offset before task dispatch prevents the
                        # same update from replaying after a handler exception.
                        offset = max(offset, update["update_id"] + 1)
                        asyncio.create_task(self._handle_update(update))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[message:telegram] 轮询异常: {e}，{self.poll_interval}s 后重试")
                await asyncio.sleep(self.poll_interval)

    # ── 更新处理 ───────────────────────────────────

    async def _handle_update(self, update: dict[str, Any]):
        try:
            if "message" in update:
                await self._handle_message(update["message"])
            elif "edited_message" in update:
                await self._handle_message(update["edited_message"], edited=True)
            elif "callback_query" in update:
                await self._handle_callback_query(update["callback_query"])
        except Exception as e:
            print(f"[message:telegram] 处理更新异常: {e}")

    async def _handle_message(self, msg: dict[str, Any], edited: bool = False):
        if edited:
            return  # 暂时忽略编辑消息

        chat = msg.get("chat", {})
        user = msg.get("from", {})
        if not user or not chat:
            return

        user_id = str(user.get("id", ""))
        chat_type = chat.get("type", "private")
        chat_id = str(chat.get("id", ""))

        # 忽略机器人自己的消息
        if user.get("is_bot"):
            return

        # 身份解析（需要在下载文件前获取 username）
        identity = self.identity.resolve_telegram(user_id, chat_id)
        if not identity:
            return

        # Store Telegram attachments as local files before invoking the Agent;
        # downstream tools see the same users/<name>/download paths as Web UI.
        downloaded = await self._download_telegram_files(msg, identity["internal_user"])

        text = self._extract_text(msg)
        if downloaded:
            file_lines = "\n".join(f"[本地文件: {p}]" for p in downloaded)
            text = f"{file_lines}\n{text}" if text else file_lines
        if not text:
            return

        is_command = text.startswith(("/cron", "/plan"))
        allowed, reason = self._check_access(identity, msg, chat_type, is_command)
        if not allowed:
            if is_command:
                await self._reply(chat_id, reason)
            return

        source = {
            "platform": "telegram",
            "external_id": user_id,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "message_id": msg.get("message_id"),
            "group_id": chat_id if chat_type in ("group", "supergroup") else "",
        }

        try:
            if is_command:
                response = await asyncio.to_thread(self._handle_command, identity, text, source)
            else:
                await self._send_chat_action(chat_id, "typing")
                response = await asyncio.to_thread(
                    self.agent.chat, identity["internal_user"], text, source
                )
        except Exception as e:
            response = f"处理失败: {e}"

        await self._reply(chat_id, response)

    async def _download_telegram_files(self, msg: dict[str, Any], username: str) -> list[str]:
        """Download file attachments from Telegram message. Returns list of local paths."""
        from message.routes._download import download_url

        downloaded: list[str] = []

        # Collect file_ids from all attachment types
        file_ids: list[tuple[str, str]] = []  # (file_id, name)

        for key in ("document", "audio", "video", "voice"):
            attach = msg.get(key)
            if isinstance(attach, dict) and attach.get("file_id"):
                name = attach.get("file_name") or ""
                file_ids.append((attach["file_id"], name))

        photos = msg.get("photo")
        if isinstance(photos, list) and photos:
            # 取最大尺寸的 photo
            largest = max(photos, key=lambda p: p.get("width", 0) * p.get("height", 0))
            if largest.get("file_id"):
                file_ids.append((largest["file_id"], "photo.jpg"))

        for file_id, name in file_ids:
            try:
                # 1. 获取文件路径
                gf = await self._api("getFile", {"file_id": file_id})
                file_path = gf.get("result", {}).get("file_path", "")
                if not file_path:
                    continue
                # 2. 下载文件
                url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                local = await download_url(self.root, username, url, name)
                if local:
                    downloaded.append(local)
            except Exception as e:
                print(f"[message:telegram] 下载文件失败 {file_id}: {e}")

        return downloaded

    async def _handle_callback_query(self, cq: dict[str, Any]):
        cq_id = cq.get("id", "")
        user = cq.get("from", {})
        user_id = str(user.get("id", ""))
        data = cq.get("data", "")
        message = cq.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", user_id)) if message else user_id

        if not cq_id:
            return

        # 先确认回调查询
        try:
            await self._api("answerCallbackQuery", {"callback_query_id": cq_id})
        except Exception:
            pass

        if not data:
            return

        identity = self.identity.resolve_telegram(user_id, chat_id)
        if not identity:
            return

        source = {
            "platform": "telegram",
            "external_id": user_id,
            "chat_type": "callback",
            "chat_id": chat_id,
            "message_id": message.get("message_id"),
        }

        try:
            response = await asyncio.to_thread(
                self.agent.chat, identity["internal_user"], f"[callback: {data}]", source
            )
            if response and response != "已处理，但没有生成文本回复。":
                await self._reply(chat_id, response)
        except Exception as e:
            print(f"[message:telegram] 回调查询处理失败: {e}")

    # ── 权限 ───────────────────────────────────────

    def _check_access(self, identity: dict[str, Any], msg: dict[str, Any],
                      chat_type: str, is_command: bool) -> tuple[bool, str]:
        if is_command and not self.app_config.get("commands", {}).get("enabled", True):
            return False, "外部命令未启用。"

        if chat_type == "private":
            return True, ""

        group_cfg = self.app_config.get("group_mode", {}).get("telegram", {})
        if not group_cfg.get("enabled", True):
            return False, "群聊消息路由未启用。"

        if group_cfg.get("require_at_bot", True) and not _mentions_bot(msg, self._bot_username):
            return False, "群聊中请 @机器人。"

        if is_command and not self.app_config.get("commands", {}).get("allow_in_group", True):
            return False, "群聊命令未启用。"

        if is_admin(identity):
            return True, ""

        if not is_command and not group_cfg.get("allow_agent_chat", True):
            return False, "群聊普通对话未启用。"

        return True, ""

    # ── 命令处理（复用 OneBot 逻辑）─────────────────

    def _handle_command(self, identity: dict[str, Any], text: str, source: dict[str, Any]) -> str:
        username = identity["internal_user"]
        cron_match = CRON_RE.match(text)
        if cron_match:
            return self._handle_cron(username, cron_match.group(1).lower(), cron_match.group(2).strip(), source)

        plan_match = PLAN_RE.match(text)
        if plan_match:
            return self._handle_plan(username, plan_match.group(1).lower(), plan_match.group(2).strip(), source)

        return "命令格式错误。可用: /cron list|add|update|delete 或 /plan list|view|approve|abort"

    def _handle_cron(self, username: str, action: str, args: str, source: dict[str, Any]) -> str:
        if action == "list":
            tasks = self.agent.list_tasks(username)
            if not tasks:
                return "当前没有定时任务。"
            lines = [f"定时任务列表（{len(tasks)} 个）:"]
            for task in tasks:
                lines.append(f"- [{task.get('id')}] {task.get('type')} {task.get('time')} — {task.get('command')}")
            return "\n".join(lines)

        if action == "add":
            match = CRON_ADD_RE.match(args)
            if not match:
                return "格式错误: /cron add daily|once HH:MM 命令内容"
            task_type, time_text, command = match.group(1).lower(), match.group(2), match.group(3).strip()
            task = self.agent.create_task(username, task_type, time_text, command, source)
            return f"定时任务已创建\nID: {task['id']}\n类型: {task['type']}\n时间: {task['time']}\n命令: {task['command']}"

        if action == "update":
            match = CRON_UPDATE_RE.match(args)
            if not match:
                return "格式错误: /cron update <task_id> time|command|type <新值>"
            task_id, field, value = match.group(1), match.group(2).lower(), match.group(3).strip()
            updated = self.agent.update_task(username, task_id, {field: value})
            if not updated:
                return f"未找到任务: {task_id}"
            return f"任务已更新\nID: {updated['id']}\n类型: {updated['type']}\n时间: {updated['time']}\n命令: {updated['command']}"

        if action == "delete":
            task_id = args.strip()
            if not task_id:
                return "格式错误: /cron delete <task_id>"
            if not self.agent.delete_task(username, task_id):
                return f"未找到任务: {task_id}"
            return f"任务已删除: {task_id}"

        return "未知 cron 命令。"

    def _handle_plan(self, username: str, action: str, args: str, source: dict[str, Any]) -> str:
        if action == "list":
            plans = self.agent.list_plans(username)
            if not plans:
                return "当前没有任务计划。"
            lines = [f"任务计划列表（{len(plans)} 个）:"]
            for plan in plans:
                steps = plan.get("steps", [])
                done = sum(1 for step in steps if step.get("status") == "completed")
                lines.append(f"- [{plan.get('id')}] {plan.get('title', '?')} ({done}/{len(steps)}) — {plan.get('status')}")
            return "\n".join(lines)

        if action == "view":
            plan_id = args.strip()
            if not plan_id:
                return "格式错误: /plan view <plan_id>"
            plan = self.agent.view_plan(username, plan_id)
            if not plan:
                return f"未找到计划: {plan_id}"
            lines = [
                f"计划: {plan.get('title', '?')}",
                f"ID: {plan.get('id', plan_id)}",
                f"状态: {plan.get('status', '?')}",
                f"描述: {plan.get('description', '')}",
                "步骤:",
            ]
            for step in plan.get("steps", []):
                lines.append(f"- [{step.get('status')}] {step.get('id')}: {step.get('description')}")
            return "\n".join(lines)

        if action == "approve":
            plan_id = args.strip()
            if not plan_id:
                return "格式错误: /plan approve <plan_id>"
            if not self.agent.approve_plan(username, plan_id):
                return f"未找到计划: {plan_id}"
            result = self.agent.chat(username, f"任务计划 {plan_id} 已批准，请继续执行该计划。", source)
            return f"计划已批准，开始执行: {plan_id}\n\n{result}"

        if action == "abort":
            plan_id = args.strip()
            if not plan_id:
                return "格式错误: /plan abort <plan_id>"
            if not self.agent.abort_plan(username, plan_id):
                return f"未找到计划: {plan_id}"
            return f"计划已中止: {plan_id}"

        return "未知 plan 命令。"

    # ── 消息收发 ───────────────────────────────────

    @staticmethod
    def _extract_text(msg: dict[str, Any]) -> str:
        text = msg.get("text") or msg.get("caption") or ""
        if isinstance(text, str):
            return text.strip()
        return ""

    async def _reply(self, chat_id: str, text: str):
        limit = int(self.app_config.get("group_mode", {}).get("telegram", {}).get("max_message_length", 4096))
        for chunk in split_message(text or "[empty]", limit):
            await self._api("sendMessage", {
                "chat_id": _to_int(chat_id),
                "text": chunk,
                "disable_web_page_preview": True,
            })
            if len(chunk) > 100:
                await asyncio.sleep(0.3)  # 避免速率限制

    async def _send_chat_action(self, chat_id: str, action: str = "typing"):
        try:
            await self._api("sendChatAction", {"chat_id": _to_int(chat_id), "action": action})
        except Exception:
            pass

    # ── Push 队列 ──────────────────────────────────

    async def dispatch_push(self, item: dict[str, Any]) -> dict[str, Any]:
        push_type = item.get("type", "message")
        chat_id = str(item.get("chat_id", ""))
        if push_type == "message":
            await self._reply(chat_id, item.get("message", ""))
            return {"ok": True}
        if push_type == "file":
            return await self._send_file(item)
        raise ValueError(f"未知推送类型: {push_type}")

    async def _send_file(self, item: dict[str, Any]) -> dict[str, Any]:
        chat_id = str(item.get("chat_id", ""))
        file_path = item.get("file_path", "")
        caption = item.get("message", "")
        if not file_path:
            raise ValueError("缺少 file_path")
        # 使用 sendDocument 发送文件（multipart/form-data）
        await self._upload_file("sendDocument", chat_id, file_path, caption)
        return {"ok": True}

    async def _upload_file(self, method: str, chat_id: str, file_path: str, caption: str = ""):
        """通过 multipart/form-data 上传文件到 Telegram。"""
        import mimetypes
        import os

        def _sync_upload():
            boundary = "votx-telegram-upload-boundary"
            filename = os.path.basename(file_path)
            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

            with open(file_path, "rb") as f:
                file_data = f.read()

            body = b""
            # chat_id
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            body += f"{chat_id}\r\n".encode()
            # document
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
            body += f"Content-Type: {mime_type}\r\n\r\n".encode()
            body += file_data
            body += b"\r\n"
            # caption (if any)
            if caption:
                body += f"--{boundary}\r\n".encode()
                body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
                body += caption.encode("utf-8")
                body += b"\r\n"
            body += f"--{boundary}--\r\n".encode()

            url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))

        result = await asyncio.to_thread(_sync_upload)
        if not result.get("ok"):
            raise RuntimeError(f"上传失败: {result.get('description', 'unknown')}")
        return result

    # ── API 调用 ───────────────────────────────────

    async def _api(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                result = await self._api_raw(method, params)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue

            if result.get("ok"):
                return result

            error_code = result.get("error_code", 0)
            description = result.get("description", "unknown")
            if error_code == 429:
                retry_after = result.get("parameters", {}).get("retry_after", 5)
                print(f"[message:telegram] 速率限制，等待 {retry_after}s")
                await asyncio.sleep(retry_after)
                continue
            raise RuntimeError(f"Telegram API ({method}): {description} (code={error_code})")

        raise RuntimeError(f"Telegram API 调用失败 ({method}): {last_error}")

    async def _api_raw(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        def _call():
            url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
            clean = {k: v for k, v in params.items() if v is not None}
            data = json.dumps(clean, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "votx-agent/1.0")
            try:
                with urllib.request.urlopen(req, timeout=self.api_timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except OSError as e:
                # getUpdates 长轮询超时是正常行为，返回空结果
                # 其他 API 的超时向上抛出让 _api 重试
                if method == "getUpdates" and "timed out" in str(e).lower():
                    return {"ok": True, "result": []}
                raise
        return await asyncio.to_thread(_call)


# ── 辅助函数 ──────────────────────────────────────

def _mentions_bot(msg: dict[str, Any], bot_username: str) -> bool:
    """检测 Telegram 消息中是否 @了 bot。"""
    if not bot_username:
        return False
    text = msg.get("text") or msg.get("caption") or ""
    entities = msg.get("entities") or msg.get("caption_entities") or []

    for entity in entities:
        if entity.get("type") == "mention":
            offset = entity.get("offset", 0)
            length = entity.get("length", 0)
            mention = text[offset:offset + length] if offset + length <= len(text) else ""
            if mention.lower() == f"@{bot_username.lower()}":
                return True

    # 兜底：检查文本中是否包含 @bot_username
    return f"@{bot_username}" in text


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
