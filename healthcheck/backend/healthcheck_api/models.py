"""Pydantic models for diagnostics API responses."""

from datetime import UTC, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    pin: str


class LoginResponse(BaseModel):
    token: str


class TestDefinition(BaseModel):
    id: str
    label: str
    component: str
    kind: Literal["connectivity", "sensor", "actuator", "camera", "status"]
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
