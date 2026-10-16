from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bmo.models import UsageRecord


class BudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class BudgetStatus:
    daily_usd: float
    monthly_usd: float
    reserved_usd: float
    daily_hard_limit_usd: float
    monthly_hard_limit_usd: float
    override_until: datetime | None


class BudgetGuard:
    def __init__(
        self,
        database: Path,
        *,
        timezone: str,
        daily_hard_limit_usd: float,
        monthly_hard_limit_usd: float,
    ) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self.timezone = ZoneInfo(timezone)
        self.daily_limit = daily_hard_limit_usd
        self.monthly_limit = monthly_hard_limit_usd
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    cost_usd REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    token TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    amount_usd REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def _period_bounds(self) -> tuple[str, str]:
        now = datetime.now(self.timezone)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month = day.replace(day=1)
        return day.astimezone(UTC).isoformat(), month.astimezone(UTC).isoformat()

    def _override_until(self, db: sqlite3.Connection) -> datetime | None:
        row = db.execute("SELECT value FROM settings WHERE key='override_until'").fetchone()
        if not row:
            return None
        try:
            return datetime.fromisoformat(row["value"])
        except ValueError:
            return None

    def status(self) -> BudgetStatus:
        day_start, month_start = self._period_bounds()
        with self._connect() as db:
            daily = db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM usage WHERE created_at >= ?",
                (day_start,),
            ).fetchone()["total"]
            monthly = db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM usage WHERE created_at >= ?",
                (month_start,),
            ).fetchone()["total"]
            reserved = db.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) AS total FROM reservations"
            ).fetchone()["total"]
            override_until = self._override_until(db)
        return BudgetStatus(
            daily,
            monthly,
            reserved,
            self.daily_limit,
            self.monthly_limit,
            override_until,
        )

    def reserve(self, estimated_cost_usd: float) -> str:
        if estimated_cost_usd < 0:
            raise ValueError("estimated cost cannot be negative")
        with self._lock:
            status = self.status()
            now = datetime.now(UTC)
            overridden = status.override_until is not None and status.override_until > now
            projected_day = status.daily_usd + status.reserved_usd + estimated_cost_usd
            projected_month = status.monthly_usd + status.reserved_usd + estimated_cost_usd
            if not overridden and (
                projected_day > self.daily_limit or projected_month > self.monthly_limit
            ):
                raise BudgetExceeded(
                    f"local API budget hard stop: day=${projected_day:.4f}, "
                    f"month=${projected_month:.4f}"
                )
            token = uuid.uuid4().hex
            with self._connect() as db:
                db.execute(
                    "INSERT INTO reservations(token, created_at, amount_usd) VALUES(?, ?, ?)",
                    (token, now.isoformat(), estimated_cost_usd),
                )
            return token

    def settle(self, token: str, usage: UsageRecord) -> None:
        import json

        with self._lock, self._connect() as db:
            row = db.execute("SELECT token FROM reservations WHERE token=?", (token,)).fetchone()
            if not row:
                raise ValueError("unknown or already settled budget reservation")
            db.execute("DELETE FROM reservations WHERE token=?", (token,))
            db.execute(
                "INSERT INTO usage(created_at, provider, model, cost_usd, metadata) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    usage.provider,
                    usage.model,
                    usage.estimated_cost_usd,
                    json.dumps(usage.metadata, separators=(",", ":")),
                ),
            )

    def release(self, token: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM reservations WHERE token=?", (token,))

    def enable_override(self, minutes: int) -> datetime:
        if not 1 <= minutes <= 60:
            raise ValueError("override duration must be between 1 and 60 minutes")
        until = datetime.now(UTC) + timedelta(minutes=minutes)
        with self._connect() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES('override_until', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (until.isoformat(),),
            )
        return until


def estimate_stt_cost(duration_sec: float) -> float:
    return max(duration_sec, 1.0) / 60.0 * 0.0045


def estimate_llm_reserve(input_text: str, max_output_tokens: int, has_image: bool) -> float:
    estimated_input_tokens = max(1, len(input_text) // 4)
    text_cost = estimated_input_tokens / 1_000_000 * 0.10
    output_cost = max_output_tokens / 1_000_000 * 0.50
    image_reserve = 0.005 if has_image else 0.0
    return max(0.001, text_cost + output_cost + image_reserve)
