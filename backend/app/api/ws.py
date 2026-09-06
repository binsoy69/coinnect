"""WebSocket endpoint and connection manager for real-time event broadcast."""

import logging
from typing import List

from fastapi import WebSocket

from app.models.events import WSEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event: WSEvent, kiosk_session_id: str | None = None) -> None:
        message = event.model_dump_json()
        if not self._connections:
            return

        import asyncio

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                if kiosk_session_id is not None:
                    from datetime import datetime
                    if (getattr(ws.state, "kiosk_session", None) != kiosk_session_id
                        or getattr(ws.state, "kiosk_expires", datetime.min) < datetime.utcnow()):
                        return None
                await ws.send_text(message)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(
            *[_send(ws) for ws in self._connections],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, WebSocket):
                self.disconnect(result)

    @property
    def client_count(self) -> int:
        return len(self._connections)
