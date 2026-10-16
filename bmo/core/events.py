from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Any

from bmo.core.states import AssistantState


@dataclass(slots=True, frozen=True)
class StateEvent:
    state: AssistantState
    operation_id: int
    message: str = ""
    monotonic_time: float = 0.0
    details: dict[str, Any] | None = None


class EventBus:
    def __init__(self, maxsize: int = 64) -> None:
        self._queue: asyncio.Queue[StateEvent] = asyncio.Queue(maxsize=maxsize)

    def publish(self, event: StateEvent) -> None:
        if not event.monotonic_time:
            event = StateEvent(
                state=event.state,
                operation_id=event.operation_id,
                message=event.message,
                monotonic_time=monotonic(),
                details=event.details,
            )
        if self._queue.full():
            self._queue.get_nowait()
            self._queue.task_done()
        self._queue.put_nowait(event)

    async def next(self) -> StateEvent:
        return await self._queue.get()
