from __future__ import annotations

from collections.abc import Sequence

from bmo.models import AudioClip, CapturedFrame, ModelReply, Transcript, UsageRecord


class MockSTTProvider:
    def __init__(self, text: str = "Привет, Бимо", language: str = "ru") -> None:
        self.text = text
        self.language = language
        self.calls = 0

    async def transcribe(self, clip: AudioClip) -> Transcript:
        self.calls += 1
        return Transcript(self.text, self.language, clip.duration_sec)


class MockLLMProvider:
    def __init__(self, reply: str = "Привет! Я готов помочь.") -> None:
        self.reply = reply
        self.calls = 0
        self.images = 0

    async def respond(
        self,
        text: str,
        history: Sequence[dict[str, str]],
        image: CapturedFrame | None = None,
    ) -> ModelReply:
        self.calls += 1
        self.images += int(image is not None)
        return ModelReply(
            self.reply,
            UsageRecord(provider="mock", model="mock", vision_images=int(image is not None)),
        )


class MockTTSProvider:
    def __init__(self) -> None:
        self.spoken: list[tuple[str, str, int]] = []
        self.cancelled = False

    async def speak(self, text: str, language: str, operation_id: int) -> None:
        self.spoken.append((text, language, operation_id))

    async def cancel(self) -> None:
        self.cancelled = True


class MockCameraProvider:
    def __init__(self, jpeg_bytes: bytes = b"fake-jpeg") -> None:
        self.jpeg_bytes = jpeg_bytes
        self.calls = 0

    async def capture(self) -> CapturedFrame:
        self.calls += 1
        return CapturedFrame(self.jpeg_bytes, 640, 480, "mock")
