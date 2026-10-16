from __future__ import annotations

from enum import StrEnum


class AssistantState(StrEnum):
    BOOTING = "booting"
    WARMUP = "warmup"
    IDLE = "idle"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    VISION_CAPTURE = "vision_capture"
    SPEAKING = "speaking"
    FOLLOW_UP_LISTENING = "follow_up_listening"
    SLEEPING = "sleeping"
    OFFLINE = "offline"
    ERROR = "error"


ALLOWED_TRANSITIONS: dict[AssistantState, set[AssistantState]] = {
    AssistantState.BOOTING: {AssistantState.WARMUP, AssistantState.ERROR},
    AssistantState.WARMUP: {AssistantState.IDLE, AssistantState.OFFLINE, AssistantState.ERROR},
    AssistantState.IDLE: {
        AssistantState.WAKE_DETECTED,
        AssistantState.LISTENING,
        AssistantState.SLEEPING,
        AssistantState.OFFLINE,
        AssistantState.ERROR,
    },
    AssistantState.WAKE_DETECTED: {AssistantState.LISTENING, AssistantState.IDLE},
    AssistantState.LISTENING: {
        AssistantState.TRANSCRIBING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.TRANSCRIBING: {
        AssistantState.THINKING,
        AssistantState.IDLE,
        AssistantState.OFFLINE,
        AssistantState.ERROR,
    },
    AssistantState.THINKING: {
        AssistantState.VISION_CAPTURE,
        AssistantState.SPEAKING,
        AssistantState.IDLE,
        AssistantState.OFFLINE,
        AssistantState.ERROR,
    },
    AssistantState.VISION_CAPTURE: {
        AssistantState.THINKING,
        AssistantState.SPEAKING,
        AssistantState.ERROR,
    },
    AssistantState.SPEAKING: {
        AssistantState.FOLLOW_UP_LISTENING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.FOLLOW_UP_LISTENING: {
        AssistantState.TRANSCRIBING,
        AssistantState.IDLE,
        AssistantState.ERROR,
    },
    AssistantState.SLEEPING: {AssistantState.IDLE},
    AssistantState.OFFLINE: {AssistantState.IDLE, AssistantState.LISTENING, AssistantState.ERROR},
    AssistantState.ERROR: {
        AssistantState.IDLE,
        AssistantState.OFFLINE,
        AssistantState.SPEAKING,
    },
}


class StateMachine:
    def __init__(self) -> None:
        self.state = AssistantState.BOOTING

    def transition(self, target: AssistantState) -> None:
        if target == self.state:
            return
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"invalid state transition: {self.state} -> {target}")
        self.state = target
