"""End-to-end integration tests for the bill acceptance flow.

Verifies the full bill acceptance pipeline using MockGPIO + MockCamera +
MockAuthenticator + MockSerial, covering acceptance, rejection,
positioning, safety shutdown, and WebSocket broadcast scenarios.
"""

import pytest
from unittest.mock import AsyncMock

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import BillDenom, BILL_DENOM_VALUES
from app.drivers.bill_controller import BillController
from app.drivers.mock_camera_controller import MockCameraController
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.mock_serial import MockSerial
from app.drivers.serial_manager import SerialManager
from app.ml.mock_authenticator import MockBillAuthenticator
from app.services.bill_acceptor import BillAcceptor, BillAcceptResult
from app.services.machine_status import MachineStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bill_acceptor(
    mock_gpio,
    mock_camera,
    mock_authenticator,
    test_settings,
    machine_status,
    ws_manager,
):
    """Create a BillAcceptor wired to all mock dependencies."""
    serial = MockSerial(port="MOCK_BILL", baudrate=115200, timeout=1.0)
    sm = SerialManager(test_settings)
    bill_controller = BillController(sm)
    # Mock the sort method to avoid needing serial connection
    bill_controller.sort = AsyncMock()
    ba = BillAcceptor(
        mock_gpio,
        mock_camera,
        mock_authenticator,
        bill_controller,
        machine_status,
        ws_manager,
        test_settings,
    )
    return ba


# ---------------------------------------------------------------------------
# 1. Full successful bill acceptance flow
# ---------------------------------------------------------------------------


class TestFullBillAcceptFlow:
    """Tests verifying the happy-path bill acceptance sequence."""

    @pytest.mark.asyncio
    async def test_successful_bill_acceptance(
        self, bill_acceptor, mock_authenticator
    ):
        """A genuine bill should be accepted with correct denomination and value."""
        mock_authenticator.set_accept_next()
        mock_authenticator.set_next_denomination(BillDenom.PHP_100)

        result = await bill_acceptor.accept_bill()

        assert result.success is True
        assert result.denomination == BillDenom.PHP_100
        assert result.value == BILL_DENOM_VALUES[BillDenom.PHP_100]
        assert result.error is None

    @pytest.mark.asyncio
    async def test_bill_acceptance_updates_inventory(
        self, bill_acceptor, mock_authenticator, machine_status
    ):
        """After accepting a bill, the storage count for that denomination
        should be incremented by 1."""
        initial_count = machine_status.snapshot().consumables.bill_storage_counts[
            "PHP_100"
        ]

        mock_authenticator.set_accept_next()
        mock_authenticator.set_next_denomination(BillDenom.PHP_100)

        result = await bill_acceptor.accept_bill()

        assert result.success is True
        updated_count = machine_status.snapshot().consumables.bill_storage_counts[
            "PHP_100"
        ]
        assert updated_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_multiple_bills_accepted(
        self, bill_acceptor, mock_authenticator, machine_status, mock_gpio
    ):
        """Accepting three different bills should succeed each time and update
        inventory for each denomination independently."""
        denominations = [BillDenom.PHP_100, BillDenom.PHP_500, BillDenom.PHP_1000]
        results = []

        for denom in denominations:
            # Reset sensor state so each bill can be positioned
            mock_gpio.set_bill_at_entry(True)
            mock_gpio.set_bill_in_position(True)

            mock_authenticator.set_accept_next()
            mock_authenticator.set_next_denomination(denom)

            result = await bill_acceptor.accept_bill()
            results.append(result)

        # All three should succeed
        for i, result in enumerate(results):
            assert result.success is True, (
                f"Bill {i} ({denominations[i].value}) failed: {result.error}"
            )
            assert result.denomination == denominations[i]
            assert result.value == BILL_DENOM_VALUES[denominations[i]]

        # Verify inventory updated for each
        snap = machine_status.snapshot()
        assert snap.consumables.bill_storage_counts["PHP_100"] >= 1
        assert snap.consumables.bill_storage_counts["PHP_500"] >= 1
        assert snap.consumables.bill_storage_counts["PHP_1000"] >= 1


