from __future__ import annotations

import pytest

from bmo.cli import _parser
from bmo.headless import run_interactive


def test_run_modes_are_separate() -> None:
    parser = _parser()

    assert parser.parse_args(["run", "--interactive"]).run_mode == "interactive"
    assert parser.parse_args(["run", "--service"]).run_mode == "service"


def test_legacy_headless_flag_remains_compatible() -> None:
    args = _parser().parse_args(["run", "--headless"])

    assert args.run_mode == "interactive"


def test_control_command_uses_configured_action() -> None:
    args = _parser().parse_args(["control", "ptt-start"])

    assert args.command == "control"
    assert args.action == "ptt-start"


@pytest.mark.asyncio
async def test_interactive_mode_refuses_non_terminal_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bmo.headless.sys.stdin.isatty", lambda: False)

    with pytest.raises(RuntimeError, match="requires a terminal"):
        await run_interactive(None, None)  # type: ignore[arg-type]
