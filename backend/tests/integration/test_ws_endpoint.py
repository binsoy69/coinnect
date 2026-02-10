import pytest

from app.main import create_app
from app.models.events import WSEvent, WSEventType


@pytest.fixture
def app():
    return create_app()


class TestWebSocketEndpoint:
    def test_ws_connect_and_receive_broadcast(self, app):
        """Test that a WebSocket client can connect and receive broadcast events."""
        from starlette.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/ws") as ws:
                # Broadcast an event via the connection manager
                ws_manager = app.state.ws_manager
                event = WSEvent(
                    type=WSEventType.COIN_INSERTED,
                    payload={"denom": 5, "total": 5},
                )

                # Run the async broadcast on the TestClient's event loop
                portal = client.portal
                assert portal is not None
                portal.call(ws_manager.broadcast, event)

                data = ws.receive_json()
                assert data["type"] == "COIN_INSERTED"
                assert data["payload"]["denom"] == 5
