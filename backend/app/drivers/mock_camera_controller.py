"""Mock camera controller for development and testing without USB camera."""

import logging
from typing import Optional

import numpy as np

from app.drivers.camera_controller import CameraControllerBase

logger = logging.getLogger(__name__)


class MockCameraController(CameraControllerBase):
    """Returns synthetic test images or preset numpy arrays.
    
    For testing, you can inject specific frames via next_frame
    or set a fixed test pattern.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self._width = width
        self._height = height
        self.next_frame: Optional[np.ndarray] = None
        self.capture_count: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info(f"MockCamera initialized ({self._width}x{self._height})")

    async def capture_frame(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        self.capture_count += 1
        if self.next_frame is not None:
            frame = self.next_frame
            self.next_frame = None  # Consume injected frame
            return frame
        # Return a synthetic blank BGR image
        return np.zeros((self._height, self._width, 3), dtype=np.uint8)

    async def release(self) -> None:
        self._initialized = False
        logger.info("MockCamera released")

    # --- Test helpers ---

    def set_next_frame(self, frame: np.ndarray) -> None:
        """Inject a specific frame for the next capture."""
        self.next_frame = frame

    def reset(self) -> None:
        """Reset capture count and injected frame."""
        self.capture_count = 0
        self.next_frame = None
