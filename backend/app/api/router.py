import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request

from app.api.forex import router as forex_router
from app.api.admin import router as admin_router
from app.api.ewallet import router as ewallet_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.status import router as status_router
from app.api.transaction import router as transaction_router
from app.api.kiosk_access import require_local
from fastapi import HTTPException

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api/v1")
async def local_customer_access(request: Request):
    require_local(request)

api_router.include_router(health_router)
api_router.include_router(status_router, dependencies=[Depends(local_customer_access)])
api_router.include_router(transaction_router, dependencies=[Depends(local_customer_access)])
api_router.include_router(inventory_router, dependencies=[Depends(local_customer_access)])
api_router.include_router(forex_router, dependencies=[Depends(local_customer_access)])
api_router.include_router(ewallet_router)
api_router.include_router(admin_router, dependencies=[Depends(local_customer_access)])


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        require_local(websocket)
    except HTTPException:
        await websocket.close(code=1008)
        return
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

    if action == "AUTH_EWALLET":
        import hashlib
        from datetime import datetime
        from app.models.db_models import KioskSession
        token = str(data.get("token", ""))
        session_id = hashlib.sha256(token.encode()).hexdigest()
        async with websocket.app.state.db_session_factory() as session:
            customer = await session.get(KioskSession, session_id)
            if not token or customer is None or customer.expires_at < datetime.utcnow():
                websocket.state.kiosk_session = None
                return
            websocket.state.kiosk_session = session_id
            websocket.state.kiosk_expires = customer.expires_at
        return

    orchestrator = websocket.app.state.transaction_orchestrator
    settings = websocket.app.state.settings

    simulation_enabled = (
        settings.environment.lower() != "production"
        and settings.use_mock_hardware
        and settings.use_mock_serial
    )

    if action == "SIMULATE_BILL_INSERT" and simulation_enabled:
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
                await orchestrator.handle_bill_inserted()
            except Exception as e:
                logger.error(f"WS SIMULATE_BILL_INSERT error: {e}")

    elif action == "SIMULATE_COIN_INSERT" and simulation_enabled:
        denom = data.get("denom", 0)
        if denom and orchestrator.has_active_transaction:
            try:
                await orchestrator.handle_coin_inserted(denom=denom, total=0)
            except Exception as e:
                logger.error(f"WS SIMULATE_COIN_INSERT error: {e}")

    elif action == "SIMULATE_FOREX_BILL_INSERT" and simulation_enabled:
        denom = data.get("denom")
        currency = data.get("currency", "PHP")
        forex_orchestrator = websocket.app.state.forex_transaction_orchestrator
        if denom and forex_orchestrator.has_active_transaction:
            try:
                bill_acceptor = websocket.app.state.bill_acceptor
                from app.core.constants import BillDenom
                from app.models.denominations import value_to_denom_string

                denom_str = value_to_denom_string(denom, currency)
                bill_denom = BillDenom(denom_str)
                auth = bill_acceptor._auth
                if hasattr(auth, "set_next_denomination"):
                    auth.set_next_denomination(bill_denom)
                if hasattr(auth, "set_accept_next"):
                    auth.set_accept_next()
                gpio = bill_acceptor._gpio
                if hasattr(gpio, "set_bill_at_entry"):
                    gpio.set_bill_at_entry(True)
                await forex_orchestrator.handle_bill_inserted()
            except Exception as e:
                logger.error(f"WS SIMULATE_FOREX_BILL_INSERT error: {e}")
