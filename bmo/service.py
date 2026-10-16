from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import stat
from contextlib import suppress
from pathlib import Path
from typing import Any

from bmo.core.states import AssistantState

LOGGER = logging.getLogger(__name__)
CONTROL_COMMANDS = {"ptt-start", "ptt-stop", "cancel", "status", "shutdown"}


class BackgroundService:
    """Run BMO without stdin and accept local commands over a protected Unix socket."""

    def __init__(self, controller: Any, audio_input: Any, socket_path: Path) -> None:
        self.controller = controller
        self.audio_input = audio_input
        self.socket_path = socket_path
        self.recording = False
        self._turn_task: asyncio.Task[None] | None = None
        self._server: asyncio.AbstractServer | None = None
        self._shutdown = asyncio.Event()
        self._command_lock = asyncio.Lock()

    async def run(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        await self._prepare_socket()
        await self.controller.start()
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        LOGGER.info("background control socket ready: %s", self.socket_path)
        try:
            await self._shutdown.wait()
        finally:
            await self._cleanup()

    async def _prepare_socket(self) -> None:
        if not self.socket_path.exists():
            return
        if not stat.S_ISSOCK(self.socket_path.lstat().st_mode):
            raise RuntimeError(f"refusing to replace non-socket path: {self.socket_path}")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)), timeout=0.25
            )
        except (ConnectionError, TimeoutError, OSError):
            self.socket_path.unlink()
            return
        writer.close()
        await writer.wait_closed()
        del reader
        raise RuntimeError(f"another BMO service is already using {self.socket_path}")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=2.0)
            command = raw.decode("utf-8", errors="replace").strip()
            response = await self.dispatch(command)
        except Exception as exc:
            LOGGER.warning("control command failed: %s", type(exc).__name__)
            response = {"ok": False, "error": str(exc)}
        writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        with suppress(ConnectionError):
            await writer.drain()
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()

    async def dispatch(self, command: str) -> dict[str, Any]:
        if command not in CONTROL_COMMANDS:
            return {"ok": False, "error": f"unsupported command: {command}"}
        async with self._command_lock:
            if command == "status":
                return self._status()
            if command == "ptt-start":
                return await self._ptt_start()
            if command == "ptt-stop":
                return await self._ptt_stop()
            if command == "cancel":
                await self._cancel()
                return self._status(ok=True, message="cancelled")
            await self._cancel()
            self._shutdown.set()
            return self._status(ok=True, message="shutting down")

    def _status(self, *, ok: bool = True, message: str = "") -> dict[str, Any]:
        task_active = self._turn_task is not None and not self._turn_task.done()
        return {
            "ok": ok,
            "message": message,
            "state": str(self.controller.state),
            "operation_id": self.controller.operation_id,
            "recording": self.recording,
            "turn_active": task_active,
        }

    async def _ptt_start(self) -> dict[str, Any]:
        if self.recording:
            return self._status(ok=False, message="recording is already active")
        if self._turn_task is not None and not self._turn_task.done():
            return self._status(ok=False, message="assistant is processing a turn")
        if self.controller.state not in {AssistantState.IDLE, AssistantState.OFFLINE}:
            return self._status(ok=False, message="assistant is not ready")
        await self.controller.begin_listening()
        try:
            self.audio_input.start()
        except Exception:
            await self.controller.cancel()
            raise
        self.recording = True
        return self._status(message="recording started")

    async def _ptt_stop(self) -> dict[str, Any]:
        if not self.recording:
            return self._status(ok=False, message="recording is not active")
        try:
            clip = self.audio_input.stop()
        except Exception:
            self.recording = False
            await self.controller.cancel()
            raise
        self.recording = False
        if clip is None:
            await self.controller.cancel()
            return self._status(ok=False, message="recording was empty")
        self._turn_task = asyncio.create_task(self.controller.submit_audio(clip))
        self._turn_task.add_done_callback(self._turn_finished)
        return self._status(message="recording submitted")

    def _turn_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOGGER.error("background turn failed: %s", type(error).__name__)

    async def _cancel(self) -> None:
        if self.recording:
            self.audio_input.cancel()
            self.recording = False
        await self.controller.cancel()
        task = self._turn_task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _cleanup(self) -> None:
        await self._cancel()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        if self.socket_path.exists() and stat.S_ISSOCK(self.socket_path.lstat().st_mode):
            self.socket_path.unlink()


async def run_background_service(controller: Any, audio_input: Any, socket_path: Path) -> None:
    service = BackgroundService(controller, audio_input, socket_path)
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal_number, service._shutdown.set)
    await service.run()


async def send_control_command(socket_path: Path, command: str) -> dict[str, Any]:
    if command not in CONTROL_COMMANDS:
        raise ValueError(f"unsupported command: {command}")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path)), timeout=2.0
        )
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"BMO service is unavailable at {socket_path}") from exc
    writer.write((command + "\n").encode("utf-8"))
    await writer.drain()
    raw = await asyncio.wait_for(reader.readline(), timeout=5.0)
    writer.close()
    await writer.wait_closed()
    if not raw:
        raise RuntimeError("BMO service returned an empty response")
    return json.loads(raw)
