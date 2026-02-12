import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.status import router as status_router
from app.api.transaction import router as transaction_router

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(status_router)
api_router.include_router(transaction_router)
api_router.include_router(inventory_router)


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            # Handle incoming WS messages from frontend
            try:
                message = json.loads(raw)
                action = message.get("action")
                data = message.get("data", {})
                await _handle_ws_action(websocket, action, data)
            except json.JSONDecodeError:
                pass  # Ignore non-JSON messages (e.g., pings)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def _handle_ws_action(
    websocket: WebSocket, action: str, data: dict
) -> None:
    """Handle incoming WebSocket commands from the frontend."""
    if action is None:
        return

    orchestrator = websocket.app.state.transaction_orchestrator
    settings = websocket.app.state.settings

    if action == "SIMULATE_BILL_INSERT" and settings.use_mock_hardware:
        denom = data.get("denom")
        if denom and orchestrator.has_active_transaction:
            try:
                bill_acceptor = websocket.app.state.bill_acceptor
                from app.core.constants import BillDenom
                from app.models.denominations import value_to_denom_string

                denom_str = value_to_denom_string(denom, "PHP")
                bill_denom = BillDenom(denom_str)
                auth = bill_acceptor._auth
                if hasattr(auth, "set_next_denomination"):
                    auth.set_next_denomination(bill_denom)
                if hasattr(auth, "set_accept_next"):
                    auth.set_accept_next()
                gpio = bill_acceptor._gpio
                if hasattr(gpio, "set_bill_at_entry"):
                    gpio.set_bill_at_entry(True)
                if hasattr(gpio, "set_bill_in_position"):
                    gpio.set_bill_in_position(True)
                await orchestrator.handle_bill_inserted()
            except Exception as e:
                logger.error(f"WS SIMULATE_BILL_INSERT error: {e}")

    elif action == "SIMULATE_COIN_INSERT" and settings.use_mock_hardware:
        denom = data.get("denom", 0)
        if denom and orchestrator.has_active_transaction:
            try:
                await orchestrator.handle_coin_inserted(denom=denom, total=0)
            except Exception as e:
                logger.error(f"WS SIMULATE_COIN_INSERT error: {e}")
