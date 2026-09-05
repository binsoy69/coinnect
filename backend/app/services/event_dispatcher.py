"""Bridges serial events to MachineStatus updates and WebSocket broadcasts.

Consumes from the shared asyncio.Queue populated by serial reader threads.
Runs as an asyncio task during application lifetime.
"""

import asyncio
import asyncio
import logging
from typing import Any

from app.api.ws import ConnectionManager
from app.models.events import WSEvent, WSEventType
from app.models.serial_messages import (
    CoinInEvent,
    CoinSessionPulseEvent,
    DoorStateEvent,
    RFIDEvent,
    ReadyEvent,
    TamperEvent,
)
from app.services.machine_status import MachineStatus
from app.services.inventory_service import InventoryLocation, InventoryService

logger = logging.getLogger(__name__)


class EventDispatcher:
    def __init__(
        self,
        event_queue: asyncio.Queue,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        inventory_service: InventoryService | None = None,
        transaction_orchestrator: Any = None,
        ewallet_orchestrator: Any = None,
        admin_session_service: Any = None,
        coin_controller: Any = None,
        bill_controller: Any = None,
        serial_manager: Any = None,
        bill_acceptor: Any = None,
    ):
        self._queue = event_queue
        self._status = machine_status
        self._ws = ws_manager
        self._inventory = inventory_service
        self._transaction_orchestrator = transaction_orchestrator
        self._ewallet_orchestrator = ewallet_orchestrator
        self._admin_sessions = admin_session_service
        self._coin_controller = coin_controller
        self._bill_controller = bill_controller
        self._serial_manager = serial_manager
        self._bill_acceptor = bill_acceptor
        self._running = False
        self._task = None

    def set_transaction_orchestrator(self, transaction_orchestrator: Any) -> None:
        self._transaction_orchestrator = transaction_orchestrator

    def set_ewallet_orchestrator(self, ewallet_orchestrator: Any) -> None:
        self._ewallet_orchestrator = ewallet_orchestrator

    def set_bill_acceptor(self, bill_acceptor: Any) -> None:
        self._bill_acceptor = bill_acceptor

    def set_bill_controller(self, bill_controller: Any) -> None:
        self._bill_controller = bill_controller

    def set_serial_manager(self, serial_manager: Any) -> None:
        self._serial_manager = serial_manager

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self._running:
            try:
                event_data = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                await self._handle_event(event_data)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event dispatcher error: {e}")

    async def _handle_event(self, event_data: dict) -> None:
        event_type = event_data.get("event")
        controller = event_data.pop("_controller", "UNKNOWN")

        logger.info(
            f"Event from {controller}: {event_type} "
            f"data={event_data}"
        )

        handlers = {
            "COIN_IN": self._handle_coin_in,
            "COIN_SESSION_PULSE": self._handle_coin_session_pulse,
            "TAMPER": self._handle_tamper,
            "RFID": self._handle_rfid,
            "DOOR_STATE": self._handle_door_state,
            "READY": self._handle_ready,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(event_data)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    async def _handle_coin_in(self, data: dict) -> None:
        parsed = CoinInEvent(**data)
        if self._transaction_orchestrator is not None and self._transaction_orchestrator.has_active_transaction:
            logger.warning("Ignoring unscoped legacy coin event during converter transaction")
            return
        coin_denom = f"PHP_{parsed.denom}"
        if self._inventory is not None:
            try:
                await self._inventory.adjust(
                    InventoryLocation.COIN_DISPENSER,
                    coin_denom,
                    1,
                    reason="COIN_ACCEPTED",
                )
            except Exception:
                self._status.set_inventory_consistent(False)
                raise
        else:
            self._status.increment_coin(coin_denom, 1)
        if (
            self._transaction_orchestrator is not None
            and self._transaction_orchestrator.has_active_transaction
        ):
            await self._transaction_orchestrator.handle_coin_inserted(
                denom=parsed.denom,
                total=parsed.total,
            )
        elif self._ewallet_orchestrator is not None:
            await self._ewallet_orchestrator.handle_coin_inserted(parsed.denom)
        await self._ws.broadcast(WSEvent(
            type=WSEventType.COIN_INSERTED,
            payload={"denom": parsed.denom, "total": parsed.total},
        ))

    async def _handle_coin_session_pulse(self, data: dict) -> None:
        parsed = CoinSessionPulseEvent(**data)
        if (
            self._transaction_orchestrator is not None
            and self._transaction_orchestrator.has_active_transaction
        ):
            await self._transaction_orchestrator.handle_coin_session_pulse(
                sid=parsed.sid,
                seq=parsed.seq,
                denom=parsed.denom,
                count=parsed.count,
            )

    async def _handle_tamper(self, data: dict) -> None:
        parsed = TamperEvent(**data)
        self._status.update_security(tamper_active=True, sensor=parsed.sensor)

        stops = []
        if self._bill_acceptor is not None:
            stops.append(self._bill_acceptor.stop_all())
        if self._serial_manager is not None:
            stops.append(self._serial_manager.emergency_stop_all())
        else:
            if self._bill_controller is not None:
                stops.append(self._bill_controller.emergency_stop())
            if self._coin_controller is not None:
                stops.append(self._coin_controller.emergency_stop())
        results = await asyncio.gather(*stops, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Emergency stop failed: %s", result)

        # 3. Active transaction handling
        if (
            self._transaction_orchestrator is not None
            and self._transaction_orchestrator.has_active_transaction
        ):
            await self._transaction_orchestrator.handle_tamper(parsed.sensor)

        await self._ws.broadcast(WSEvent(
            type=WSEventType.TAMPER,
            payload={"sensor": parsed.sensor},
        ))

    async def _handle_rfid(self, data: dict) -> None:
        parsed = RFIDEvent(**data)
        if self._admin_sessions is None:
            logger.warning("Admin session service not injected; ignoring RFID event")
            return
        try:
            session = self._admin_sessions.login_rfid(parsed.uid)
            logger.info(f"RFID admin login success: {parsed.uid} -> session {session.session_id}")
            if self._coin_controller is not None:
                try:
                    await self._coin_controller.security_unlock()
                except Exception as e:
                    logger.error(f"Failed to send security unlock to coin controller: {e}")
            else:
                logger.warning("Coin controller not injected; cannot unlock door")
            
            await self._ws.broadcast(WSEvent(
                type=WSEventType.STATE_CHANGE,
                payload={
                    "mode": "maintenance",
                    "admin_session": {
                        "token": session.token,
                        "session_id": session.session_id,
                        "expires_at": session.expires_at.isoformat(),
                    }
                },
            ))
        except Exception as e:
            logger.error(f"RFID login failed: {e}")

    async def _handle_door_state(self, data: dict) -> None:
        parsed = DoorStateEvent(**data)
        self._status.update_security(locked=parsed.locked)
        await self._ws.broadcast(WSEvent(
            type=WSEventType.STATE_CHANGE,
            payload={"door_locked": parsed.locked},
        ))

    async def _handle_ready(self, data: dict) -> None:
        parsed = ReadyEvent(**data)
        if parsed.controller == "BILL":
            self._status.update_bill_device(
                connection="connected",
                firmware_version=parsed.version,
            )
        elif parsed.controller == "COIN_SECURITY":
            self._status.update_coin_device(
                connection="connected",
                firmware_version=parsed.version,
            )
        await self._ws.broadcast(WSEvent(
            type=WSEventType.DEVICE_CONNECTED,
            payload={
                "controller": parsed.controller,
                "version": parsed.version,
            },
        ))
