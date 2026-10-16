from __future__ import annotations

import os
from pathlib import Path

import pytest

from bmo.security import load_dotenv_secure


def test_secure_dotenv_loads_without_shell_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".env"
    path.write_text("BMO_TEST_VALUE='literal $HOME'\n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.delenv("BMO_TEST_VALUE", raising=False)
    load_dotenv_secure(path)
    assert os.environ["BMO_TEST_VALUE"] == "literal $HOME"


def test_insecure_dotenv_permissions_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="0600"):
        load_dotenv_secure(path)
