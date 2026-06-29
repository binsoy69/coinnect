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
        self._currency: str = "PHP"

    async def authenticate(self, uv_image: np.ndarray) -> BillAuthResult:
        self.auth_call_count += 1
        import cv2
        import base64
        try:
            annotated = uv_image.copy()
            # Draw a green (genuine) or red (fake) bounding box border
            color = (0, 255, 0) if self.next_auth_genuine else (0, 0, 255)
            cv2.rectangle(annotated, (20, 20), (annotated.shape[1] - 20, annotated.shape[0] - 20), color, 3)
            label = "GENUINE" if self.next_auth_genuine else "FAKE"
            cv2.putText(annotated, f"AUTH: {label} ({self.auth_confidence:.1%})", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            _, buffer = cv2.imencode('.jpg', annotated)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            annotated_image_b64 = f"data:image/jpeg;base64,{b64_str}"
        except Exception as e:
            logger.warning(f"Failed to draw mock auth annotation: {e}")
            annotated_image_b64 = None

        return BillAuthResult(
            is_genuine=self.next_auth_genuine,
            confidence=self.auth_confidence,
            raw_label="genuine" if self.next_auth_genuine else "fake",
            annotated_image_b64=annotated_image_b64,
        )

    async def identify_denomination(
        self, visible_image: np.ndarray
    ) -> BillAuthResult:
        self.denom_call_count += 1
        import cv2
        import base64
        try:
            annotated = visible_image.copy()
            label = self.next_denomination.value if self.next_denomination else "unknown"
            # Draw an orange bounding box border
            color = (0, 165, 255)  # BGR for orange
            cv2.rectangle(annotated, (20, 20), (annotated.shape[1] - 20, annotated.shape[0] - 20), color, 3)
            cv2.putText(annotated, f"DENOM: {label} ({self.denom_confidence:.1%})", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            _, buffer = cv2.imencode('.jpg', annotated)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            annotated_image_b64 = f"data:image/jpeg;base64,{b64_str}"
        except Exception as e:
            logger.warning(f"Failed to draw mock denom annotation: {e}")
            annotated_image_b64 = None

        return BillAuthResult(
            is_genuine=True,
            confidence=self.denom_confidence,
            denomination=self.next_denomination,
            raw_label=label,
            annotated_image_b64=annotated_image_b64,
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

    def set_currency(self, currency: str) -> None:
        """Set the expected currency for mock auth."""
        self._currency = currency

    def reset(self) -> None:
        """Reset to defaults."""
        self.next_auth_genuine = True
        self.next_denomination = BillDenom.PHP_100
        self.auth_confidence = 0.95
        self.denom_confidence = 0.92
        self.auth_call_count = 0
        self.denom_call_count = 0
        self._currency = "PHP"
