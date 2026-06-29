"""Mock camera controller for development and testing without USB camera."""

import asyncio
import time
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
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._initialized = True
        logger.info(f"MockCamera initialized ({self._width}x{self._height})")

    async def capture_frame(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        async with self._lock:
            self.capture_count += 1
            if self.next_frame is not None:
                frame = self.next_frame
                self.next_frame = None  # Consume injected frame
                return frame
            
            # Return a synthetic test pattern with dynamic elements
            import cv2
            # Create a gray background
            frame = np.ones((self._height, self._width, 3), dtype=np.uint8) * 128
            # Draw some grid lines
            for i in range(0, self._width, 80):
                cv2.line(frame, (i, 0), (i, self._height), (100, 100, 100), 1)
            for i in range(0, self._height, 60):
                cv2.line(frame, (0, i), (self._width, i), (100, 100, 100), 1)
            # Draw a simulated bill outline in the center
            cv2.rectangle(frame, (self._width // 4, self._height // 4), (self._width * 3 // 4, self._height * 3 // 4), (200, 200, 200), -1)
            cv2.rectangle(frame, (self._width // 4, self._height // 4), (self._width * 3 // 4, self._height * 3 // 4), (0, 0, 0), 2)
            # Add dynamic details
            cv2.putText(frame, "MOCK CAMERA FEED", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(frame, f"Frame: {self.capture_count}", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(frame, f"Time: {time.strftime('%H:%M:%S')}", (30, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            # Draw a moving target circle based on capture count
            circle_x = int(self._width // 2 + 100 * np.cos(self.capture_count * 0.2))
            circle_y = int(self._height // 2 + 50 * np.sin(self.capture_count * 0.2))
            cv2.circle(frame, (circle_x, circle_y), 15, (0, 255, 0), -1)
            return frame

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
