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

    async def broadcast(self, event: WSEvent) -> None:
        message = event.model_dump_json()
        stale = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)
