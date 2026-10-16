from __future__ import annotations

from pathlib import Path

import pytest

from bmo.config import load_settings


def test_defaults_are_safe(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.yaml")
    assert settings.cloud.llm_model == "gpt-6-luna"
    assert settings.cloud.stt_model == "gpt-transcribe"
    assert settings.cloud.store_responses is False
    assert settings.cloud.use_web_search is False
    assert settings.app.headless is True


def test_missing_environment_placeholder_keeps_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BMO_LLM_MODEL", raising=False)
    config = tmp_path / "config.yaml"
    config.write_text('cloud:\n  llm_model: "${BMO_LLM_MODEL}"\n', encoding="utf-8")
    assert load_settings(config).cloud.llm_model == "gpt-6-luna"


def test_store_true_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("cloud:\n  store_responses: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="store_responses"):
        load_settings(config)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("audio:\n  magic_device: 7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown configuration"):
        load_settings(config)


def test_unpriced_model_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("cloud:\n  llm_model: unpriced-model\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verified pricing"):
        load_settings(config)
