from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class AudioClip:
    wav_bytes: bytes
    duration_sec: float
    sample_rate: int
    channels: int = 1


@dataclass(slots=True, frozen=True)
class Transcript:
    text: str
    language: str | None = None
    duration_sec: float = 0.0


@dataclass(slots=True, frozen=True)
class CapturedFrame:
    jpeg_bytes: bytes
    width: int
    height: int
    source: str


@dataclass(slots=True, frozen=True)
class UsageRecord:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0
    vision_images: int = 0
    estimated_cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ModelReply:
    text: str
    usage: UsageRecord
