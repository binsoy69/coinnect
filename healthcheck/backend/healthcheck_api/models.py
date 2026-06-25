"""Pydantic models for diagnostics API responses."""

from datetime import UTC, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    pin: str


class LoginResponse(BaseModel):
    token: str


class TestDefinition(BaseModel):
    id: str
    label: str
    component: str
    kind: Literal[
        "connectivity",
        "sensor",
        "actuator",
        "camera",
        "status",
        "printer",
        "ml",
    ]
    description: str
    caution: Optional[str] = None


class ComponentGroup(BaseModel):
    id: str
    label: str
    description: str
    tests: list[TestDefinition] = Field(default_factory=list)


class HealthcheckStatus(BaseModel):
    serial: dict
    gpio: dict
    camera: dict
    printer: dict
    busy: bool
    recent_run_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TestRunResult(BaseModel):
    id: str
    test_id: str
    label: str
    status: Literal["passed", "failed"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    response: dict = Field(default_factory=dict)
    error: Optional[str] = None
    error_code: Optional[str] = None


class EWalletSandboxSessionCreate(BaseModel):
    provider: Literal["gcash", "maya"]
    direction: Literal["cash-in", "cash-out"]
    amount: int = Field(ge=1, le=50_000)
    mobile_number: Optional[str] = Field(
        default=None,
        pattern=r"^09\d{9}$",
    )
    account_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    @model_validator(mode="after")
    def validate_cash_in_identity(self):
        if self.direction == "cash-in":
            if not self.mobile_number or not self.account_name:
                raise ValueError(
                    "Cash-in requires mobile_number and account_name"
                )
        elif self.mobile_number is not None or self.account_name is not None:
            raise ValueError(
                "Cash-out does not accept mobile_number or account_name"
            )
        return self
