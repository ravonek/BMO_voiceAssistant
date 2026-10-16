from __future__ import annotations

from collections import deque


class ConversationContext:
    def __init__(self, max_turns: int = 12) -> None:
        self._messages: deque[dict[str, str]] = deque(maxlen=max_turns * 2)

    def append_turn(self, user: str, assistant: str) -> None:
        self._messages.append({"role": "user", "content": user})
        self._messages.append({"role": "assistant", "content": assistant})

    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
