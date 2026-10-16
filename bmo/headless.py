from __future__ import annotations

import asyncio
import os
import sys
import termios
import tty
from collections.abc import Iterator
from contextlib import contextmanager

from bmo.audio.io import SoundDeviceAudioInput
from bmo.core.controller import AssistantController


@contextmanager
def cbreak_terminal() -> Iterator[None]:
    if not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


async def _print_events(controller: AssistantController) -> None:
    while True:
        event = await controller.events.next()
        print(f"\n[{event.state}] {event.message}", flush=True)


async def run_headless(controller: AssistantController, audio_input: SoundDeviceAudioInput) -> None:
    await controller.start()
    event_task = asyncio.create_task(_print_events(controller))
    turn_task: asyncio.Task[None] | None = None
    recording = False
    print("Enter: start/stop recording | Esc: cancel | q: quit", flush=True)
    try:
        with cbreak_terminal():
            while True:
                key = await asyncio.to_thread(os.read, sys.stdin.fileno(), 1)
                if key in {b"q", b"Q"}:
                    await controller.cancel()
                    break
                if key == b"\x1b":
                    audio_input.cancel()
                    recording = False
                    await controller.cancel()
                    continue
                if key in {b"\n", b"\r"}:
                    if turn_task and not turn_task.done():
                        print("BMO is busy; press Esc to cancel.", flush=True)
                        continue
                    if not recording:
                        await controller.begin_listening()
                        audio_input.start()
                        recording = True
                    else:
                        clip = audio_input.stop()
                        recording = False
                        if clip is None:
                            await controller.cancel()
                        else:
                            turn_task = asyncio.create_task(controller.submit_audio(clip))
    finally:
        if recording:
            audio_input.cancel()
        if turn_task and not turn_task.done():
            await controller.cancel()
        event_task.cancel()
