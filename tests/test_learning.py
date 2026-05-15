from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from whale_watch.config import (
    AlertConfig,
    AppConfig,
    AssetConfig,
    BotConfig,
    LearningConfig,
    SignalConfig,
    WhaleAlertConfig,
)
from whale_watch.learner import tune_thresholds
from whale_watch.models import Signal, WalletLabel, WhaleEvent
from whale_watch.store import SignalStore


def _config(auto_tune: bool = False) -> AppConfig:
    return AppConfig(
        bot=BotConfig(poll_seconds=120, lookback_minutes=20, dry_run=True),
        whale_alert=WhaleAlertConfig(api_key="", min_usd_value=1_000_000),
        signals=SignalConfig(alert_score_threshold=55),
        alerts=AlertConfig(console=True, webhook_url="", telegram_url="", telegram_chat_id=""),
        learning=LearningConfig(
            enabled=True,
            auto_tune=auto_tune,
            database_path=":memory:",
            follow_up_minutes=60,
            min_move_percent=1.5,
            min_samples=2,
            low_success_rate=0.4,
            high_success_rate=0.68,
            tune_step_percent=15.0,
        ),
        assets={"BTC": AssetConfig(key="BTC", symbol="btc", display_name="Bitcoin", whale_usd=5_000_000)},
    )


class LearningTests(unittest.TestCase):
    def test_due_signal_review_and_auto_tune_records_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SignalStore(f"{tmp}/signals.sqlite3")
            signal = _signal("tx-a")
            store.record_signal(signal, 100.0)
            due = store.due_signals(follow_up_minutes=60)
            self.assertEqual(len(due), 1)

            store.mark_reviewed(due[0].id, follow_up_price_usd=90.0, outcome="miss", move_percent=-10.0)
            signal = _signal("tx-b")
            store.record_signal(signal, 100.0)
            due = store.due_signals(follow_up_minutes=60)
            store.mark_reviewed(due[0].id, follow_up_price_usd=91.0, outcome="miss", move_percent=-9.0)

            notes = tune_thresholds(_config(auto_tune=True), store)

            self.assertTrue(notes)
            self.assertGreater(store.get_threshold_multipliers()["BTC"], 1.0)


def _signal(tx_hash: str) -> Signal:
    event = WhaleEvent(
        tx_hash=tx_hash,
        blockchain="bitcoin",
        symbol="btc",
        amount=100,
        amount_usd=10_000_000,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        sender=WalletLabel("exchange", "Binance", "exchange"),
        receiver=WalletLabel("wallet", "Unknown", "unknown"),
    )
    return Signal(
        event=event,
        direction="bullish",
        score=80,
        title="Possible Bitcoin accumulation",
        reasons=("test",),
    )


if __name__ == "__main__":
    unittest.main()
