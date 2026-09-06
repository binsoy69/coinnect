from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.api.ws import ConnectionManager
from app.models.events import WSEvent, WSEventType


@pytest.mark.asyncio
async def test_private_wallet_events_reach_only_current_unexpired_session():
    manager = ConnectionManager()
    owner = SimpleNamespace(state=SimpleNamespace(kiosk_session="owner", kiosk_expires=datetime.utcnow()+timedelta(minutes=1)), send_text=AsyncMock())
    other = SimpleNamespace(state=SimpleNamespace(kiosk_session="other", kiosk_expires=datetime.utcnow()+timedelta(minutes=1)), send_text=AsyncMock())
    expired = SimpleNamespace(state=SimpleNamespace(kiosk_session="owner", kiosk_expires=datetime.utcnow()-timedelta(seconds=1)), send_text=AsyncMock())
    manager._connections = [owner, other, expired]
    await manager.broadcast(WSEvent(type=WSEventType.EWALLET_STATE_CHANGED, payload={"transaction_id": "private"}), kiosk_session_id="owner")
    owner.send_text.assert_awaited_once()
    other.send_text.assert_not_awaited()
    expired.send_text.assert_not_awaited()
