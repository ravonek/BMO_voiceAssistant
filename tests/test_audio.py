from __future__ import annotations

import numpy as np
import pytest

from bmo.audio.devices import AudioDevice, select_device
from bmo.audio.io import pcm_to_wav, rms_int16

DEVICES = [
    AudioDevice(0, "USB Camera Microphone", 1, 0, 48000),
    AudioDevice(1, "KT USB Audio", 1, 2, 48000),
]


def test_selects_ugreen_not_camera_microphone() -> None:
    selected = select_device(DEVICES, "KT USB Audio", required_direction="input")
    assert selected.index == 1


def test_missing_named_device_does_not_silently_fallback() -> None:
    with pytest.raises(RuntimeError, match="no input device"):
        select_device(DEVICES, "Unknown", required_direction="input")


def test_pcm_helpers() -> None:
    quiet = np.zeros(160, dtype=np.int16).tobytes()
    loud = np.full(160, 2000, dtype=np.int16).tobytes()
    assert rms_int16(quiet) == 0
    assert rms_int16(loud) == pytest.approx(2000)
    assert pcm_to_wav(loud, 16000).startswith(b"RIFF")
