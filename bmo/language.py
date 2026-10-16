from __future__ import annotations

import re


def detect_language(text: str, hint: str | None = None) -> str:
    if hint:
        normalized = hint.casefold().split("-")[0].split("_")[0]
        if normalized in {"ru", "en"}:
            return normalized
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyrillic > latin else "en"


def is_vision_request(text: str) -> bool:
    lowered = text.casefold()
    phrases = (
        "что ты видишь",
        "что видишь",
        "посмотри",
        "сделай фото",
        "какого цвета",
        "прочитай надпись",
        "what do you see",
        "look at",
        "take a photo",
        "what color",
        "read the text",
    )
    return any(phrase in lowered for phrase in phrases)
