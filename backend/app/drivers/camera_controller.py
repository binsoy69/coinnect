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
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._loop.run_in_executor(None, self._open_camera)

    def _open_camera(self) -> None:
        import cv2
        
        # Try the configured index first
        logger.info(f"Attempting to open camera at configured index {self._device_index}...")
        cap = self._try_open_device(cv2, self._device_index)
        if cap is not None:
            self._cap = cap
            return

        # Configured index failed, fallback to auto-scan
        logger.warning(
            f"Failed to open camera at configured index {self._device_index}. "
            "Scanning indices 0-5 for a working camera..."
        )
        
        for idx in range(6):
            if idx == self._device_index:
                continue  # Already tried
            
            cap = self._try_open_device(cv2, idx)
            if cap is not None:
                logger.info(
                    f"Successfully auto-detected working camera at index {idx} "
                    f"(configured was {self._device_index})."
                )
                self._device_index = idx
                self._cap = cap
                return
                
        raise RuntimeError(
            f"Failed to open camera. Configured index {self._device_index} failed, "
            "and scanning indices 0-5 found no working camera device."
        )

    def _try_open_device(self, cv2, index: int):
        """Attempts to open a camera device and verify it by reading a frame."""
        cap = None
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                if cap is not None:
                    cap.release()
                return None
            
            # Set resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
            
            # Verify we can actually read a frame from it.
            # Virtual/metadata V4L2 devices often open but fail to read a frame.
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.debug(f"Camera index {index} opened but failed to read a frame.")
                cap.release()
                return None
                
            logger.info(
                f"USB camera opened successfully: device={index}, "
                f"resolution={self._resolution}"
            )
            return cap
        except Exception as e:
            logger.debug(f"Error testing camera index {index}: {e}")
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            return None


    async def capture_frame(self) -> np.ndarray:
        if self._cap is None:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        async with self._lock:
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
