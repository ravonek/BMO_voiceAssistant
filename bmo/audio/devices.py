from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class AudioDevice:
    index: int
    name: str
    input_channels: int
    output_channels: int
    default_sample_rate: int


def list_audio_devices(sd_module: Any | None = None) -> list[AudioDevice]:
    if sd_module is None:
        import sounddevice as sd_module

    result = []
    for index, item in enumerate(sd_module.query_devices()):
        result.append(
            AudioDevice(
                index=index,
                name=str(item["name"]),
                input_channels=int(item["max_input_channels"]),
                output_channels=int(item["max_output_channels"]),
                default_sample_rate=int(item["default_samplerate"]),
            )
        )
    return result


def select_device(
    devices: list[AudioDevice], preferred_name: str, *, required_direction: str
) -> AudioDevice:
    if required_direction not in {"input", "output"}:
        raise ValueError("required_direction must be input or output")
    matches = [
        item
        for item in devices
        if preferred_name.casefold() in item.name.casefold()
        and (item.input_channels > 0 if required_direction == "input" else item.output_channels > 0)
    ]
    if not matches:
        raise RuntimeError(f"no {required_direction} device matched {preferred_name!r}")
    return matches[0]


def usb_device_present(vid_pid: str) -> bool:
    try:
        output = subprocess.run(
            ["lsusb"], capture_output=True, text=True, timeout=3, check=False
        ).stdout.casefold()
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return vid_pid.casefold() in output
