from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import numpy as np

from bmo.config import SpeechConfig


def normalize_for_speech(text: str) -> str:
    # Remove emoji and pictographic symbols before speech synthesis.
    text = re.sub(
        r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]",
        "",
        text,
    )
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_#>|]", " ", text)
    text = re.sub(r"https?://\S+", "ссылка", text)
    return re.sub(r"\s+", " ", text).strip()


class PiperTTSProvider:
    def __init__(self, config: SpeechConfig, audio_output: object) -> None:
        self.config = config
        self.audio_output = audio_output
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    def _model_for(self, language: str) -> Path:
        return Path(self.config.voice_ru if language.startswith("ru") else self.config.voice_en)

    @staticmethod
    def _sample_rate(model: Path) -> int:
        config_path = Path(f"{model}.json")
        if not model.exists() or not config_path.exists():
            raise FileNotFoundError(
                f"Piper model or JSON is missing: {model}; run 'bmo assets install-voices'"
            )
        metadata = json.loads(config_path.read_text(encoding="utf-8"))
        return int(metadata["audio"]["sample_rate"])

    async def speak(self, text: str, language: str, operation_id: int) -> None:
        clean = normalize_for_speech(text)
        if not clean:
            return
        model = self._model_for(language)
        sample_rate = self._sample_rate(model)
        async with self._lock:
            self._process = await asyncio.create_subprocess_exec(
                self.config.piper_executable,
                "--model",
                str(model),
                "--output-raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await self._process.communicate((clean + "\n").encode("utf-8"))
            return_code = self._process.returncode
            self._process = None
            if return_code:
                error_text = stderr[-500:].decode(errors="replace")
                raise RuntimeError(f"Piper failed with code {return_code}: {error_text}")
            samples = np.frombuffer(stdout, dtype=np.int16)
            await self.audio_output.play(samples, sample_rate)

    async def cancel(self) -> None:
        process = self._process
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except TimeoutError:
                process.kill()
                await process.wait()
        await self.audio_output.cancel()
