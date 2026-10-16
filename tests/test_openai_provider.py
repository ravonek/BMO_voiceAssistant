from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bmo.budget import BudgetGuard
from bmo.config import CloudConfig
from bmo.models import AudioClip, CapturedFrame
from bmo.providers.openai_api import OpenAIProviders


class FakeResponses:
    def __init__(self) -> None:
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text="OK",
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        )


class FakeTranscriptions:
    def __init__(self) -> None:
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(text="Привет", languages=[SimpleNamespace(code="ru")])


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()
        self.audio = SimpleNamespace(transcriptions=FakeTranscriptions())


class FailingResponses:
    async def create(self, **kwargs):
        raise RuntimeError("offline")


def guard(tmp_path: Path) -> BudgetGuard:
    return BudgetGuard(
        tmp_path / "budget.sqlite3",
        timezone="Asia/Almaty",
        daily_hard_limit_usd=1,
        monthly_hard_limit_usd=2,
    )


@pytest.mark.asyncio
async def test_response_always_disables_storage(tmp_path: Path) -> None:
    client = FakeClient()
    provider = OpenAIProviders(CloudConfig(), guard(tmp_path), client=client)
    result = await provider.respond("hello", [], CapturedFrame(b"jpeg", 1, 1, "mock"))
    assert result.text == "OK"
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["model"] == "gpt-6-luna"
    assert client.responses.kwargs["reasoning"] == {"effort": "none"}
    assert "data:image/jpeg;base64," in str(client.responses.kwargs["input"])


@pytest.mark.asyncio
async def test_transcription_uses_completed_wav(tmp_path: Path) -> None:
    client = FakeClient()
    provider = OpenAIProviders(CloudConfig(), guard(tmp_path), client=client)
    result = await provider.transcribe(AudioClip(b"RIFFtest", 2.0, 16000))
    assert result.text == "Привет"
    assert result.language == "ru"
    assert client.audio.transcriptions.kwargs["model"] == "gpt-transcribe"
    assert client.audio.transcriptions.kwargs["file"][0] == "speech.wav"


@pytest.mark.asyncio
async def test_failed_request_keeps_conservative_cost(tmp_path: Path) -> None:
    client = FakeClient()
    client.responses = FailingResponses()
    budget = guard(tmp_path)
    provider = OpenAIProviders(CloudConfig(), budget, client=client)
    with pytest.raises(RuntimeError, match="offline"):
        await provider.respond("hello", [])
    status = budget.status()
    assert status.reserved_usd == 0
    assert status.daily_usd >= 0.001
