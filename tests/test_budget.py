from __future__ import annotations

from pathlib import Path

import pytest

from bmo.budget import BudgetExceeded, BudgetGuard, estimate_stt_cost
from bmo.models import UsageRecord


def make_guard(tmp_path: Path, daily: float = 0.01) -> BudgetGuard:
    return BudgetGuard(
        tmp_path / "budget.sqlite3",
        timezone="Asia/Almaty",
        daily_hard_limit_usd=daily,
        monthly_hard_limit_usd=1.0,
    )


def test_reserve_and_settle_survive_new_instance(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)
    token = guard.reserve(0.005)
    assert guard.status().reserved_usd == pytest.approx(0.005)
    guard.settle(
        token,
        UsageRecord(provider="openai", model="gpt-6-luna", estimated_cost_usd=0.003),
    )
    status = make_guard(tmp_path).status()
    assert status.reserved_usd == 0
    assert status.daily_usd == pytest.approx(0.003)


def test_hard_stop_counts_reservations(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)
    guard.reserve(0.008)
    with pytest.raises(BudgetExceeded):
        guard.reserve(0.003)


def test_release_prevents_phantom_spend(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)
    token = guard.reserve(0.009)
    guard.release(token)
    assert guard.status().reserved_usd == 0


def test_stt_estimate_is_duration_based() -> None:
    assert estimate_stt_cost(60) == pytest.approx(0.0045)
