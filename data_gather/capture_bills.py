"""Capture bill images from a webcam for YOLO classification training.

Run ``python data_gather/capture_bills.py --help`` for configuration options.
The live preview lists all available keyboard controls.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


WINDOW_NAME = "Coinnect Bill Data Capture"
DEFAULT_OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "captures"

DENOMINATION_KEYS = {
    ord("1"): "PHP_20",
    ord("2"): "PHP_50",
    ord("3"): "PHP_100",
    ord("4"): "PHP_200",
    ord("5"): "PHP_500",
    ord("6"): "PHP_1000",
    ord("7"): "USD_10",
    ord("8"): "USD_50",
    ord("9"): "EUR_5",
    ord("0"): "EUR_10",
}

KEY_HELP = (
    "1 PHP_20 | 2 PHP_50 | 3 PHP_100 | 4 PHP_200 | 5 PHP_500",
    "6 PHP_1000 | 7 USD_10 | 8 USD_50 | 9 EUR_5 | 0 EUR_10",
    "SPACE capture | A auto capture | Q / ESC quit",
)


def positive_int(value: str) -> int:
    """Parse a positive integer for an argparse option."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def positive_float(value: str) -> float:
    """Parse a positive floating-point value for an argparse option."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def jpeg_quality(value: str) -> int:
    """Parse and validate a JPEG quality setting."""
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture webcam images of bills and organize them into canonical "
            "Coinnect denomination folders."
        )
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        metavar="INDEX",
        help="webcam device index (default: 0)",
    )
    parser.add_argument(
        "--width",
        type=positive_int,
        default=1920,
        help="requested capture width in pixels (default: 1920)",
    )
    parser.add_argument(
        "--height",
        type=positive_int,
        default=1080,
        help="requested capture height in pixels (default: 1080)",
    )
    parser.add_argument(
        "--quality",
        type=jpeg_quality,
        default=95,
        metavar="1-100",
        help="JPEG quality (default: 95)",
    )
    parser.add_argument(
        "--interval",
        type=positive_float,
        default=1.0,
        metavar="SECONDS",
        help="seconds between automatic captures (default: 1.0)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        metavar="DIRECTORY",
        help=f"image output directory (default: {DEFAULT_OUTPUT_DIRECTORY})",
    )
    return parser


def import_opencv() -> Any:
    """Import OpenCV with an actionable error when it is unavailable."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is not installed. From the repository root, run:\n"
            "  python -m pip install -r backend/requirements.txt\n"
            "or install only the required package:\n"
            "  python -m pip install opencv-python"
        ) from exc
    return cv2


def _camera_backends(cv2: Any) -> list[int]:
    """Return preferred camera backends, with DirectShow first on Windows."""
    backends: list[int] = []
    if os.name == "nt" and hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)
    backends.append(cv2.CAP_ANY)
    return backends


def open_camera(
    cv2: Any, camera_index: int, width: int, height: int
) -> tuple[Any, Any]:
    """Open and validate a webcam, returning it and its first frame."""
    errors: list[str] = []

    for backend in _camera_backends(cv2):
        camera = cv2.VideoCapture(camera_index, backend)
        backend_name = (
            "DirectShow"
            if hasattr(cv2, "CAP_DSHOW") and backend == cv2.CAP_DSHOW
            else "default"
        )

        if not camera.isOpened():
            errors.append(f"{backend_name} could not open the device")
            camera.release()
            continue

        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        success, frame = camera.read()
        if success and frame is not None:
            return camera, frame

        errors.append(f"{backend_name} opened the device but returned no image")
        camera.release()

    details = "; ".join(errors)
    raise RuntimeError(
        f"Could not read from camera index {camera_index}. {details}. "
        "Close other applications using the webcam or try another index, "
        "for example: --camera 1"
    )


def save_frame(
    cv2: Any,
    frame: Any,
    output_root: Path,
    denomination: str,
    quality: int,
) -> Path:
    """Save an unannotated frame in its denomination directory."""
    denomination_directory = output_root / denomination
    denomination_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    unique_suffix = uuid.uuid4().hex[:8]
    output_path = denomination_directory / (
        f"{denomination}_{timestamp}_{unique_suffix}.jpg"
    )
    saved = cv2.imwrite(
        str(output_path),
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, quality],
    )
    if not saved:
        raise OSError(
            f"OpenCV could not write the image to '{output_path}'. "
            "Check that the location is writable and has free disk space."
        )
    return output_path


