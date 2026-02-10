"""Bridges serial events to MachineStatus updates and WebSocket broadcasts.

Consumes from the shared asyncio.Queue populated by serial reader threads.
Runs as an asyncio task during application lifetime.
"""

import asyncio
import logging

from app.api.ws import ConnectionManager
from app.models.events import WSEvent, WSEventType
from app.models.serial_messages import (
    CoinInEvent,
    DoorStateEvent,
    KeypadEvent,
    ReadyEvent,
    TamperEvent,
)
from app.services.machine_status import MachineStatus

logger = logging.getLogger(__name__)


class EventDispatcher:
    def __init__(
        self,
        event_queue: asyncio.Queue,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
    ):
        self._queue = event_queue
        self._status = machine_status
        self._ws = ws_manager
        self._running = False
        self._task = None

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
            "TAMPER": self._handle_tamper,
            "KEYPAD": self._handle_keypad,
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
        self._status.increment_coin(f"PHP_{parsed.denom}", 1)
        await self._ws.broadcast(WSEvent(
            type=WSEventType.COIN_INSERTED,
            payload={"denom": parsed.denom, "total": parsed.total},
        ))

    async def _handle_tamper(self, data: dict) -> None:
        parsed = TamperEvent(**data)
        self._status.update_security(tamper_active=True, sensor=parsed.sensor)
        await self._ws.broadcast(WSEvent(
            type=WSEventType.TAMPER,
            payload={"sensor": parsed.sensor},
        ))

    async def _handle_keypad(self, data: dict) -> None:
        parsed = KeypadEvent(**data)
        logger.info(f"Keypad key pressed: {parsed.key}")

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
