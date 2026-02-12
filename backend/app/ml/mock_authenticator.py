"""Mock bill authenticator for development and testing without YOLO models."""

import logging
from typing import Optional

import numpy as np

from app.core.constants import BillDenom
from app.ml.bill_authenticator import BillAuthenticatorBase, BillAuthResult

logger = logging.getLogger(__name__)


class MockBillAuthenticator(BillAuthenticatorBase):
    """Configurable mock for testing without YOLO models.
    
    Default behavior: all bills are genuine PHP_100.
    Use set methods to configure specific test scenarios.
    """

    def __init__(self):
        self.next_auth_genuine: bool = True
        self.next_denomination: Optional[BillDenom] = BillDenom.PHP_100
        self.auth_confidence: float = 0.95
        self.denom_confidence: float = 0.92
        self.auth_call_count: int = 0
        self.denom_call_count: int = 0

    async def authenticate(self, uv_image: np.ndarray) -> BillAuthResult:
        self.auth_call_count += 1
        return BillAuthResult(
            is_genuine=self.next_auth_genuine,
            confidence=self.auth_confidence,
            raw_label="genuine" if self.next_auth_genuine else "fake",
        )

    async def identify_denomination(
        self, visible_image: np.ndarray
    ) -> BillAuthResult:
        self.denom_call_count += 1
        return BillAuthResult(
            is_genuine=True,
            confidence=self.denom_confidence,
            denomination=self.next_denomination,
            raw_label=self.next_denomination.value if self.next_denomination else "unknown",
        )

    # --- Configuration helpers ---

    def set_reject_next(self) -> None:
        """Next authentication call will reject the bill as fake."""
        self.next_auth_genuine = False

    def set_accept_next(self) -> None:
        """Next authentication call will accept the bill as genuine."""
        self.next_auth_genuine = True

    def set_next_denomination(self, denom: BillDenom) -> None:
        """Set the denomination to return on next identification."""
        self.next_denomination = denom

    def set_unknown_denomination(self) -> None:
        """Next denomination identification will return unknown."""
        self.next_denomination = None

    def reset(self) -> None:
        """Reset to defaults."""
        self.next_auth_genuine = True
        self.next_denomination = BillDenom.PHP_100
        self.auth_confidence = 0.95
        self.denom_confidence = 0.92
        self.auth_call_count = 0
        self.denom_call_count = 0