# ---------------------------------------------------------------------------
# 2. Bill rejection scenarios
# ---------------------------------------------------------------------------


class TestBillRejectionFlow:
    """Tests verifying that counterfeit, unrecognized, and over-capacity bills
    are correctly rejected."""

    @pytest.mark.asyncio
    async def test_counterfeit_bill_rejected(
        self, bill_acceptor, mock_authenticator
    ):
        """A counterfeit (non-genuine) bill should be rejected with
        NOT_GENUINE error."""
        mock_authenticator.set_reject_next()

        result = await bill_acceptor.accept_bill()

        assert result.success is False
        assert result.error == "NOT_GENUINE"
        assert result.auth_confidence is not None

    @pytest.mark.asyncio
    async def test_unknown_denomination_rejected(
        self, bill_acceptor, mock_authenticator
    ):
        """A bill that passes authentication but has an unrecognizable
        denomination should be rejected."""
        mock_authenticator.set_accept_next()
        mock_authenticator.set_unknown_denomination()

        result = await bill_acceptor.accept_bill()

        assert result.success is False
        assert result.error == "UNKNOWN_DENOMINATION"

    @pytest.mark.asyncio
    async def test_storage_full_rejection(
        self, bill_acceptor, mock_authenticator, machine_status, test_settings
    ):
        """When storage is at maximum capacity for a denomination, the bill
        should be rejected with STORAGE_FULL error."""
        # Fill the PHP_100 storage slot to capacity
        capacity = test_settings.storage_slot_capacity
        machine_status.increment_bill_storage("PHP_100", count=capacity)

        mock_authenticator.set_accept_next()
        mock_authenticator.set_next_denomination(BillDenom.PHP_100)

        result = await bill_acceptor.accept_bill()

        assert result.success is False
        assert result.error == "STORAGE_FULL"
        assert result.denomination == BillDenom.PHP_100


# ---------------------------------------------------------------------------
# 3. Bill positioning / sensor scenarios
# ---------------------------------------------------------------------------


