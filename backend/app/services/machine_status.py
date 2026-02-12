"""Thread-safe singleton store for all device state.

Mutated from serial reader threads; produces immutable snapshots for
the API/WebSocket layer via snapshot().
"""

import logging
import threading
from datetime import datetime
from typing import Callable, List, Optional

from app.core.config import Settings
from app.models.machine import (
    ConsumablesState,
    DeviceConnectionState,
    DeviceStatus,
    MachineStateSnapshot,
    SecurityState,
    SorterState,
)

logger = logging.getLogger(__name__)


class MachineStatus:
    def __init__(self, settings: Settings):
        self._lock = threading.Lock()
        self._settings = settings

        self._bill_device = DeviceStatus()
        self._coin_device = DeviceStatus()
        self._sorter = SorterState()
        self._security = SecurityState()
        self._consumables = ConsumablesState()

        self._on_change: Optional[Callable] = None

    def snapshot(self) -> MachineStateSnapshot:
        with self._lock:
            return MachineStateSnapshot(
                bill_device=self._bill_device.model_copy(),
                coin_device=self._coin_device.model_copy(),
                sorter=self._sorter.model_copy(),
                security=self._security.model_copy(),
                consumables=self._consumables.model_copy(),
                timestamp=datetime.utcnow(),
            )

    def set_on_change(self, callback: Callable) -> None:
        self._on_change = callback

    # --- Device connection ---

    def update_bill_device(
        self,
        connection: Optional[str] = None,
        firmware_version: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if connection is not None:
                self._bill_device.connection = DeviceConnectionState(connection)
            if firmware_version is not None:
                self._bill_device.firmware_version = firmware_version
                self._bill_device.controller_type = "BILL"
            if last_error is not None:
                self._bill_device.last_error = last_error
            self._bill_device.last_ping = datetime.utcnow()
        self._notify_change()

    def update_coin_device(
        self,
        connection: Optional[str] = None,
        firmware_version: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if connection is not None:
                self._coin_device.connection = DeviceConnectionState(connection)
            if firmware_version is not None:
                self._coin_device.firmware_version = firmware_version
                self._coin_device.controller_type = "COIN_SECURITY"
            if last_error is not None:
                self._coin_device.last_error = last_error
            self._coin_device.last_ping = datetime.utcnow()
        self._notify_change()

    # --- Sorter state ---

    def update_sorter(
        self,
        homed: Optional[bool] = None,
        position: Optional[int] = None,
        slot: Optional[int] = None,
    ) -> None:
        with self._lock:
            if homed is not None:
                self._sorter.homed = homed
            if position is not None:
                self._sorter.current_position = position
            if slot is not None:
                self._sorter.current_slot = slot
        self._notify_change()

    # --- Security state ---

    def update_security(
        self,
        locked: Optional[bool] = None,
        tamper_active: Optional[bool] = None,
        sensor: Optional[str] = None,
    ) -> None:
        with self._lock:
            if locked is not None:
                self._security.locked = locked
            if tamper_active is not None:
                self._security.tamper_active = tamper_active
            if sensor is not None:
                self._security.last_tamper_sensor = sensor
                self._security.last_tamper_time = datetime.utcnow()
        self._notify_change()

    # --- Consumables ---

    def increment_bill_storage(self, denom: str, count: int = 1) -> None:
        with self._lock:
            # Map full denom to storage key (USD_* -> USD, EUR_* -> EUR)
            storage_key = denom
            if denom.startswith("USD_"):
                storage_key = "USD"
            elif denom.startswith("EUR_"):
                storage_key = "EUR"

            if storage_key in self._consumables.bill_storage_counts:
                self._consumables.bill_storage_counts[storage_key] += count
                self._check_storage_alerts()
        self._notify_change()

    def decrement_bill_dispenser(self, denom: str, count: int = 1) -> None:
        with self._lock:
            if denom in self._consumables.bill_dispenser_counts:
                self._consumables.bill_dispenser_counts[denom] = max(
                    0, self._consumables.bill_dispenser_counts[denom] - count
                )
                self._check_dispenser_alerts()
        self._notify_change()

    def increment_coin(self, denom: str, count: int = 1) -> None:
        with self._lock:
            if denom in self._consumables.coin_counts:
                self._consumables.coin_counts[denom] += count
        self._notify_change()

    def decrement_coin(self, denom: str, count: int = 1) -> None:
        with self._lock:
            if denom in self._consumables.coin_counts:
                self._consumables.coin_counts[denom] = max(
                    0, self._consumables.coin_counts[denom] - count
                )
                self._check_coin_alerts()
        self._notify_change()

    def set_dispenser_counts(self, counts: dict) -> None:
        """Bulk-set dispenser inventory (e.g., after maintenance)."""
        with self._lock:
            for denom, count in counts.items():
                if denom in self._consumables.bill_dispenser_counts:
                    self._consumables.bill_dispenser_counts[denom] = count
            self._check_dispenser_alerts()
        self._notify_change()

    def set_coin_counts(self, counts: dict) -> None:
        """Bulk-set coin inventory."""
        with self._lock:
            for denom, count in counts.items():
                if denom in self._consumables.coin_counts:
                    self._consumables.coin_counts[denom] = count
            self._check_coin_alerts()
        self._notify_change()

    def get_alerts(self) -> List[str]:
        with self._lock:
            return list(self._consumables.alerts)

    def is_storage_full(self, denom: str) -> bool:
        """Check if the storage slot for the given denomination is at capacity."""
        with self._lock:
            storage_key = denom
            if denom.startswith("USD_"):
                storage_key = "USD"
            elif denom.startswith("EUR_"):
                storage_key = "EUR"
            count = self._consumables.bill_storage_counts.get(storage_key, 0)
            return count >= self._settings.storage_slot_capacity

    def get_acceptable_denominations(self) -> List[str]:
        """Return list of denomination strings whose storage is not full."""
        from app.core.constants import DENOM_TO_SLOT

        with self._lock:
            acceptable = []
            for denom in DENOM_TO_SLOT:
                storage_key = denom.value
                if denom.value.startswith("USD_"):
                    storage_key = "USD"
                elif denom.value.startswith("EUR_"):
                    storage_key = "EUR"
                count = self._consumables.bill_storage_counts.get(
                    storage_key, 0
                )
                if count < self._settings.storage_slot_capacity:
                    acceptable.append(denom.value)
            return acceptable

    # --- Internal alert checks ---

    def _check_storage_alerts(self) -> None:
        """Check if any storage slot is nearing capacity."""
        # Slot capacity is not precisely known; use threshold as absolute count
        threshold = self._settings.low_bill_threshold * 10  # ~100 bills as "full"
        alerts = []
        for denom, count in self._consumables.bill_storage_counts.items():
            if count >= threshold:
                alerts.append(f"STORAGE_FULL:{denom}")
        self._update_alerts("STORAGE_FULL", alerts)

    def _check_dispenser_alerts(self) -> None:
        threshold = self._settings.low_bill_threshold
        alerts = []
        for denom, count in self._consumables.bill_dispenser_counts.items():
            if 0 < count <= threshold:
                alerts.append(f"LOW_BILL:{denom}")
            elif count == 0:
                alerts.append(f"EMPTY_BILL:{denom}")
        self._update_alerts("LOW_BILL", alerts)
        self._update_alerts("EMPTY_BILL", alerts)

    def _check_coin_alerts(self) -> None:
        threshold = self._settings.low_coin_threshold
        alerts = []
        for denom, count in self._consumables.coin_counts.items():
            if 0 < count <= threshold:
                alerts.append(f"LOW_COIN:{denom}")
            elif count == 0:
                alerts.append(f"EMPTY_COIN:{denom}")
        self._update_alerts("LOW_COIN", alerts)
        self._update_alerts("EMPTY_COIN", alerts)

    def _update_alerts(self, prefix: str, new_alerts: List[str]) -> None:
        """Replace alerts matching prefix with new set."""
        self._consumables.alerts = [
            a for a in self._consumables.alerts if not a.startswith(prefix)
        ] + [a for a in new_alerts if a.startswith(prefix)]

    def _notify_change(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception as e:
                logger.error(f"on_change callback error: {e}")
