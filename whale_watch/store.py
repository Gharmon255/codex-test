from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Signal


@dataclass(frozen=True)
class StoredSignal:
    id: int
    tx_hash: str
    symbol: str
    direction: str
    score: int
    signal_time: datetime
    entry_price_usd: float | None


class SignalStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record_signal(self, signal: Signal, entry_price_usd: float | None) -> None:
        event = signal.event
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    tx_hash, symbol, direction, score, signal_time, amount_usd,
                    entry_price_usd, reviewed_at, follow_up_price_usd,
                    outcome, move_percent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    event.tx_hash,
                    event.symbol.upper(),
                    signal.direction,
                    signal.score,
                    event.timestamp.astimezone(timezone.utc).isoformat(),
                    event.amount_usd,
                    entry_price_usd,
                ),
            )

    def due_signals(self, follow_up_minutes: int) -> list[StoredSignal]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=follow_up_minutes)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, tx_hash, symbol, direction, score, signal_time, entry_price_usd
                FROM signals
                WHERE reviewed_at IS NULL
                  AND entry_price_usd IS NOT NULL
                  AND signal_time <= ?
                ORDER BY signal_time ASC
                """,
                (cutoff.isoformat(),),
            ).fetchall()
        return [_stored_signal(row) for row in rows]

    def mark_reviewed(self, signal_id: int, follow_up_price_usd: float, outcome: str, move_percent: float) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE signals
                SET reviewed_at = ?, follow_up_price_usd = ?, outcome = ?, move_percent = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), follow_up_price_usd, outcome, move_percent, signal_id),
            )

    def outcome_summary(self, min_samples: int) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT symbol, direction,
                       COUNT(*) AS samples,
                       SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS wins,
                       AVG(move_percent) AS avg_move
                FROM signals
                WHERE outcome IS NOT NULL
                GROUP BY symbol, direction
                HAVING COUNT(*) >= ?
                """,
                (min_samples,),
            ).fetchall()
        return [
            {
                "symbol": row["symbol"],
                "direction": row["direction"],
                "samples": int(row["samples"]),
                "wins": int(row["wins"]),
                "success_rate": float(row["wins"]) / float(row["samples"]),
                "avg_move": float(row["avg_move"] or 0.0),
            }
            for row in rows
        ]

    def get_threshold_multipliers(self) -> dict[str, float]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT symbol, multiplier FROM threshold_adjustments").fetchall()
        return {str(row["symbol"]).upper(): float(row["multiplier"]) for row in rows}

    def set_threshold_multiplier(self, symbol: str, multiplier: float) -> None:
        multiplier = min(5.0, max(0.2, multiplier))
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO threshold_adjustments (symbol, multiplier, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET multiplier = excluded.multiplier, updated_at = excluded.updated_at
                """,
                (symbol.upper(), multiplier, datetime.now(timezone.utc).isoformat()),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    signal_time TEXT NOT NULL,
                    amount_usd REAL NOT NULL,
                    entry_price_usd REAL,
                    reviewed_at TEXT,
                    follow_up_price_usd REAL,
                    outcome TEXT,
                    move_percent REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threshold_adjustments (
                    symbol TEXT PRIMARY KEY,
                    multiplier REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


def _stored_signal(row: sqlite3.Row) -> StoredSignal:
    return StoredSignal(
        id=int(row["id"]),
        tx_hash=str(row["tx_hash"]),
        symbol=str(row["symbol"]),
        direction=str(row["direction"]),
        score=int(row["score"]),
        signal_time=datetime.fromisoformat(str(row["signal_time"])),
        entry_price_usd=float(row["entry_price_usd"]) if row["entry_price_usd"] is not None else None,
    )
