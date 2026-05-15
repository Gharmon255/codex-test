from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path


@dataclass(frozen=True)
class AssetConfig:
    key: str
    symbol: str
    display_name: str
    whale_usd: float


@dataclass(frozen=True)
class BotConfig:
    poll_seconds: int
    lookback_minutes: int
    dry_run: bool


@dataclass(frozen=True)
class WhaleAlertConfig:
    api_key: str
    min_usd_value: float


@dataclass(frozen=True)
class SignalConfig:
    alert_score_threshold: int


@dataclass(frozen=True)
class AlertConfig:
    console: bool
    webhook_url: str
    telegram_url: str
    telegram_chat_id: str


@dataclass(frozen=True)
class LearningConfig:
    enabled: bool
    auto_tune: bool
    database_path: str
    follow_up_minutes: int
    min_move_percent: float
    min_samples: int
    low_success_rate: float
    high_success_rate: float
    tune_step_percent: float


@dataclass(frozen=True)
class AppConfig:
    bot: BotConfig
    whale_alert: WhaleAlertConfig
    signals: SignalConfig
    alerts: AlertConfig
    learning: LearningConfig
    assets: dict[str, AssetConfig]


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    bot_data = data.get("bot", {})
    whale_data = data.get("whale_alert", {})
    signal_data = data.get("signals", {})
    alert_data = data.get("alerts", {})
    learning_data = data.get("learning", {})
    asset_data = data.get("assets", {})

    api_key = os.getenv("WHALE_ALERT_API_KEY", whale_data.get("api_key", ""))

    assets = {
        key.upper(): AssetConfig(
            key=key.upper(),
            symbol=str(value["symbol"]).lower(),
            display_name=str(value.get("display_name", key.upper())),
            whale_usd=float(value.get("whale_usd", whale_data.get("min_usd_value", 1_000_000))),
        )
        for key, value in asset_data.items()
    }

    return AppConfig(
        bot=BotConfig(
            poll_seconds=int(bot_data.get("poll_seconds", 120)),
            lookback_minutes=int(bot_data.get("lookback_minutes", 20)),
            dry_run=bool(bot_data.get("dry_run", False)),
        ),
        whale_alert=WhaleAlertConfig(
            api_key=str(api_key),
            min_usd_value=float(whale_data.get("min_usd_value", 1_000_000)),
        ),
        signals=SignalConfig(
            alert_score_threshold=int(signal_data.get("alert_score_threshold", 55)),
        ),
        alerts=AlertConfig(
            console=bool(alert_data.get("console", True)),
            webhook_url=str(alert_data.get("webhook_url", "")),
            telegram_url=str(alert_data.get("telegram_url", "")),
            telegram_chat_id=str(alert_data.get("telegram_chat_id", "")),
        ),
        learning=LearningConfig(
            enabled=bool(learning_data.get("enabled", True)),
            auto_tune=bool(learning_data.get("auto_tune", False)),
            database_path=str(learning_data.get("database_path", "data/whale_watch.sqlite3")),
            follow_up_minutes=int(learning_data.get("follow_up_minutes", 240)),
            min_move_percent=float(learning_data.get("min_move_percent", 1.5)),
            min_samples=int(learning_data.get("min_samples", 8)),
            low_success_rate=float(learning_data.get("low_success_rate", 0.4)),
            high_success_rate=float(learning_data.get("high_success_rate", 0.68)),
            tune_step_percent=float(learning_data.get("tune_step_percent", 15.0)),
        ),
        assets=assets,
    )


def apply_threshold_multipliers(config: AppConfig, multipliers: dict[str, float]) -> AppConfig:
    if not multipliers:
        return config

    adjusted_assets = {}
    for key, asset in config.assets.items():
        multiplier = multipliers.get(key.upper(), 1.0)
        adjusted_assets[key] = replace(asset, whale_usd=max(1.0, asset.whale_usd * multiplier))
    return replace(config, assets=adjusted_assets)
