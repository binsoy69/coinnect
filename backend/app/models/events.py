from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WSEventType(str, Enum):
    BILL_INSERTED = "BILL_INSERTED"
    BILL_AUTHENTICATED = "BILL_AUTHENTICATED"
    BILL_REJECTED = "BILL_REJECTED"
    COIN_INSERTED = "COIN_INSERTED"
    DISPENSE_PROGRESS = "DISPENSE_PROGRESS"
    DISPENSE_COMPLETE = "DISPENSE_COMPLETE"
    STATE_CHANGE = "STATE_CHANGE"
    ERROR = "ERROR"
    TAMPER = "TAMPER"
    DEVICE_CONNECTED = "DEVICE_CONNECTED"
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"


class WSEvent(BaseModel):
    type: WSEventType
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
