"""Bill authentication using YOLO object detection.

Two-stage pipeline:
1. Authentication: Is the bill genuine? (UV image)
2. Denomination identification: What denomination? (visible light image)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

import numpy as np
from pydantic import BaseModel

from app.core.constants import BillDenom

logger = logging.getLogger(__name__)

# Map YOLO label strings to BillDenom enum values
LABEL_TO_DENOM: Dict[str, BillDenom] = {
    "PHP_20": BillDenom.PHP_20,
    "PHP_50": BillDenom.PHP_50,
    "PHP_100": BillDenom.PHP_100,
    "PHP_200": BillDenom.PHP_200,
    "PHP_500": BillDenom.PHP_500,
    "PHP_1000": BillDenom.PHP_1000,
    "USD_10": BillDenom.USD_10,
    "USD_50": BillDenom.USD_50,
    "USD_100": BillDenom.USD_100,
    "EUR_5": BillDenom.EUR_5,
    "EUR_10": BillDenom.EUR_10,
    "EUR_20": BillDenom.EUR_20,
}


class BillAuthResult(BaseModel):
    """Result of a bill authentication or denomination identification."""

    is_genuine: bool = False
    confidence: float = 0.0
    denomination: Optional[BillDenom] = None
    raw_label: Optional[str] = None


class BillAuthenticatorBase(ABC):
    """Abstract base for bill authentication."""

    @abstractmethod
    async def authenticate(self, uv_image: np.ndarray) -> BillAuthResult:
        """Authenticate bill genuineness from UV image."""

    @abstractmethod
    async def identify_denomination(
        self, visible_image: np.ndarray
    ) -> BillAuthResult:
        """Identify bill denomination from visible light image."""


class YOLOBillAuthenticator(BillAuthenticatorBase):
    """YOLO-based bill authentication using Ultralytics.
    
    Models are loaded lazily on first use to avoid slow startup.
    Inference runs in executor thread to avoid blocking async loop.
    """

    def __init__(
        self,
        auth_model_path: str,
        denom_model_path: str,
        confidence_threshold: float = 0.7,
    ):
        self._auth_model_path = auth_model_path
        self._denom_model_path = denom_model_path
        self._confidence_threshold = confidence_threshold
        self._auth_model = None
        self._denom_model = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _ensure_loop(self) -> None:
        if self._loop is None:
            self._loop = asyncio.get_event_loop()

    def _load_auth_model(self):
        if self._auth_model is None:
            from ultralytics import YOLO

            logger.info(f"Loading auth model: {self._auth_model_path}")
            self._auth_model = YOLO(self._auth_model_path)
            logger.info("Auth model loaded")

    def _load_denom_model(self):
        if self._denom_model is None:
            from ultralytics import YOLO

            logger.info(f"Loading denom model: {self._denom_model_path}")
            self._denom_model = YOLO(self._denom_model_path)
            logger.info("Denom model loaded")

    async def authenticate(self, uv_image: np.ndarray) -> BillAuthResult:
        """Run authentication model on UV image.
        
        Expected model output: class "genuine" or "fake" with confidence.
        """
        self._ensure_loop()
        return await self._loop.run_in_executor(
            None, self._run_auth_inference, uv_image
        )

    def _run_auth_inference(self, image: np.ndarray) -> BillAuthResult:
        self._load_auth_model()
        results = self._auth_model.predict(image, verbose=False)
        if not results or len(results) == 0:
            return BillAuthResult(is_genuine=False, confidence=0.0)

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return BillAuthResult(is_genuine=False, confidence=0.0)

        # Get highest confidence detection
        best_idx = result.boxes.conf.argmax().item()
        confidence = float(result.boxes.conf[best_idx])
        class_id = int(result.boxes.cls[best_idx])
        label = result.names.get(class_id, "unknown")

        is_genuine = label.lower() == "genuine" and confidence >= self._confidence_threshold

        return BillAuthResult(
            is_genuine=is_genuine,
            confidence=confidence,
            raw_label=label,
        )

    async def identify_denomination(
        self, visible_image: np.ndarray
    ) -> BillAuthResult:
        """Run denomination model on visible light image."""
        self._ensure_loop()
        return await self._loop.run_in_executor(
            None, self._run_denom_inference, visible_image
        )

    def _run_denom_inference(self, image: np.ndarray) -> BillAuthResult:
        self._load_denom_model()
        results = self._denom_model.predict(image, verbose=False)
        if not results or len(results) == 0:
            return BillAuthResult(is_genuine=True, confidence=0.0)

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return BillAuthResult(is_genuine=True, confidence=0.0)

        # Get highest confidence detection
        best_idx = result.boxes.conf.argmax().item()
        confidence = float(result.boxes.conf[best_idx])
        class_id = int(result.boxes.cls[best_idx])
        label = result.names.get(class_id, "unknown")

        denomination = LABEL_TO_DENOM.get(label)

        return BillAuthResult(
            is_genuine=True,
            confidence=confidence,
            denomination=denomination,
            raw_label=label,
        )
