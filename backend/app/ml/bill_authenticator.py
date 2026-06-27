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
    "EUR_5": BillDenom.EUR_5,
    "EUR_10": BillDenom.EUR_10,
    # NCNN model custom classification formats
    "20php": BillDenom.PHP_20,
    "50php": BillDenom.PHP_50,
    "100php": BillDenom.PHP_100,
    "200php": BillDenom.PHP_200,
    "500php": BillDenom.PHP_500,
    "1000php": BillDenom.PHP_1000,
    "1000php_polymer": BillDenom.PHP_1000,
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
    Supports per-currency model switching for forex transactions.
    """

    def __init__(
        self,
        auth_model_path: str,
        denom_model_path: str,
        confidence_threshold: float = 0.7,
        auth_model_path_usd: Optional[str] = None,
        denom_model_path_usd: Optional[str] = None,
        auth_model_path_eur: Optional[str] = None,
        denom_model_path_eur: Optional[str] = None,
    ):
        self._confidence_threshold = confidence_threshold
        self._model_paths: Dict[str, Dict[str, str]] = {
            "PHP": {"auth": auth_model_path, "denom": denom_model_path},
        }
        if auth_model_path_usd and denom_model_path_usd:
            self._model_paths["USD"] = {
                "auth": auth_model_path_usd,
                "denom": denom_model_path_usd,
            }
        if auth_model_path_eur and denom_model_path_eur:
            self._model_paths["EUR"] = {
                "auth": auth_model_path_eur,
                "denom": denom_model_path_eur,
            }
        self._loaded_models: Dict[str, Dict[str, object]] = {}
        self._active_currency = "PHP"
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_currency(self, currency: str) -> None:
        """Switch to models for the given currency."""
        if currency not in self._model_paths:
            raise ValueError(f"No models available for currency: {currency}")
        self._active_currency = currency

    def _ensure_loop(self) -> None:
        if self._loop is None:
            self._loop = asyncio.get_event_loop()

    def _load_model(self, currency: str, model_type: str):
        """Lazily load a model for the given currency and type."""
        if currency not in self._loaded_models:
            self._loaded_models[currency] = {}
        if model_type not in self._loaded_models[currency]:
            from ultralytics import YOLO

            path = self._model_paths[currency][model_type]
            logger.info(f"Loading {model_type} model for {currency}: {path}")
            self._loaded_models[currency][model_type] = YOLO(path)
            logger.info(f"{model_type} model for {currency} loaded")
        return self._loaded_models[currency][model_type]

    def _get_active_auth_model(self):
        return self._load_model(self._active_currency, "auth")

    def _get_active_denom_model(self):
        return self._load_model(self._active_currency, "denom")

    async def authenticate(self, uv_image: np.ndarray) -> BillAuthResult:
        """Run authentication model on UV image.

        Expected model output: class "genuine" or "fake" with confidence.
        """
        self._ensure_loop()
        return await self._loop.run_in_executor(
            None, self._run_auth_inference, uv_image
        )

    def _run_auth_inference(self, image: np.ndarray) -> BillAuthResult:
        model = self._get_active_auth_model()
        results = model.predict(image, verbose=False)
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
        model = self._get_active_denom_model()
        results = model.predict(image, verbose=False)
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
