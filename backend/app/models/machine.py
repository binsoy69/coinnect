from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DeviceConnectionState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"


class DeviceStatus(BaseModel):
    connection: DeviceConnectionState = DeviceConnectionState.DISCONNECTED
    controller_type: Optional[str] = None
    firmware_version: Optional[str] = None
    last_ping: Optional[datetime] = None
    last_error: Optional[str] = None


class SorterState(BaseModel):
    homed: bool = False
    current_position: int = 0
    current_slot: Optional[int] = None


class SecurityState(BaseModel):
    locked: bool = True
    tamper_active: bool = False
    last_tamper_sensor: Optional[str] = None
    last_tamper_time: Optional[datetime] = None


class ConsumablesState(BaseModel):
    bill_storage_counts: Dict[str, int] = Field(
        default_factory=lambda: {
            "PHP_20": 0, "PHP_50": 0, "PHP_100": 0,
            "PHP_200": 0, "PHP_500": 0, "PHP_1000": 0,
            "USD": 0, "EUR": 0,
        }
    )
    bill_dispenser_counts: Dict[str, int] = Field(
        default_factory=lambda: {
            "PHP_20": 0, "PHP_50": 0, "PHP_100": 0,
            "PHP_200": 0, "PHP_500": 0, "PHP_1000": 0,
            "USD_10": 0, "USD_50": 0, "USD_100": 0,
            "EUR_5": 0, "EUR_10": 0, "EUR_20": 0,
        }
    )
    coin_counts: Dict[str, int] = Field(
        default_factory=lambda: {
            "PHP_1": 0, "PHP_5": 0, "PHP_10": 0, "PHP_20": 0,
        }
    )
    alerts: List[str] = Field(default_factory=list)


class MachineStateSnapshot(BaseModel):
    bill_device: DeviceStatus = Field(default_factory=DeviceStatus)
    coin_device: DeviceStatus = Field(default_factory=DeviceStatus)
    sorter: SorterState = Field(default_factory=SorterState)
    security: SecurityState = Field(default_factory=SecurityState)
    consumables: ConsumablesState = Field(default_factory=ConsumablesState)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
