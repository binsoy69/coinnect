from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request

from app.api.health import router as health_router
from app.api.status import router as status_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(status_router)


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; frontend sends no commands via WS in Phase 2
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
