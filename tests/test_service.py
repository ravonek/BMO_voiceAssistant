from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from bmo.core.states import AssistantState
from bmo.models import AudioClip
from bmo.service import BackgroundService, send_control_command


class FakeController:
    def __init__(self) -> None:
        self.state = AssistantState.BOOTING
        self.operation_id = 0
        self.submitted: list[AudioClip] = []
        self.cancelled = 0

    async def start(self) -> None:
        self.state = AssistantState.IDLE

    async def begin_listening(self) -> int:
        self.operation_id += 1
        self.state = AssistantState.LISTENING
        return self.operation_id

    async def submit_audio(self, clip: AudioClip) -> None:
        self.submitted.append(clip)
        self.state = AssistantState.IDLE

    async def cancel(self) -> None:
        self.cancelled += 1
        self.operation_id += 1
        self.state = AssistantState.IDLE


class FakeAudioInput:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.cancelled = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> AudioClip:
        self.stopped += 1
        return AudioClip(b"RIFFfake", 1.0, 16_000)

    def cancel(self) -> None:
        self.cancelled += 1


async def wait_for_socket(path: Path) -> None:
    for _ in range(100):
        if path.exists():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("service socket was not created")


@pytest.mark.asyncio
async def test_background_service_works_without_stdin() -> None:
    # macOS limits AF_UNIX paths to 104 bytes; pytest's tmp_path can exceed it.
    socket_path = Path("/tmp") / f"bmo-{os.getpid()}-{uuid4().hex[:8]}.sock"
    controller = FakeController()
    audio = FakeAudioInput()
    service = BackgroundService(controller, audio, socket_path)
    service_task = asyncio.create_task(service.run())
    await wait_for_socket(socket_path)

    status = await send_control_command(socket_path, "status")
    assert status["state"] == "idle"
    started = await send_control_command(socket_path, "ptt-start")
    assert started["recording"] is True
    stopped = await send_control_command(socket_path, "ptt-stop")
    assert stopped["message"] == "recording submitted"
    await asyncio.sleep(0)
    assert controller.submitted
    assert audio.started == 1
    assert audio.stopped == 1

    response = await send_control_command(socket_path, "shutdown")
    assert response["message"] == "shutting down"
    await service_task
    assert not socket_path.exists()


@pytest.mark.asyncio
async def test_service_rejects_unknown_command(tmp_path: Path) -> None:
    service = BackgroundService(FakeController(), FakeAudioInput(), tmp_path / "control.sock")
    response = await service.dispatch("dangerous-shell-command")
    assert response["ok"] is False


@pytest.mark.asyncio
async def test_service_refuses_to_replace_regular_file(tmp_path: Path) -> None:
    socket_path = tmp_path / "control.sock"
    socket_path.write_text("do not delete", encoding="utf-8")
    service = BackgroundService(FakeController(), FakeAudioInput(), socket_path)
    with pytest.raises(RuntimeError, match="non-socket"):
        await service.run()
    assert socket_path.read_text(encoding="utf-8") == "do not delete"
