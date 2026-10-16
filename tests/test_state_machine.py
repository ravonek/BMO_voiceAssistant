from __future__ import annotations

import pytest

from bmo.core.states import AssistantState, StateMachine


def test_happy_path_transitions() -> None:
    machine = StateMachine()
    for state in (
        AssistantState.WARMUP,
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.TRANSCRIBING,
        AssistantState.THINKING,
        AssistantState.SPEAKING,
        AssistantState.FOLLOW_UP_LISTENING,
        AssistantState.IDLE,
    ):
        machine.transition(state)
    assert machine.state is AssistantState.IDLE


def test_invalid_transition_is_rejected() -> None:
    machine = StateMachine()
    with pytest.raises(ValueError, match="invalid state transition"):
        machine.transition(AssistantState.SPEAKING)
