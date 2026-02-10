from typing import Dict, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.core.constants import BillDenom, ErrorCode

# ============================================================================
# Commands (RPi -> Arduino)
# ============================================================================


class SortCommand(BaseModel):
    cmd: Literal["SORT"] = "SORT"
    denom: BillDenom


class HomeCommand(BaseModel):
    cmd: Literal["HOME"] = "HOME"


class SortStatusCommand(BaseModel):
    cmd: Literal["SORT_STATUS"] = "SORT_STATUS"


class DispenseCommand(BaseModel):
    cmd: Literal["DISPENSE"] = "DISPENSE"
    denom: BillDenom
    count: int = Field(ge=1, le=20)


class DispenseStatusCommand(BaseModel):
    cmd: Literal["DISPENSE_STATUS"] = "DISPENSE_STATUS"
    denom: BillDenom


class CoinDispenseCommand(BaseModel):
    cmd: Literal["COIN_DISPENSE"] = "COIN_DISPENSE"
    denom: int = Field(description="Coin denomination integer (1, 5, 10, 20)")
    count: int = Field(ge=1, le=50)


class CoinChangeCommand(BaseModel):
    cmd: Literal["COIN_CHANGE"] = "COIN_CHANGE"
    amount: int = Field(ge=1)


class CoinResetCommand(BaseModel):
    cmd: Literal["COIN_RESET"] = "COIN_RESET"


class SecurityLockCommand(BaseModel):
    cmd: Literal["SECURITY_LOCK"] = "SECURITY_LOCK"


class SecurityUnlockCommand(BaseModel):
    cmd: Literal["SECURITY_UNLOCK"] = "SECURITY_UNLOCK"


class SecurityStatusCommand(BaseModel):
    cmd: Literal["SECURITY_STATUS"] = "SECURITY_STATUS"


class PingCommand(BaseModel):
    cmd: Literal["PING"] = "PING"


class VersionCommand(BaseModel):
    cmd: Literal["VERSION"] = "VERSION"


class ResetCommand(BaseModel):
    cmd: Literal["RESET"] = "RESET"


# ============================================================================
# Responses (Arduino -> RPi)
# ============================================================================


class SortResponse(BaseModel):
    status: Literal["READY"]
    slot: int


class HomeResponse(BaseModel):
    status: Literal["OK"]
    position: int = 0


class SortStatusResponse(BaseModel):
    status: Literal["OK"]
    position: int
    slot: int
    homed: bool


class DispenseResponse(BaseModel):
    status: Literal["OK"]
    dispensed: int


class DispenseStatusResponse(BaseModel):
    status: Literal["OK"]
    ready: bool


class CoinDispenseResponse(BaseModel):
    status: Literal["OK"]
    dispensed: int


class CoinChangeResponse(BaseModel):
    status: Literal["OK"]
    breakdown: Dict[str, int]


class CoinResetResponse(BaseModel):
    status: Literal["OK"]
    previous_total: int


class SecurityLockResponse(BaseModel):
    status: Literal["OK"]
    locked: bool = True


class SecurityUnlockResponse(BaseModel):
    status: Literal["OK"]
    locked: bool = False


class SecurityStatusResponse(BaseModel):
    status: Literal["OK"]
    locked: bool
    tamper_a: bool = False


class PingResponse(BaseModel):
    status: Literal["OK"]
    message: str = "PONG"


class VersionResponse(BaseModel):
    status: Literal["OK"]
    version: str
    controller: str


class ErrorResponse(BaseModel):
    status: Literal["ERROR"]
    code: ErrorCode
    dispensed: Optional[int] = None


# ============================================================================
# Events (Arduino -> RPi, unsolicited)
# ============================================================================


class CoinInEvent(BaseModel):
    event: Literal["COIN_IN"]
    denom: int
    total: int


class TamperEvent(BaseModel):
    event: Literal["TAMPER"]
    sensor: str


class KeypadEvent(BaseModel):
    event: Literal["KEYPAD"]
    key: str


class DoorStateEvent(BaseModel):
    event: Literal["DOOR_STATE"]
    locked: bool


class ReadyEvent(BaseModel):
    event: Literal["READY"]
    version: str
    controller: str


SerialEvent = Union[CoinInEvent, TamperEvent, KeypadEvent, DoorStateEvent, ReadyEvent]
