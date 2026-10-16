from __future__ import annotations

import asyncio
import io
import math
import threading
import time
import wave
from collections import deque
from typing import Any

import numpy as np

from bmo.audio.devices import list_audio_devices, select_device
from bmo.config import AudioConfig
from bmo.models import AudioClip


def pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def rms_int16(data: bytes) -> float:
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float64)
    if not samples.size:
        return 0.0
    return float(math.sqrt(np.mean(samples * samples)))


class SoundDeviceAudioInput:
    def __init__(self, config: AudioConfig, sd_module: Any | None = None) -> None:
        if sd_module is None:
            import sounddevice as sd_module

        self.sd = sd_module
        self.config = config
        self.device = select_device(
            list_audio_devices(self.sd), config.preferred_input_name, required_direction="input"
        )
        self._stream: Any | None = None
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self._started_at = 0.0

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("audio capture is already active")
        self._chunks = []
        self._started_at = time.monotonic()

        def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
            del frames, time_info
            if status:
                pass
            with self._lock:
                self._chunks.append(bytes(indata))

        self._stream = self.sd.RawInputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="int16",
            device=self.device.index,
            callback=callback,
            blocksize=int(self.config.sample_rate * 0.05),
        )
        self._stream.start()

    def stop(self) -> AudioClip | None:
        stream, self._stream = self._stream, None
        if stream is None:
            return None
        stream.stop()
        stream.close()
        with self._lock:
            pcm = b"".join(self._chunks)
            self._chunks = []
        duration = len(pcm) / (2 * self.config.channels * self.config.sample_rate)
        if duration < 0.1:
            return None
        return AudioClip(
            pcm_to_wav(pcm, self.config.sample_rate, self.config.channels),
            duration,
            self.config.sample_rate,
            self.config.channels,
        )

    def cancel(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.abort()
            stream.close()
        with self._lock:
            self._chunks = []

    async def record_followup(self, timeout_sec: float) -> AudioClip | None:
        return await asyncio.to_thread(self._record_until_silence, timeout_sec)

    def _record_until_silence(self, timeout_sec: float) -> AudioClip | None:
        block_duration = 0.03
        blocksize = int(self.config.sample_rate * block_duration)
        pre_roll: deque[bytes] = deque(maxlen=max(1, int(0.3 / block_duration)))
        chunks: list[bytes] = []
        started = False
        silent_for = 0.0
        elapsed = 0.0
        with self.sd.RawInputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="int16",
            device=self.device.index,
            blocksize=blocksize,
        ) as stream:
            while elapsed < self.config.max_utterance_sec:
                data, _overflow = stream.read(blocksize)
                raw = bytes(data)
                level = rms_int16(raw)
                elapsed += block_duration
                if not started:
                    pre_roll.append(raw)
                    if level >= self.config.vad_rms_threshold:
                        started = True
                        chunks.extend(pre_roll)
                    elif elapsed >= timeout_sec:
                        return None
                else:
                    chunks.append(raw)
                    if level < self.config.vad_rms_threshold:
                        silent_for += block_duration
                        if silent_for >= self.config.end_silence_sec:
                            break
                    else:
                        silent_for = 0.0
        pcm = b"".join(chunks)
        if not pcm:
            return None
        duration = len(pcm) / (2 * self.config.channels * self.config.sample_rate)
        return AudioClip(
            pcm_to_wav(pcm, self.config.sample_rate, self.config.channels),
            duration,
            self.config.sample_rate,
            self.config.channels,
        )


class SoundDeviceAudioOutput:
    def __init__(self, config: AudioConfig, sd_module: Any | None = None) -> None:
        if sd_module is None:
            import sounddevice as sd_module

        self.sd = sd_module
        self.config = config
        self.device = select_device(
            list_audio_devices(self.sd), config.preferred_output_name, required_direction="output"
        )

    async def play(self, samples: np.ndarray, sample_rate: int) -> None:
        await asyncio.to_thread(self._play_blocking, samples, sample_rate)

    def _play_blocking(self, samples: np.ndarray, sample_rate: int) -> None:
        target_rate = int(self.device.default_sample_rate)

        if sample_rate != target_rate and len(samples) > 0:
            old_positions = np.arange(len(samples), dtype=np.float64)
            new_count = round(len(samples) * target_rate / sample_rate)
            new_positions = (
                np.arange(new_count, dtype=np.float64)
                * sample_rate / target_rate
            )
            samples = np.interp(
                new_positions, old_positions, samples
            ).astype(np.int16)

        self.sd.play(
            samples,
            samplerate=target_rate,
            device=self.device.index,
            blocking=True,
        )

    async def cancel(self) -> None:
        await asyncio.to_thread(self.sd.stop)
