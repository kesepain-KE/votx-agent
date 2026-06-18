"""OneBot/NapCat WebSocket router."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import uuid
from typing import Any

from message.identity import IdentityStore
from message.permissions import is_admin, message_mentions_bot, onebot_text, split_message

CRON_RE = re.compile(r"^/cron\s+(list|add|update|delete)\s*(.*)$", re.IGNORECASE | re.DOTALL)
CRON_ADD_RE = re.compile(r"^(daily|once)\s+(\d{2}:\d{2})\s+(.+)$", re.IGNORECASE | re.DOTALL)
CRON_UPDATE_RE = re.compile(r"^(\w+)\s+(time|command|type)\s+(.+)$", re.IGNORECASE | re.DOTALL)
PLAN_RE = re.compile(r"^/plan\s+(list|view|approve|abort)\s*(.*)$", re.IGNORECASE | re.DOTALL)


class OneBotRouter:
    def __init__(self, root: str, app_config: dict[str, Any], config: dict[str, Any], agent_service):
        self.root = root
        self.app_config = app_config
        self.config = config
        self.agent = agent_service
        self.ws_url = config.get("ws_url", "ws://127.0.0.1:3001")
        self.access_token = config.get("access_token", "")
        self.reconnect_interval = int(config.get("reconnect_interval", 5))
        self.api_timeout = int(config.get("api_timeout", 15))
        self.ws = None
        self.running = False
        self.self_id: str | None = None
        self.identity = IdentityStore(root, app_config)
        self._pending: dict[str, asyncio.Future] = {}

    async def start(self):
        self.running = True
        retries = 0
        max_backoff = 300  # 最大重连间隔 5 分钟
        while self.running:
            try:
                await self._connect_once()
                if not self.running:
                    break
                retries += 1
                delay = min(self.reconnect_interval * (2 ** (retries - 1)), max_backoff)
                print(f"[message:onebot] 连接已关闭，{delay}s 后重连 (第 {retries} 次)")
                await self._sleep_before_reconnect(delay)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                retries += 1
                delay = min(self.reconnect_interval * (2 ** (retries - 1)), max_backoff)
                print(f"[message:onebot] 连接断开: {e}，{delay}s 后重连 (第 {retries} 次)")
                await self._sleep_before_reconnect(delay)

    async def _sleep_before_reconnect(self, delay: int):
        """分片 sleep，允许 stop() 尽快打断长退避。"""
        loop = asyncio.get_running_loop()
        end_at = loop.time() + max(0, delay)
        while self.running:
            remaining = end_at - loop.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(1.0, remaining))

    def stop(self):
        self.running = False
        if self.ws:
            try:
                asyncio.create_task(self.ws.close())
            except Exception:
                pass

    def is_ready(self) -> bool:
        return self.ws is not None and not getattr(self.ws, "closed", False)

    async def _connect_once(self):
        import websockets

        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        ping_interval = int(self.config.get("ping_interval", 60))
        ping_timeout = int(self.config.get("ping_timeout", 30))
        kwargs = {"ping_interval": ping_interval, "ping_timeout": ping_timeout, "max_size": 16 * 1024 * 1024}

        # Avoid HTTP_PROXY/HTTPS_PROXY hijacking local NapCat forward WS links.
        local_ws = self.ws_url.startswith(("ws://127.", "wss://127.", "ws://localhost", "wss://localhost"))
        sig = inspect.signature(websockets.connect)
        if local_ws and "proxy" in sig.parameters:
            kwargs["proxy"] = None

        headers_key = "extra_headers" if "extra_headers" in sig.parameters else "additional_headers"
        async with websockets.connect(self.ws_url, **{headers_key: headers}, **kwargs) as ws:
            await self._serve(ws)

    async def _serve(self, ws):
        self.ws = ws
        print(f"[message:onebot] 已连接 NapCat: {self.ws_url}")
        asyncio.create_task(self._load_login_info())
        try:
            async for raw in ws:
                await self._handle_raw(raw)
        finally:
            if self.ws is ws:
                self.ws = None

    async def _load_login_info(self):
        try:
            result = await self.call_api("get_login_info", {})
            data = result.get("data") or result
            user_id = data.get("user_id") or data.get("self_id")
            if user_id:
                self.self_id = str(user_id)
                print(f"[message:onebot] bot self_id={self.self_id}")
        except Exception as e:
            print(f"[message:onebot] 获取登录信息失败: {e}")

    async def _handle_raw(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        echo = msg.get("echo")
        if echo and echo in self._pending:
            # OneBot API responses are matched to outbound requests by echo.
            # Events without echo continue through the normal message path.
            fut = self._pending.pop(echo)
            if not fut.done():
                fut.set_result(msg)
            return

        if msg.get("post_type") == "meta_event":
            return
        if msg.get("post_type") == "message":
            asyncio.create_task(self._handle_message_event(msg))

    async def _handle_message_event(self, msg: dict[str, Any]):
        user_id = str(msg.get("user_id", ""))
        if not user_id or (self.self_id and user_id == self.self_id):
            return

        identity = self.identity.resolve_onebot(user_id)
        if not identity:
            return

        message_type = msg.get("message_type", "private")
        group_id = msg.get("group_id")
        chat_type = "group" if message_type == "group" else "private"
        chat_id = str(group_id if chat_type == "group" else user_id)

        text = onebot_text(msg, self.self_id)
        source = {
            "platform": "onebot",
            "external_id": user_id,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "message_id": msg.get("message_id"),
            "group_id": str(group_id) if group_id else "",
        }

        is_command = text.startswith(("/cron", "/plan"))
        allowed, reason = self._check_access(identity, msg, chat_type, is_command)
        if not allowed:
            if is_command:
                await self._reply(chat_type, chat_id, reason)
            return

        attachments = []
        if not is_command:
            # Attachments are saved to users/<name>/history/file (same pool as Web uploads)
            # and formatted into a structured prompt block by AgentService.
            attachments = await self._download_onebot_files(
                msg, identity["internal_user"], str(user_id), str(msg.get("message_id", "")),
            )

        if not text and not attachments:
            return

        try:
            if is_command:
                response = await asyncio.to_thread(self._handle_command, identity, text, source)
            else:
                response = await asyncio.to_thread(
                    self.agent.chat, identity["internal_user"], text, source, attachments
                )
        except Exception as e:
            response = f"处理失败: {e}"

        await self._reply(chat_type, chat_id, response)

    async def _download_onebot_files(self, msg: dict[str, Any], username: str,
                                      source_id: str = "", message_id: str = "") -> "list[AttachmentRecord]":
        """Download file segments from OneBot message. Returns list of AttachmentRecord dicts.

        NapCat 多字段容错: 依次取 file / file_id / name / url / file_unique / path
        """
        from message.attachments import AttachmentRecord, save_url_attachment, save_base64_attachment, save_local_attachment

        segments = msg.get("message", [])
        if not isinstance(segments, list):
            return []

        # kind 映射
        _KIND_MAP = {"image": "image", "record": "voice", "video": "video", "file": "file"}

        downloaded: list[AttachmentRecord] = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type", "")
            if seg_type not in _KIND_MAP:
                continue
            kind = _KIND_MAP[seg_type]

            data = seg.get("data", {})
            # NapCat 多字段容错: 文件名可能在不同字段
            original_name = (
                data.get("file") or data.get("file_id") or data.get("name")
                or data.get("file_unique") or data.get("path") or ""
            )

            # 1. Try URL download first
            url = data.get("url", "")
            if url:
                record = await save_url_attachment(
                    self.root, username, url, kind=kind,
                    platform="onebot", message_id=message_id, source_id=source_id,
                    filename=original_name,
                )
                if record:
                    downloaded.append(record)
                    continue

            # 2. Fall back to OneBot API (get_image / get_record / get_file)
            file_ref = data.get("file", "") or data.get("file_id", "") or data.get("url", "")
            if not file_ref:
                continue

            try:
                if seg_type == "image":
                    api_name, api_param = "get_image", "file"
                elif seg_type == "record":
                    api_name, api_param = "get_record", "file"
                elif seg_type == "video":
                    api_name, api_param = "get_record", "file"  # 无 get_video，尝试 get_record
                else:
                    api_name, api_param = "get_file", "file_id"

                result = await self.call_api(api_name, {api_param: file_ref})
                b64 = (result.get("data") or result).get("file", "")
                if b64.startswith("base64://"):
                    record = save_base64_attachment(
                        self.root, username, b64[len("base64://"):], kind=kind,
                        platform="onebot", message_id=message_id, source_id=source_id,
                        filename=original_name,
                    )
                    if record:
                        downloaded.append(record)
                elif b64.startswith(("http://", "https://")):
                    record = await save_url_attachment(
                        self.root, username, b64, kind=kind,
                        platform="onebot", message_id=message_id, source_id=source_id,
                        filename=original_name,
                    )
                    if record:
                        downloaded.append(record)
                elif b64:
                    # NapCat 返回容器内文件路径（如 /app/.config/QQ/NapCat/temp/xxx）
                    # 通过 docker volume 映射转为宿主机路径后 copy2
                    record = save_local_attachment(
                        self.root, username, b64, kind=kind,
                        platform="onebot", message_id=message_id, source_id=source_id,
                        filename=original_name or os.path.basename(b64),
                    )
                    if record:
                        downloaded.append(record)
            except Exception as e:
                print(f"[message:onebot] 下载文件失败 {file_ref}: {e}")

        return downloaded

    def _check_access(self, identity: dict[str, Any], msg: dict[str, Any],
                      chat_type: str, is_command: bool) -> tuple[bool, str]:
        if is_command and not self.app_config.get("commands", {}).get("enabled", True):
            return False, "外部命令未启用。"

        if chat_type == "private":
            return True, ""

        group_cfg = self.app_config.get("group_mode", {}).get("qq", {})
        if not group_cfg.get("enabled", True):
            return False, "群聊消息路由未启用。"

        if group_cfg.get("require_at_bot", True) and not message_mentions_bot(msg, self.self_id):
            return False, "群聊中请先 @机器人。"

        if is_command and not self.app_config.get("commands", {}).get("allow_in_group", True):
            return False, "群聊命令未启用。"

        if is_admin(identity):
            return True, ""

        if not is_command and not group_cfg.get("allow_agent_chat", True):
            return False, "群聊普通对话未启用。"

        return True, ""

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

    async def _reply(self, chat_type: str, chat_id: str, text: str):
        limit = int(self.app_config.get("group_mode", {}).get("qq", {}).get("max_message_length", 4096))
        for chunk in split_message(text or "（空回复）", limit):
            if chat_type == "group":
                await self.send_group_msg(int(chat_id), chunk)
            else:
                await self.send_private_msg(int(chat_id), chunk)

    async def send_private_msg(self, user_id: int, message: str):
        return await self.call_api("send_private_msg", {"user_id": user_id, "message": message})

    async def send_group_msg(self, group_id: int, message: str):
        return await self.call_api("send_group_msg", {"group_id": group_id, "message": message})

    async def dispatch_push(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("type") == "message":
            await self._reply(item.get("chat_type", "private"), str(item["chat_id"]), item.get("message", ""))
            return {"ok": True}
        if item.get("type") == "file":
            return await self.send_file(item)
        raise ValueError(f"未知推送类型: {item.get('type')}")

    @staticmethod
    def _to_onebot_file(file_path: str) -> str:
        """读取文件编码为 base64:// URI，避免跨系统路径问题（Win/WSL/Docker 通用）"""
        import base64
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f"base64://{data}"

    async def send_file(self, item: dict[str, Any]) -> dict[str, Any]:
        chat_type = item.get("chat_type", "private")
        file_path = item.get("file_path", "")
        name = item.get("name") or file_path.replace("\\", "/").split("/")[-1]
        ob_file = self._to_onebot_file(file_path)
        if chat_type == "group":
            return await self.call_api("upload_group_file", {
                "group_id": int(item["chat_id"]),
                "file": ob_file,
                "name": name,
            })
        return await self.call_api("upload_private_file", {
            "user_id": int(item["chat_id"]),
            "file": ob_file,
            "name": name,
        })

    async def call_api(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.ws:
            raise RuntimeError("OneBot WebSocket 未连接")
        echo = f"{action}_{uuid.uuid4().hex}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[echo] = fut
        payload = {"action": action, "params": params, "echo": echo}
        # NapCat forward WS is full-duplex: send API calls on the same socket
        # that receives events, then wait for the matching echo response.
        await self.ws.send(json.dumps(payload, ensure_ascii=False))
        try:
            response = await asyncio.wait_for(fut, timeout=self.api_timeout)
        finally:
            self._pending.pop(echo, None)
        status = response.get("status")
        retcode = response.get("retcode", 0)
        if status in ("failed", "error") or retcode not in (0, None):
            raise RuntimeError(response.get("message") or response.get("wording") or str(response))
        return response
