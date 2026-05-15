"""OneBot/NapCat reverse WebSocket server — NapCat connects to us."""
from __future__ import annotations

import asyncio
import os
from http import HTTPStatus
from typing import Any

from message.routes.onebot import OneBotRouter


class OneBotServer(OneBotRouter):
    """Reverse WebSocket server mode: NapCat connects to votx-agent.

    Inherits all message handling / command / API logic from OneBotRouter.
    Only overrides start/stop and connection management, plus access_token
    validation per OneBot v11 spec (Authorization: Bearer <token>).
    """

    def __init__(self, root: str, app_config: dict[str, Any], config: dict[str, Any], agent_service):
        self.server_host = config.get("server_host", "127.0.0.1")
        self.server_port = int(config.get("server_port", 8082))
        self.server_path = config.get("server_path", "/ws")
        self._server = None
        super().__init__(root, app_config, config, agent_service)

    def _validate_request(self, headers):
        """OneBot v11: access_token via Authorization: Bearer <token> header."""
        if not self.access_token:
            return None  # no token configured — allow all
        auth = headers.get("Authorization", "")
        expected = f"Bearer {self.access_token}"
        if auth == expected:
            return None  # accept
        print(f"[message:onebot-server] token 校验失败: {auth[:20]}...")
        return HTTPStatus.UNAUTHORIZED, [("Content-Type", "text/plain")], b"token mismatch"

    async def start(self):
        import websockets

        self.running = True
        host = self.server_host
        port = self.server_port
        path_str = f", path={self.server_path}" if self.server_path != "/ws" else ""
        print(f"[message:onebot-server] 反向 WebSocket 监听 ws://{host}:{port}{path_str}")
        try:
            self._server = await websockets.serve(
                self._handler, host, port,
                process_request=self._validate_request,
            )
            await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except OSError as e:
            print(f"[message:onebot-server] 端口 {port} 不可用: {e}")
        finally:
            if self._server:
                self._server.close()
                await self._server.wait_closed()

    def stop(self):
        super().stop()
        if self._server:
            self._server.close()

    async def _handler(self, ws):
        """Handle a single NapCat reverse WebSocket client."""
        if self.ws:
            print("[message:onebot-server] 已有客户端连接，替换为新连接")
            try:
                await self.ws.close()
            except Exception:
                pass
        await self._serve(ws)
