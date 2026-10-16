from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def handle_local_command(text: str, timezone: str) -> tuple[str, str] | None:
    normalized = " ".join(text.casefold().split()).strip("?!.,")
    if normalized in {"забудь наш разговор", "forget our conversation"}:
        return "forget", ""
    if normalized in {"который час", "сколько времени", "what time is it"}:
        now = datetime.now(ZoneInfo(timezone))
        if normalized.startswith("what"):
            return "reply", now.strftime("It is %H:%M.")
        return "reply", now.strftime("Сейчас %H:%M.")
    if normalized in {"статус системы", "system status"}:
        load = os.getloadavg()[0]
        if normalized.startswith("system"):
            return "reply", f"System is running. One-minute load is {load:.2f}."
        return "reply", f"Система работает. Средняя нагрузка за минуту — {load:.2f}."
    return None
