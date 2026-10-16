from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from bmo.budget import BudgetGuard, estimate_llm_reserve, estimate_stt_cost
from bmo.config import CloudConfig
from bmo.models import AudioClip, CapturedFrame, ModelReply, Transcript, UsageRecord

GPT_6_LUNA_INPUT_PER_MILLION_USD = 0.10
GPT_6_LUNA_OUTPUT_PER_MILLION_USD = 0.50
GPT_TRANSCRIBE_PER_MINUTE_USD = 0.0045


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    value = getattr(usage, name, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(name)
    return int(value or 0)


class OpenAIProviders:
    """OpenAI STT and Responses clients sharing one SDK client and budget guard."""

    def __init__(
        self,
        config: CloudConfig,
        budget: BudgetGuard,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.config = config
        self.budget = budget
        self.client = client or AsyncOpenAI(
            timeout=config.request_timeout_sec,
            max_retries=config.max_retries,
        )

    async def transcribe(self, clip: AudioClip) -> Transcript:
        estimated_cost = estimate_stt_cost(clip.duration_sec)
        reservation = self.budget.reserve(estimated_cost)
        try:
            result = await self.client.audio.transcriptions.create(
                model=self.config.stt_model,
                file=("speech.wav", clip.wav_bytes, "audio/wav"),
            )
            text = str(getattr(result, "text", "")).strip()
            languages = getattr(result, "languages", None) or []
            language = None
            if languages:
                first = languages[0]
                language = getattr(first, "code", None)
                if language is None and isinstance(first, dict):
                    language = first.get("code")
            usage = UsageRecord(
                provider="openai",
                model=self.config.stt_model,
                audio_seconds=clip.duration_sec,
                estimated_cost_usd=clip.duration_sec / 60 * GPT_TRANSCRIBE_PER_MINUTE_USD,
            )
            self.budget.settle(reservation, usage)
            return Transcript(text=text, language=language, duration_sec=clip.duration_sec)
        except Exception:
            self.budget.settle(
                reservation,
                UsageRecord(
                    provider="openai",
                    model=self.config.stt_model,
                    audio_seconds=clip.duration_sec,
                    estimated_cost_usd=estimated_cost,
                    metadata={"outcome": "error_or_cancelled_conservative_reserve"},
                ),
            )
            raise

    async def respond(
        self,
        text: str,
        history: Sequence[dict[str, str]],
        image: CapturedFrame | None = None,
    ) -> ModelReply:
        estimated_cost = estimate_llm_reserve(
            text, self.config.max_output_tokens, image is not None
        )
        reservation = self.budget.reserve(estimated_cost)
        system = (
            "You are BMO, a friendly, playful desktop robot. Reply in the user's language. "
            "Be truthful about unavailable sensors and keep answers to 1-3 short sentences. "
            "Do not claim to see anything unless an image is included."
	    "Do not use emojis, emoticons, or decorative symbols in your replies. "
        )
        input_items: list[dict[str, Any]] = [
            {"role": "developer", "content": system},
            *[{"role": item["role"], "content": item["content"]} for item in history],
        ]
        if image is None:
            input_items.append({"role": "user", "content": text})
        else:
            encoded = base64.b64encode(image.jpeg_bytes).decode("ascii")
            input_items.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": text},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{encoded}",
                            "detail": "low",
                        },
                    ],
                }
            )
        try:
            response = await self.client.responses.create(
                model=self.config.llm_model,
                reasoning={"effort": self.config.reasoning_effort},
                input=input_items,
                max_output_tokens=self.config.max_output_tokens,
                store=False,
            )
            input_tokens = _usage_value(getattr(response, "usage", None), "input_tokens")
            output_tokens = _usage_value(getattr(response, "usage", None), "output_tokens")
            cost = (
                input_tokens / 1_000_000 * GPT_6_LUNA_INPUT_PER_MILLION_USD
                + output_tokens / 1_000_000 * GPT_6_LUNA_OUTPUT_PER_MILLION_USD
            )
            usage = UsageRecord(
                provider="openai",
                model=self.config.llm_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                vision_images=int(image is not None),
                estimated_cost_usd=cost,
            )
            self.budget.settle(reservation, usage)
            return ModelReply(text=response.output_text.strip(), usage=usage)
        except Exception:
            self.budget.settle(
                reservation,
                UsageRecord(
                    provider="openai",
                    model=self.config.llm_model,
                    vision_images=int(image is not None),
                    estimated_cost_usd=estimated_cost,
                    metadata={"outcome": "error_or_cancelled_conservative_reserve"},
                ),
            )
            raise
