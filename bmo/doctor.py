from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from bmo.assets import verify_voices
from bmo.audio.devices import list_audio_devices, usb_device_present
from bmo.config import Settings


def _command_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or result.stderr.strip() or None


def collect_diagnostics(settings: Settings) -> dict[str, Any]:
    try:
        devices = [asdict(item) for item in list_audio_devices()]
        audio_error = None
    except Exception as exc:
        devices = []
        audio_error = f"{type(exc).__name__}: {exc}"
    camera_devices = sorted(str(path) for path in Path("/dev").glob("video*"))
    return {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version.split()[0],
        "os_release": _command_output(["sh", "-c", ". /etc/os-release && echo $PRETTY_NAME"]),
        "openai_api_key": "set" if os.getenv("OPENAI_API_KEY") else "not set",
        "ollama_required": False,
        "ollama_installed_ignored": shutil.which("ollama") is not None,
        "piper_executable": shutil.which(settings.speech.piper_executable),
        "ugreen_usb_31b2_5075": usb_device_present("31b2:5075"),
        "camera_usb_0bda_5842": usb_device_present("0bda:5842"),
        "camera_devices": camera_devices,
        "audio_devices": devices,
        "audio_error": audio_error,
        "voice_problems": verify_voices(Path("voices")),
    }


def render_diagnostics(data: dict[str, Any], as_json: bool) -> str:
    if as_json:
        return json.dumps(data, ensure_ascii=False, indent=2)
    lines = []
    for key, value in data.items():
        if key == "audio_devices":
            lines.append("audio_devices:")
            for item in value:
                lines.append(
                    f"  [{item['index']}] {item['name']} "
                    f"in={item['input_channels']} out={item['output_channels']}"
                )
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
