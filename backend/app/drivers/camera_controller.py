"""Camera controller for bill image capture.

Provides abstract base and real USB camera implementation
using OpenCV for the bill acceptor system.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class CameraControllerBase(ABC):
    """Abstract base for camera capture."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize camera hardware."""

    @abstractmethod
    async def capture_frame(self) -> np.ndarray:
        """Capture a single frame. Returns BGR numpy array."""

    @abstractmethod
    async def release(self) -> None:
        """Release camera resources."""


class USBCameraController(CameraControllerBase):
    """Real USB camera implementation using OpenCV VideoCapture.
    
    Uses run_in_executor for blocking OpenCV calls to avoid
    blocking the async event loop.
    """

    def __init__(self, device_index: int = 0, resolution: tuple = (1920, 1080)):
        self._device_index = device_index
        self._resolution = resolution
        self._cap = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def initialize(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._loop.run_in_executor(None, self._open_camera)

    def _open_camera(self) -> None:
        import cv2
        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Failed to open camera device {self._device_index}"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        # Warm-up: discard first frame (often bad quality)
        self._cap.read()
        logger.info(
            f"USB camera opened: device={self._device_index}, "
            f"resolution={self._resolution}"
        )

    async def capture_frame(self) -> np.ndarray:
        if self._cap is None:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        frame = await self._loop.run_in_executor(None, self._read_frame)
        return frame

    def _read_frame(self) -> np.ndarray:
        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame from camera")
        return frame

    async def release(self) -> None:
        if self._cap is not None:
            await self._loop.run_in_executor(None, self._cap.release)
            self._cap = None
            logger.info("USB camera released")
