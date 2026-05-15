from __future__ import annotations

import unittest
from datetime import datetime, timezone

from whale_watch.config import (
    AlertConfig,
    AppConfig,
    AssetConfig,
    BotConfig,
    LearningConfig,
    SignalConfig,
    WhaleAlertConfig,
)
from whale_watch.models import WalletLabel, WhaleEvent
from whale_watch.signals import score_event, should_alert


def _config() -> AppConfig:
    return AppConfig(
        bot=BotConfig(poll_seconds=120, lookback_minutes=20, dry_run=True),
        whale_alert=WhaleAlertConfig(api_key="", min_usd_value=1_000_000),
        signals=SignalConfig(alert_score_threshold=55),
        alerts=AlertConfig(console=True, webhook_url="", telegram_url="", telegram_chat_id=""),
        learning=LearningConfig(
            enabled=True,
            auto_tune=False,
            database_path=":memory:",
            follow_up_minutes=240,
            min_move_percent=1.5,
            min_samples=8,
            low_success_rate=0.4,
            high_success_rate=0.68,
            tune_step_percent=15.0,
        ),
        assets={"BTC": AssetConfig(key="BTC", symbol="btc", display_name="Bitcoin", whale_usd=5_000_000)},
    )


class SignalTests(unittest.TestCase):
    def test_exchange_outflow_scores_bullish(self) -> None:
        event = WhaleEvent(
            tx_hash="tx1",
            blockchain="bitcoin",
            symbol="btc",
            amount=100,
            amount_usd=10_000_000,
            timestamp=datetime.now(timezone.utc),
            sender=WalletLabel("exchange", "Binance", "exchange"),
            receiver=WalletLabel("wallet", "Unknown", "unknown"),
        )

        signal = score_event(event, _config())

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.direction, "bullish")
        self.assertTrue(should_alert(signal, _config()))

    def test_exchange_inflow_scores_bearish(self) -> None:
        event = WhaleEvent(
            tx_hash="tx2",
            blockchain="bitcoin",
            symbol="btc",
            amount=100,
            amount_usd=10_000_000,
            timestamp=datetime.now(timezone.utc),
            sender=WalletLabel("wallet", "Unknown", "unknown"),
            receiver=WalletLabel("exchange", "Coinbase", "exchange"),
        )

        signal = score_event(event, _config())

        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.direction, "bearish")
        self.assertTrue(should_alert(signal, _config()))


if __name__ == "__main__":
    unittest.main()
