from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from bmo.models import AudioClip, CapturedFrame, ModelReply, Transcript


class STTProvider(Protocol):
    async def transcribe(self, clip: AudioClip) -> Transcript: ...


class LLMProvider(Protocol):
    async def respond(
        self,
        text: str,
        history: Sequence[dict[str, str]],
        image: CapturedFrame | None = None,
    ) -> ModelReply: ...


class TTSProvider(Protocol):
    async def speak(self, text: str, language: str, operation_id: int) -> None: ...

    async def cancel(self) -> None: ...


class CameraProvider(Protocol):
    async def capture(self) -> CapturedFrame: ...
