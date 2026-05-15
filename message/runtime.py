"""Background asyncio runtime for message routers."""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from message.agent_service import AgentService
from message.config import load_config
from message.push_queue import PushQueue


class MessageRuntime:
    def __init__(self, root: str, core_config: dict[str, Any]):
        self.root = root
        self.core_config = core_config
        self.config = load_config(root)
        self.enabled = bool(self.config.get("enabled"))
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._tasks: list[asyncio.Task] = []
        self.routers: dict[str, Any] = {}

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if self.is_alive():
            return
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="message-router")
        self._thread.start()
        print("[message] 路由后台线程已启动")

    def stop(self):
        self._stop.set()
        if self._loop:
            self._loop.call_soon_threadsafe(self._cancel_tasks)
        if self._thread:
            self._thread.join(timeout=5)
        print("[message] 路由后台线程已停止")

    def _thread_main(self):
        try:
            asyncio.run(self._amain())
        except Exception as e:
            print(f"[message] 路由运行异常: {e}")

    async def _amain(self):
        self._loop = asyncio.get_running_loop()
        service = AgentService(self.root, self.core_config)

        onebot_cfg = self.config.get("platforms", {}).get("onebot", {})
        if onebot_cfg.get("enabled"):
            from message.routes.onebot import OneBotRouter
            router = OneBotRouter(self.root, self.config, onebot_cfg, service)
            self.routers["onebot"] = router
            self._tasks.append(asyncio.create_task(router.start(), name="onebot-router"))

        if self.config.get("push", {}).get("enabled", True):
            self._tasks.append(asyncio.create_task(self._push_loop(), name="message-push-queue"))

        if not self._tasks:
            print("[message] 未启用任何平台")
            return

        await asyncio.gather(*self._tasks, return_exceptions=True)

    def _cancel_tasks(self):
        for router in self.routers.values():
            if hasattr(router, "stop"):
                router.stop()
        for task in self._tasks:
            task.cancel()

    async def _push_loop(self):
        push_cfg = self.config.get("push", {})
        queue = PushQueue(self.root, push_cfg.get("queue_dir", "message/push_queue"))
        retry_times = int(push_cfg.get("retry_times", 3))
        interval = int(push_cfg.get("retry_interval", 5))

        while not self._stop.is_set():
            for item in queue.pending():
                router = self.routers.get(item.get("platform"))
                if not router:
                    queue.fail(item["id"], f"平台未启用: {item.get('platform')}", retry_times)
                    continue
                if hasattr(router, "is_ready") and not router.is_ready():
                    continue
                try:
                    result = await router.dispatch_push(item)
                    queue.complete(item["id"], result)
                except Exception as e:
                    queue.fail(item["id"], str(e), retry_times)
            await asyncio.sleep(max(1, interval))
