from __future__ import annotations

import asyncio

import pytest

from bmo.config import Settings
from bmo.core.controller import AssistantController
from bmo.core.states import AssistantState
from bmo.models import AudioClip, Transcript
from bmo.providers.mock import (
    MockCameraProvider,
    MockLLMProvider,
    MockSTTProvider,
    MockTTSProvider,
)


def clip() -> AudioClip:
    return AudioClip(b"RIFFfake", 1.0, 16000)


async def ready(controller: AssistantController) -> None:
    await controller.start()
    await controller.begin_listening()


@pytest.mark.asyncio
async def test_mock_voice_turn() -> None:
    stt = MockSTTProvider("Привет", "ru")
    llm = MockLLMProvider("Привет! Чем займёмся?")
    tts = MockTTSProvider()
    controller = AssistantController(Settings(), stt=stt, llm=llm, tts=tts)
    await ready(controller)
    await controller.submit_audio(clip(), allow_followup=False)
    assert controller.state is AssistantState.IDLE
    assert llm.calls == 1
    assert tts.spoken[0][1] == "ru"
    assert controller.context.messages()[-1]["content"] == "Привет! Чем займёмся?"


@pytest.mark.asyncio
async def test_vision_only_for_explicit_request() -> None:
    camera = MockCameraProvider()
    llm = MockLLMProvider("Вижу стол.")
    controller = AssistantController(
        Settings(),
        stt=MockSTTProvider("Что ты видишь?", "ru"),
        llm=llm,
        tts=MockTTSProvider(),
        camera=camera,
    )
    await ready(controller)
    await controller.submit_audio(clip(), allow_followup=False)
    assert camera.calls == 1
    assert llm.images == 1


class FailingCamera:
    async def capture(self):
        raise RuntimeError("camera busy")


@pytest.mark.asyncio
async def test_camera_failure_keeps_voice_dialog_available() -> None:
    llm = MockLLMProvider()
    tts = MockTTSProvider()
    controller = AssistantController(
        Settings(),
        stt=MockSTTProvider("Что ты видишь?", "ru"),
        llm=llm,
        tts=tts,
        camera=FailingCamera(),
    )
    await ready(controller)
    await controller.submit_audio(clip(), allow_followup=False)
    assert controller.state is AssistantState.IDLE
    assert llm.calls == 0
    assert "Не удалось получить кадр" in tts.spoken[0][0]


@pytest.mark.asyncio
async def test_local_time_does_not_call_llm() -> None:
    llm = MockLLMProvider()
    controller = AssistantController(
        Settings(), stt=MockSTTProvider("Который час?", "ru"), llm=llm, tts=MockTTSProvider()
    )
    await ready(controller)
    await controller.submit_audio(clip(), allow_followup=False)
    assert llm.calls == 0


class SlowSTT:
    async def transcribe(self, clip: AudioClip) -> Transcript:
        await asyncio.sleep(10)
        return Transcript("late", "en", clip.duration_sec)


@pytest.mark.asyncio
async def test_cancel_drops_late_operation() -> None:
    tts = MockTTSProvider()
    controller = AssistantController(Settings(), stt=SlowSTT(), llm=MockLLMProvider(), tts=tts)
    await ready(controller)
    task = asyncio.create_task(controller.submit_audio(clip(), allow_followup=False))
    await asyncio.sleep(0)
    await controller.cancel()
    await task
    assert controller.state is AssistantState.IDLE
    assert not tts.spoken


class OneFollowupAudio:
    def __init__(self) -> None:
        self.calls = 0

    async def record_followup(self, timeout_sec: float) -> AudioClip | None:
        assert timeout_sec == 5.0
        self.calls += 1
        return clip() if self.calls == 1 else None


@pytest.mark.asyncio
async def test_followup_turn_runs_without_new_wake_or_ptt() -> None:
    settings = Settings()
    settings.audio.anti_echo_cooldown_sec = 0
    stt = MockSTTProvider("Продолжение", "ru")
    llm = MockLLMProvider("Ответ")
    followup = OneFollowupAudio()
    controller = AssistantController(
        settings,
        stt=stt,
        llm=llm,
        tts=MockTTSProvider(),
        audio_input=followup,
    )
    await ready(controller)
    await controller.submit_audio(clip())
    assert controller.state is AssistantState.IDLE
    assert stt.calls == 2
    assert llm.calls == 2
    assert followup.calls == 2
