from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")


@dataclass(slots=True)
class AppConfig:
    language: str = "auto"
    headless: bool = True
    timezone: str = "Asia/Almaty"
    log_format: str = "plain"


@dataclass(slots=True)
class AudioConfig:
    preferred_input_name: str = "KT USB Audio"
    preferred_output_name: str = "KT USB Audio"
    sample_rate: int = 16_000
    channels: int = 1
    followup_timeout_sec: float = 5.0
    anti_echo_cooldown_sec: float = 0.35
    start_speech_timeout_sec: float = 10.0
    end_silence_sec: float = 1.2
    max_utterance_sec: float = 30.0
    vad_rms_threshold: int = 500


@dataclass(slots=True)
class CameraConfig:
    usb_vid: str = "0bda"
    usb_pid: str = "5842"
    device: str = "auto"
    format: str = "YUYV"
    width: int = 640
    height: int = 480
    fps: int = 30
    rotation: int = 0
    keep_photos: bool = False


@dataclass(slots=True)
class CloudConfig:
    llm_model: str = "gpt-6-luna"
    stt_model: str = "gpt-transcribe"
    reasoning_effort: str = "none"
    max_output_tokens: int = 300
    request_timeout_sec: float = 30.0
    max_retries: int = 2
    store_responses: bool = False
    use_web_search: bool = False
    daily_warning_usd: float = 0.20
    daily_hard_limit_usd: float = 0.40
    monthly_warning_usd: float = 3.50
    monthly_hard_limit_usd: float = 4.50


@dataclass(slots=True)
class SpeechConfig:
    piper_executable: str = "piper"
    voice_ru: str = "voices/ru_RU-dmitri-medium.onnx"
    voice_en: str = "voices/en_US-kristin-medium.onnx"


@dataclass(slots=True)
class MemoryConfig:
    max_recent_turns: int = 12
    persist_transcripts: bool = False


@dataclass(slots=True)
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    state_dir: Path = field(default_factory=lambda: Path.home() / ".local/state/bmo")

    def validate(self) -> None:
        if self.app.language not in {"auto", "ru", "en"}:
            raise ValueError("app.language must be auto, ru, or en")
        if self.cloud.store_responses:
            raise ValueError("cloud.store_responses must remain false")
        if self.cloud.use_web_search:
            raise ValueError("web search is outside the MVP and must remain disabled")
        if self.cloud.llm_model != "gpt-6-luna":
            raise ValueError("this release has verified pricing only for gpt-6-luna")
        if self.cloud.stt_model != "gpt-transcribe":
            raise ValueError("this release has verified pricing only for gpt-transcribe")
        if self.audio.channels != 1:
            raise ValueError("MVP audio capture must be mono")
        if not 3.0 <= self.audio.followup_timeout_sec <= 5.0:
            raise ValueError("followup timeout must be between 3 and 5 seconds")
        if self.cloud.daily_hard_limit_usd <= 0 or self.cloud.monthly_hard_limit_usd <= 0:
            raise ValueError("budget hard limits must be positive")
        if self.cloud.daily_hard_limit_usd > self.cloud.monthly_hard_limit_usd:
            raise ValueError("daily hard limit cannot exceed monthly hard limit")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["state_dir"] = str(self.state_dir)
        return result


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        match = _ENV_PATTERN.match(value)
        if match:
            return os.getenv(match.group(1), value)
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


def _merge_dataclass(target: Any, values: dict[str, Any]) -> None:
    unknown = set(values) - set(target.__dataclass_fields__)
    if unknown:
        raise ValueError(
            f"unknown configuration keys for {type(target).__name__}: {sorted(unknown)}"
        )
    for key, value in values.items():
        if isinstance(value, str):
            match = _ENV_PATTERN.match(value)
            if match:
                environment_value = os.getenv(match.group(1))
                if environment_value is None:
                    continue
                value = environment_value
        setattr(target, key, value)


def load_settings(path: Path | None = None) -> Settings:
    settings = Settings()
    config_path = path or Path(os.getenv("BMO_CONFIG", Path.home() / ".config/bmo/config.yaml"))
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("configuration root must be a mapping")
        raw = _resolve_env(raw)
        allowed = {"app", "audio", "camera", "cloud", "speech", "memory", "state_dir"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown configuration sections: {sorted(unknown)}")
        for section in ("app", "audio", "camera", "cloud", "speech", "memory"):
            if section in raw:
                _merge_dataclass(getattr(settings, section), raw[section])
        if "state_dir" in raw:
            settings.state_dir = Path(raw["state_dir"]).expanduser()

    settings.cloud.llm_model = os.getenv("BMO_LLM_MODEL", settings.cloud.llm_model)
    settings.cloud.stt_model = os.getenv("BMO_STT_MODEL", settings.cloud.stt_model)
    settings.validate()
    return settings
