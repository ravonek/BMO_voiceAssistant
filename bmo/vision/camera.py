from __future__ import annotations

import asyncio
import glob
import subprocess
from pathlib import Path

from bmo.config import CameraConfig
from bmo.models import CapturedFrame


def find_video_device(config: CameraConfig) -> str:
    if config.device != "auto":
        return config.device
    target = f"{config.usb_vid}:{config.usb_pid}".casefold()
    for device in sorted(glob.glob("/dev/video*")):
        try:
            output = subprocess.run(
                ["udevadm", "info", "--query=property", f"--name={device}"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            ).stdout.casefold()
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        vid = f"id_vendor_id={config.usb_vid}".casefold() in output
        pid = f"id_model_id={config.usb_pid}".casefold() in output
        if target in output or (vid and pid):
            return device
    raise RuntimeError(f"USB camera {target} was not found")


class OpenCVCameraProvider:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config

    async def capture(self) -> CapturedFrame:
        return await asyncio.to_thread(self._capture_blocking)

    def _capture_blocking(self) -> CapturedFrame:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("vision extra is not installed") from exc

        device = find_video_device(self.config)
        capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not capture.isOpened():
            raise RuntimeError(f"cannot open camera {device}; close Guvcview and retry")
        try:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            capture.set(cv2.CAP_PROP_FPS, self.config.fps)
            actual_fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
            actual_format = "".join(chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4))
            if "YUYV" not in actual_format:
                raise RuntimeError(f"camera negotiated {actual_format!r}, expected YUYV")
            valid_frames = []
            for _ in range(8):
                ok, frame = capture.read()
                if ok and frame is not None and frame.size:
                    valid_frames.append(frame)
            if not valid_frames:
                raise RuntimeError("camera returned no valid frames")
            frame = max(valid_frames[-4:], key=lambda item: cv2.Laplacian(item, cv2.CV_64F).var())
            if self.config.rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif self.config.rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif self.config.rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                raise RuntimeError("JPEG encoding failed")
            if self.config.keep_photos:
                Path("diagnostics").mkdir(exist_ok=True)
                Path("diagnostics/last_camera.jpg").write_bytes(encoded.tobytes())
            return CapturedFrame(
                encoded.tobytes(), int(frame.shape[1]), int(frame.shape[0]), device
            )
        finally:
            capture.release()