def draw_preview(
    cv2: Any,
    frame: Any,
    selected_denomination: str | None,
    captured_count: int,
    automatic_capture: bool,
    interval: float,
    status: str,
) -> Any:
    """Draw controls and capture state on a copy of the camera frame."""
    preview = frame.copy()
    overlay = preview.copy()
    panel_height = min(190, preview.shape[0])
    cv2.rectangle(overlay, (0, 0), (preview.shape[1], panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.68, preview, 0.32, 0, preview)

    selected_text = selected_denomination or "NONE - press a denomination key"
    auto_text = f"ON ({interval:g}s)" if automatic_capture else "OFF"
    lines = [
        f"Selected: {selected_text} | Captured this run: {captured_count} | Auto: {auto_text}",
        *KEY_HELP,
    ]
    if status:
        lines.append(status)

    max_lines = max(1, panel_height // 30)
    for index, line in enumerate(lines[:max_lines]):
        color = (80, 255, 80) if index == 0 else (235, 235, 235)
        if index == len(lines) - 1 and status:
            color = (0, 220, 255)
        cv2.putText(
            preview,
            line,
            (14, 27 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    return preview


def run_capture(args: argparse.Namespace, cv2: Any) -> None:
    """Run the interactive camera capture loop."""
    camera = None
    selected_denomination: str | None = None
    automatic_capture = False
    last_automatic_capture = time.monotonic()
    counts: defaultdict[str, int] = defaultdict(int)
    status = "Select a denomination to begin."
    frame = None

    try:
        camera, frame = open_camera(
            cv2, args.camera, args.width, args.height
        )
        print(
            f"Camera {args.camera} opened. Images will be saved under: "
            f"{args.output.resolve()}"
        )
        print("Use the controls shown in the preview window.")

        while True:
            success, latest_frame = camera.read()
            if success and latest_frame is not None:
                frame = latest_frame
            elif frame is None:
                raise RuntimeError("The camera stopped returning images.")
            else:
                status = "WARNING: Camera frame read failed; showing last frame."

            now = time.monotonic()
            if (
                automatic_capture
                and selected_denomination is not None
                and now - last_automatic_capture >= args.interval
            ):
                try:
                    path = save_frame(
                        cv2,
                        frame,
                        args.output,
                        selected_denomination,
                        args.quality,
                    )
                    counts[selected_denomination] += 1
                    status = f"Saved: {path.name}"
                    print(f"Saved {path}")
                    last_automatic_capture = now
                except OSError as exc:
                    automatic_capture = False
                    status = f"ERROR: {exc}"
                    print(status, file=sys.stderr)

            preview = draw_preview(
                cv2,
                frame,
                selected_denomination,
                counts[selected_denomination] if selected_denomination else 0,
                automatic_capture,
                args.interval,
                status,
            )
            cv2.imshow(WINDOW_NAME, preview)
            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q"), ord("Q")):
                break

            if key in DENOMINATION_KEYS:
                new_denomination = DENOMINATION_KEYS[key]
                if automatic_capture and new_denomination != selected_denomination:
                    automatic_capture = False
                    status = (
                        f"Selected {new_denomination}; automatic capture stopped "
                        "to prevent mislabeled images."
                    )
                else:
                    status = f"Selected {new_denomination}."
                selected_denomination = new_denomination
                continue

            if key == ord(" "):
                if selected_denomination is None:
                    status = "Select a denomination before capturing."
                    continue
                try:
                    path = save_frame(
                        cv2,
                        frame,
                        args.output,
                        selected_denomination,
                        args.quality,
                    )
                    counts[selected_denomination] += 1
                    status = f"Saved: {path.name}"
                    print(f"Saved {path}")
                except OSError as exc:
                    status = f"ERROR: {exc}"
                    print(status, file=sys.stderr)
                continue

            if key in (ord("a"), ord("A")):
                if selected_denomination is None:
                    status = "Select a denomination before enabling auto capture."
                    continue
                automatic_capture = not automatic_capture
                last_automatic_capture = time.monotonic()
                status = (
                    f"Automatic capture {'started' if automatic_capture else 'stopped'}."
                )
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cv2 = import_opencv()
        run_capture(args, cv2)
    except KeyboardInterrupt:
        print("\nCapture stopped by user.")
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
