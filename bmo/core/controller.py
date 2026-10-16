from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from bmo.config import Settings
from bmo.core.events import EventBus, StateEvent
from bmo.core.states import AssistantState, StateMachine
from bmo.language import detect_language, is_vision_request
from bmo.memory.context import ConversationContext
from bmo.models import AudioClip
from bmo.providers.base import CameraProvider, LLMProvider, STTProvider, TTSProvider
from bmo.tools.local import handle_local_command

LOGGER = logging.getLogger(__name__)


class AssistantController:
    def __init__(
        self,
        settings: Settings,
        *,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
        camera: CameraProvider | None = None,
        audio_input: Any | None = None,
        events: EventBus | None = None,
    ) -> None:
        self.settings = settings
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.camera = camera
        self.audio_input = audio_input
        self.events = events or EventBus()
        self.state_machine = StateMachine()
        self.context = ConversationContext(settings.memory.max_recent_turns)
        self.operation_id = 0
        self._active_task: asyncio.Task[Any] | None = None
        self._command_lock = asyncio.Lock()

    @property
    def state(self) -> AssistantState:
        return self.state_machine.state

    def _set_state(self, state: AssistantState, message: str = "") -> None:
        self.state_machine.transition(state)
        self.events.publish(StateEvent(state, self.operation_id, message))
        LOGGER.info("state=%s operation_id=%s message=%s", state, self.operation_id, message)

    async def start(self) -> None:
        self._set_state(AssistantState.WARMUP, "Initializing local providers")
        self._set_state(AssistantState.IDLE, "Press Enter to talk")

    async def begin_listening(self) -> int:
        async with self._command_lock:
            if self.state not in {AssistantState.IDLE, AssistantState.OFFLINE}:
                raise RuntimeError(f"cannot listen while state is {self.state}")
            self.operation_id += 1
            self._set_state(AssistantState.LISTENING, "Recording")
            return self.operation_id

    async def submit_audio(self, clip: AudioClip, *, allow_followup: bool = True) -> None:
        operation_id = self.operation_id
        task = asyncio.create_task(self._run_turn(clip, operation_id, allow_followup))
        self._active_task = task
        try:
            await task
        except asyncio.CancelledError:
            if operation_id == self.operation_id:
                raise
        finally:
            if self._active_task is task:
                self._active_task = None

    async def _run_turn(self, clip: AudioClip, operation_id: int, allow_followup: bool) -> None:
        try:
            self._set_state(AssistantState.TRANSCRIBING, "Transcribing")
            transcript = await self.stt.transcribe(clip)
            self._ensure_current(operation_id)
            if not transcript.text.strip():
                self._set_state(AssistantState.IDLE, "No speech detected")
                return

            language = detect_language(transcript.text, transcript.language)
            self._set_state(AssistantState.THINKING, "Routing request")
            reply_text: str | None = None
            local = handle_local_command(transcript.text, self.settings.app.timezone)
            if local and local[0] == "forget":
                self.context.clear()
                reply_text = (
                    "Я забыл текущий разговор. Уже отправленные данные регулируются "
                    "политикой провайдера."
                    if language == "ru"
                    else "I forgot this conversation. Previously sent data remains subject "
                    "to the provider policy."
                )
            elif local:
                reply_text = local[1]
            else:
                image = None
                if is_vision_request(transcript.text):
                    if self.camera is None:
                        reply_text = (
                            "Камера сейчас недоступна, поэтому я не буду придумывать, что вижу."
                            if language == "ru"
                            else "The camera is unavailable, so I will not pretend that I can see."
                        )
                    else:
                        self._set_state(AssistantState.VISION_CAPTURE, "Capturing one frame")
                        try:
                            image = await self.camera.capture()
                            self._ensure_current(operation_id)
                            self._set_state(AssistantState.THINKING, "Analyzing image")
                        except Exception as exc:
                            LOGGER.warning("camera capture failed: %s", exc)
                            reply_text = (
                                "Не удалось получить кадр с камеры. "
                                "Голосовой режим продолжает работать."
                                if language == "ru"
                                else "I could not capture a camera frame. "
                                "Voice mode is still available."
                            )
                if reply_text is None:
                    reply = await self.llm.respond(
                        transcript.text, self.context.messages(), image=image
                    )
                    self._ensure_current(operation_id)
                    reply_text = reply.text
                    self.context.append_turn(transcript.text, reply_text)

            assert reply_text is not None
            self._set_state(AssistantState.SPEAKING, reply_text)
            await self.tts.speak(reply_text, language, operation_id)
            self._ensure_current(operation_id)

            if allow_followup and self.audio_input is not None:
                await asyncio.sleep(self.settings.audio.anti_echo_cooldown_sec)
                self._ensure_current(operation_id)
                self._set_state(AssistantState.FOLLOW_UP_LISTENING, "Follow-up window")
                followup = await self.audio_input.record_followup(
                    self.settings.audio.followup_timeout_sec
                )
                self._ensure_current(operation_id)
                if followup is not None:
                    await self._run_turn(followup, operation_id, allow_followup=True)
                    return
            self._set_state(AssistantState.IDLE, "Ready")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if operation_id != self.operation_id:
                return
            LOGGER.error("turn failed: %s", type(exc).__name__)
            if self.state not in {AssistantState.ERROR, AssistantState.IDLE}:
                self._set_state(AssistantState.ERROR, type(exc).__name__)
            if self.state is not AssistantState.SPEAKING:
                message = "Облачный сервис сейчас недоступен. Попробуйте позже."
                try:
                    self._set_state(AssistantState.SPEAKING, message)
                    await self.tts.speak(message, "ru", operation_id)
                except Exception as tts_exc:
                    LOGGER.error("error announcement failed: %s", type(tts_exc).__name__)
            if self.state is not AssistantState.IDLE:
                self._set_state(AssistantState.IDLE, "Ready after error")

    def _ensure_current(self, operation_id: int) -> None:
        if operation_id != self.operation_id:
            raise asyncio.CancelledError

    async def cancel(self) -> None:
        self.operation_id += 1
        task = self._active_task
        if task and not task.done():
            task.cancel()
        with contextlib.suppress(Exception):
            await self.tts.cancel()
        if task:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if self.state not in {AssistantState.IDLE, AssistantState.ERROR}:
            try:
                self._set_state(AssistantState.IDLE, "Cancelled")
            except ValueError:
                self.state_machine.state = AssistantState.IDLE
                self.events.publish(StateEvent(AssistantState.IDLE, self.operation_id, "Cancelled"))