class TestBillPositioning:
    """Tests verifying sensor-driven positioning timeouts."""

    @pytest.mark.asyncio
    async def test_bill_not_detected_timeout(
        self, mock_gpio, mock_camera, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """If no bill is detected at the entry sensor, wait_for_bill should
        return False, and accept_bill should time out at positioning."""
        mock_gpio.set_bill_at_entry(False)
        mock_gpio.set_bill_in_position(False)
        mock_gpio.simulate_jam = True  # Prevent auto-position on motor forward

        serial = MockSerial(port="MOCK_BILL", baudrate=115200, timeout=1.0)
        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            mock_camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        result = await acceptor.accept_bill()

        assert result.success is False
        assert result.error == "TIMEOUT_POSITION"

    @pytest.mark.asyncio
    async def test_bill_detected_but_not_positioned(
        self, mock_gpio, mock_camera, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """If a bill is at entry but never reaches the camera position,
        accept_bill should time out during positioning."""
        mock_gpio.set_bill_at_entry(True)
        mock_gpio.set_bill_in_position(False)
        mock_gpio.simulate_jam = True  # Prevent position from ever becoming True

        serial = MockSerial(port="MOCK_BILL", baudrate=115200, timeout=1.0)
        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            mock_camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        result = await acceptor.accept_bill()

        assert result.success is False
        assert result.error == "TIMEOUT_POSITION"


# ---------------------------------------------------------------------------
# 4. Safety shutdown on errors
# ---------------------------------------------------------------------------


class TestBillAcceptorSafetyShutdown:
    """Tests that hardware is put into a safe state on unexpected errors."""

    @pytest.mark.asyncio
    async def test_error_during_acceptance_stops_motor(
        self, mock_gpio, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """If the camera raises an error during capture, the motor should be
        stopped as part of the safe shutdown procedure."""
        mock_gpio.set_bill_at_entry(True)
        mock_gpio.set_bill_in_position(True)

        # Use a camera mock that raises on capture
        camera = MockCameraController()
        camera._initialized = True
        original_capture = camera.capture_frame

        async def _raise_on_capture():
            raise RuntimeError("Camera hardware fault")

        camera.capture_frame = _raise_on_capture

        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        result = await acceptor.accept_bill()

        assert result.success is False
        assert "Camera hardware fault" in result.error
        # Verify motor_stop was called during safe shutdown
        assert "motor_stop" in mock_gpio.call_log

    @pytest.mark.asyncio
    async def test_leds_off_after_error(
        self, mock_gpio, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """After a camera error, both the UV LED and white LED should be
        turned off as part of safe shutdown."""
        mock_gpio.set_bill_at_entry(True)
        mock_gpio.set_bill_in_position(True)

        camera = MockCameraController()
        camera._initialized = True

        async def _raise_on_capture():
            raise RuntimeError("Camera hardware fault")

        camera.capture_frame = _raise_on_capture

        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        await acceptor.accept_bill()

        # After the error, LEDs must be off
        assert mock_gpio.uv_led_state is False
        assert mock_gpio.white_led_state is False
        # Verify the off calls were logged
        assert "uv_led_off" in mock_gpio.call_log
        assert "white_led_off" in mock_gpio.call_log


# ---------------------------------------------------------------------------
# 5. WebSocket broadcast verification
# ---------------------------------------------------------------------------


class TestWebSocketBroadcasts:
    """Tests verifying that correct WebSocket events are broadcast during
    bill acceptance and rejection flows."""

    @pytest.mark.asyncio
    async def test_broadcasts_during_acceptance(
        self, mock_gpio, mock_camera, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """A successful bill acceptance should broadcast BILL_ACCEPTING and
        BILL_STORED events."""
        ws_manager.broadcast = AsyncMock()

        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            mock_camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        mock_authenticator.set_accept_next()
        mock_authenticator.set_next_denomination(BillDenom.PHP_100)

        result = await acceptor.accept_bill()
        assert result.success is True

        # Collect all broadcast call arguments (each call receives a WSEvent object)
        broadcast_events = []
        for call in ws_manager.broadcast.call_args_list:
            args, kwargs = call
            event = args[0] if args else kwargs.get("event")
            broadcast_events.append(event)

        event_types = [e.type.value for e in broadcast_events]

        assert "BILL_ACCEPTING" in event_types, (
            f"Expected BILL_ACCEPTING in broadcasts, got: {event_types}"
        )
        assert "BILL_STORED" in event_types, (
            f"Expected BILL_STORED in broadcasts, got: {event_types}"
        )

    @pytest.mark.asyncio
    async def test_broadcasts_on_rejection(
        self, mock_gpio, mock_camera, mock_authenticator, test_settings,
        machine_status, ws_manager
    ):
        """When a bill is rejected as counterfeit, a BILL_REJECTED event
        should be broadcast."""
        ws_manager.broadcast = AsyncMock()

        sm = SerialManager(test_settings)
        bill_controller = BillController(sm)
        bill_controller.sort = AsyncMock()
        acceptor = BillAcceptor(
            mock_gpio,
            mock_camera,
            mock_authenticator,
            bill_controller,
            machine_status,
            ws_manager,
            test_settings,
        )

        mock_authenticator.set_reject_next()

        result = await acceptor.accept_bill()
        assert result.success is False

        # Collect all broadcast call arguments (each call receives a WSEvent object)
        broadcast_events = []
        for call in ws_manager.broadcast.call_args_list:
            args, kwargs = call
            event = args[0] if args else kwargs.get("event")
            broadcast_events.append(event)

        event_types = [e.type.value for e in broadcast_events]

        assert "BILL_REJECTED" in event_types, (
            f"Expected BILL_REJECTED in broadcasts, got: {event_types}"
        )

        # Verify the rejection reason is included in the payload
        rejected_events = [e for e in broadcast_events if e.type.value == "BILL_REJECTED"]
        assert len(rejected_events) >= 1
        assert rejected_events[0].payload["reason"] == "NOT_GENUINE"
