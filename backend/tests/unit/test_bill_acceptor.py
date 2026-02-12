"""Unit tests for the BillAcceptor service.

Tests the full bill acceptance orchestration including sensor polling,
ML authentication, denomination identification, storage checks, and
Arduino sort commands using mock hardware implementations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.core.constants import BillDenom, BILL_DENOM_VALUES
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.mock_camera_controller import MockCameraController
from app.ml.mock_authenticator import MockBillAuthenticator
from app.services.bill_acceptor import BillAcceptor, BillAcceptResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gpio():
    gpio = MockGPIOController()
    gpio.set_bill_at_entry(True)
    gpio.set_bill_in_position(True)
    return gpio


@pytest.fixture
def mock_camera():
    camera = MockCameraController()
    # Pre-initialize so capture_frame() does not raise
    camera._initialized = True
    return camera


@pytest.fixture
def mock_auth():
    return MockBillAuthenticator()


@pytest.fixture
def mock_bill_controller():
    controller = AsyncMock()
    controller.sort = AsyncMock(return_value=MagicMock(slot=3))
    return controller


@pytest.fixture
def mock_ws_manager():
    ws = AsyncMock()
    ws.broadcast = AsyncMock()
    return ws


@pytest.fixture
def mock_machine_status():
    status = MagicMock()
    status.is_storage_full = MagicMock(return_value=False)
    status.increment_bill_storage = MagicMock()
    return status

@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK",
        serial_port_coin="MOCK",
        bill_acceptance_timeout=1,
        bill_position_timeout=0.5,
        led_stabilization_delay=0.0,
        bill_pull_speed=60,
        bill_eject_speed=80,
        bill_store_speed=70,
        bill_store_duration=0.0,
        bill_eject_duration=0.0,
        storage_slot_capacity=100,
    )


@pytest.fixture
def acceptor(
    mock_gpio,
    mock_camera,
    mock_auth,
    mock_bill_controller,
    mock_machine_status,
    mock_ws_manager,
    test_settings,
):
    return BillAcceptor(
        gpio=mock_gpio,
        camera=mock_camera,
        authenticator=mock_auth,
        bill_controller=mock_bill_controller,
        machine_status=mock_machine_status,
        ws_manager=mock_ws_manager,
        settings=test_settings,
    )


# ---------------------------------------------------------------------------
# Tests: accept_bill
# ---------------------------------------------------------------------------


class TestAcceptBillSuccess:
    """Successful bill acceptance (genuine + identified denomination)."""

    @pytest.mark.asyncio
    async def test_successful_acceptance_returns_success(self, acceptor):
        result = await acceptor.accept_bill()

        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_successful_acceptance_returns_denomination(self, acceptor):
        result = await acceptor.accept_bill()

        assert result.denomination == BillDenom.PHP_100
        assert result.value == BILL_DENOM_VALUES[BillDenom.PHP_100]

    @pytest.mark.asyncio
    async def test_successful_acceptance_returns_confidence_scores(self, acceptor):
        result = await acceptor.accept_bill()

        assert result.auth_confidence is not None
        assert result.auth_confidence > 0.0
        assert result.denom_confidence is not None
        assert result.denom_confidence > 0.0

    @pytest.mark.asyncio
    async def test_successful_acceptance_calls_sort(
        self, acceptor, mock_bill_controller
    ):
        await acceptor.accept_bill()

        mock_bill_controller.sort.assert_awaited_once_with(BillDenom.PHP_100)

    @pytest.mark.asyncio
    async def test_successful_acceptance_increments_storage(
        self, acceptor, mock_machine_status
    ):
        await acceptor.accept_bill()

        mock_machine_status.increment_bill_storage.assert_called_once_with(
            BillDenom.PHP_100.value
        )

    @pytest.mark.asyncio
    async def test_successful_acceptance_broadcasts_events(
        self, acceptor, mock_ws_manager
    ):
        await acceptor.accept_bill()

        # Should broadcast at least: BILL_ACCEPTING, BILL_SORTING, BILL_STORED
        assert mock_ws_manager.broadcast.await_count >= 3

    @pytest.mark.asyncio
    async def test_successful_acceptance_with_different_denomination(
        self, acceptor, mock_auth
    ):
        mock_auth.set_next_denomination(BillDenom.PHP_500)

        result = await acceptor.accept_bill()

        assert result.success is True
        assert result.denomination == BillDenom.PHP_500
        assert result.value == BILL_DENOM_VALUES[BillDenom.PHP_500]

    @pytest.mark.asyncio
    async def test_leds_are_off_after_success(self, acceptor, mock_gpio):
        await acceptor.accept_bill()

        assert mock_gpio.uv_led_state is False
        assert mock_gpio.white_led_state is False

class TestAcceptBillNotGenuine:
    """Bill rejected as not genuine by ML authenticator."""

    @pytest.mark.asyncio
    async def test_not_genuine_returns_failure(self, acceptor, mock_auth):
        mock_auth.set_reject_next()

        result = await acceptor.accept_bill()

        assert result.success is False
        assert result.error == "NOT_GENUINE"

    @pytest.mark.asyncio
    async def test_not_genuine_returns_auth_confidence(self, acceptor, mock_auth):
        mock_auth.set_reject_next()
        mock_auth.auth_confidence = 0.35

        result = await acceptor.accept_bill()

        assert result.auth_confidence == pytest.approx(0.35)

    @pytest.mark.asyncio
    async def test_not_genuine_does_not_sort(
        self, acceptor, mock_auth, mock_bill_controller
    ):
        mock_auth.set_reject_next()

        await acceptor.accept_bill()

        mock_bill_controller.sort.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_genuine_does_not_update_storage(
        self, acceptor, mock_auth, mock_machine_status
    ):
        mock_auth.set_reject_next()

        await acceptor.accept_bill()

        mock_machine_status.increment_bill_storage.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_genuine_ejects_bill(self, acceptor, mock_auth, mock_gpio):
        mock_auth.set_reject_next()

        await acceptor.accept_bill()

        # Motor should have been reversed at some point to eject
        assert "motor_reverse(80)" in mock_gpio.call_log


class TestAcceptBillUnknownDenomination:
    """Bill rejected with unknown denomination."""

    @pytest.mark.asyncio
    async def test_unknown_denom_returns_failure(self, acceptor, mock_auth):
        mock_auth.set_unknown_denomination()

        result = await acceptor.accept_bill()

        assert result.success is False
        assert result.error == "UNKNOWN_DENOMINATION"

    @pytest.mark.asyncio
    async def test_unknown_denom_has_no_denomination(self, acceptor, mock_auth):
        mock_auth.set_unknown_denomination()

        result = await acceptor.accept_bill()

        assert result.denomination is None

    @pytest.mark.asyncio
    async def test_unknown_denom_returns_confidence_scores(
        self, acceptor, mock_auth
    ):
        mock_auth.set_unknown_denomination()

        result = await acceptor.accept_bill()

        # Auth confidence should still be present (bill was genuine)
        assert result.auth_confidence is not None
        # Denom confidence may still be present
        assert result.denom_confidence is not None

    @pytest.mark.asyncio
    async def test_unknown_denom_does_not_sort(
        self, acceptor, mock_auth, mock_bill_controller
    ):
        mock_auth.set_unknown_denomination()

        await acceptor.accept_bill()

        mock_bill_controller.sort.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_denom_ejects_bill(
        self, acceptor, mock_auth, mock_gpio
    ):
        mock_auth.set_unknown_denomination()

        await acceptor.accept_bill()

        assert "motor_reverse(80)" in mock_gpio.call_log

class TestAcceptBillPositionTimeout:
    """Bill position timeout (simulate_jam=True)."""

    @pytest.fixture
    def jam_gpio(self):
        gpio = MockGPIOController(simulate_jam=True)
        gpio.set_bill_at_entry(True)
        # Do NOT set bill_in_position -- the jam will prevent it
        return gpio

    @pytest.fixture
    def jam_acceptor(
        self,
        jam_gpio,
        mock_camera,
        mock_auth,
        mock_bill_controller,
        mock_machine_status,
        mock_ws_manager,
        test_settings,
    ):
        return BillAcceptor(
            gpio=jam_gpio,
            camera=mock_camera,
            authenticator=mock_auth,
            bill_controller=mock_bill_controller,
            machine_status=mock_machine_status,
            ws_manager=mock_ws_manager,
            settings=test_settings,
        )

    @pytest.mark.asyncio
    async def test_position_timeout_returns_failure(self, jam_acceptor):
        result = await jam_acceptor.accept_bill()

        assert result.success is False
        assert result.error == "TIMEOUT_POSITION"

    @pytest.mark.asyncio
    async def test_position_timeout_does_not_authenticate(
        self, jam_acceptor, mock_auth
    ):
        await jam_acceptor.accept_bill()

        assert mock_auth.auth_call_count == 0
        assert mock_auth.denom_call_count == 0

    @pytest.mark.asyncio
    async def test_position_timeout_does_not_sort(
        self, jam_acceptor, mock_bill_controller
    ):
        await jam_acceptor.accept_bill()

        mock_bill_controller.sort.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_position_timeout_ejects_bill(self, jam_acceptor, jam_gpio):
        await jam_acceptor.accept_bill()

        # Bill should be ejected after timeout
        assert "motor_reverse(80)" in jam_gpio.call_log

class TestAcceptBillStorageFull:
    """Storage full rejection."""

    @pytest.mark.asyncio
    async def test_storage_full_returns_failure(
        self, acceptor, mock_machine_status
    ):
        mock_machine_status.is_storage_full.return_value = True

        result = await acceptor.accept_bill()

        assert result.success is False
        assert result.error == "STORAGE_FULL"

    @pytest.mark.asyncio
    async def test_storage_full_returns_denomination(
        self, acceptor, mock_machine_status
    ):
        mock_machine_status.is_storage_full.return_value = True

        result = await acceptor.accept_bill()

        # Denomination should still be identified even if storage is full
        assert result.denomination == BillDenom.PHP_100

    @pytest.mark.asyncio
    async def test_storage_full_does_not_sort(
        self, acceptor, mock_machine_status, mock_bill_controller
    ):
        mock_machine_status.is_storage_full.return_value = True

        await acceptor.accept_bill()

        mock_bill_controller.sort.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_storage_full_does_not_update_inventory(
        self, acceptor, mock_machine_status
    ):
        mock_machine_status.is_storage_full.return_value = True

        await acceptor.accept_bill()

        mock_machine_status.increment_bill_storage.assert_not_called()

    @pytest.mark.asyncio
    async def test_storage_full_ejects_bill(
        self, acceptor, mock_machine_status, mock_gpio
    ):
        mock_machine_status.is_storage_full.return_value = True

        await acceptor.accept_bill()

        assert "motor_reverse(80)" in mock_gpio.call_log

# ---------------------------------------------------------------------------
# Tests: wait_for_bill
# ---------------------------------------------------------------------------


class TestWaitForBill:
    """Tests for the wait_for_bill sensor polling method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_bill_detected(self, acceptor, mock_gpio):
        mock_gpio.set_bill_at_entry(True)

        result = await acceptor.wait_for_bill(timeout=1.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self, acceptor, mock_gpio):
        mock_gpio.set_bill_at_entry(False)

        result = await acceptor.wait_for_bill(timeout=0.2)

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_default_timeout_from_settings(
        self, acceptor, mock_gpio, test_settings
    ):
        mock_gpio.set_bill_at_entry(False)

        # Default timeout from settings is 1 second; this should complete
        # without hanging since the timeout is short for testing
        result = await acceptor.wait_for_bill()

        assert result is False

    @pytest.mark.asyncio
    async def test_detects_bill_appearing_after_delay(self):
        """Bill appears at sensor after a small delay using mock built-in delay."""
        gpio = MockGPIOController(bill_at_entry_delay=0.05)
        camera = MockCameraController()
        camera._initialized = True
        auth = MockBillAuthenticator()
        settings = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
            bill_acceptance_timeout=2,
            bill_position_timeout=0.5,
            led_stabilization_delay=0.0,
            bill_store_duration=0.0,
            bill_eject_duration=0.0,
        )
        acceptor = BillAcceptor(
            gpio=gpio,
            camera=camera,
            authenticator=auth,
            bill_controller=AsyncMock(),
            machine_status=MagicMock(),
            ws_manager=AsyncMock(),
            settings=settings,
        )

        result = await acceptor.wait_for_bill(timeout=2.0)

        assert result is True
