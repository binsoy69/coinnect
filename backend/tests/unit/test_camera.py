import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from app.drivers.camera_controller import USBCameraController


class TestUSBCameraController:
    @patch("cv2.VideoCapture")
    @pytest.mark.anyio
    async def test_initialize_configured_device_success(self, mock_video_capture):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        camera = USBCameraController(device_index=0)
        await camera.initialize()

        assert camera._device_index == 0
        assert camera._cap is mock_cap
        mock_video_capture.assert_called_once_with(0)

    @patch("cv2.VideoCapture")
    @pytest.mark.anyio
    async def test_initialize_fallback_scanning_success(self, mock_video_capture):
        cap_fail_open = MagicMock()
        cap_fail_open.isOpened.return_value = False

        cap_fail_read = MagicMock()
        cap_fail_read.isOpened.return_value = True
        cap_fail_read.read.return_value = (False, None)

        cap_success = MagicMock()
        cap_success.isOpened.return_value = True
        cap_success.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))

        def side_effect(index):
            if index == 0:
                return cap_fail_open
            elif index == 1:
                return cap_fail_read
            elif index == 2:
                return cap_success
            else:
                cap = MagicMock()
                cap.isOpened.return_value = False
                return cap

        mock_video_capture.side_effect = side_effect

        camera = USBCameraController(device_index=0)
        await camera.initialize()

        assert camera._device_index == 2
        assert camera._cap is cap_success

    @patch("cv2.VideoCapture")
    @pytest.mark.anyio
    async def test_initialize_all_devices_fail_raises_runtime_error(self, mock_video_capture):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_video_capture.return_value = mock_cap

        camera = USBCameraController(device_index=0)
        with pytest.raises(RuntimeError) as exc_info:
            await camera.initialize()

        assert "found no working camera device" in str(exc_info.value)
