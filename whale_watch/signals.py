from __future__ import annotations

from .config import AppConfig
from .models import Signal, WhaleEvent


def score_event(event: WhaleEvent, config: AppConfig) -> Signal | None:
    asset = config.assets.get(event.symbol.upper())
    if asset is None or event.amount_usd < asset.whale_usd:
        return None

    reasons: list[str] = []
    score = min(45, int(event.amount_usd / asset.whale_usd * 12))
    direction = "neutral"
    title = f"{asset.display_name} whale transfer"

    if event.sender.is_exchange and not event.receiver.is_exchange:
        direction = "bullish"
        score += 35
        title = f"Possible {asset.display_name} accumulation"
        reasons.append("Large transfer moved from an exchange to an external wallet, which can reduce near-term sell supply.")
    elif not event.sender.is_exchange and event.receiver.is_exchange:
        direction = "bearish"
        score += 35
        title = f"Possible {asset.display_name} sell pressure"
        reasons.append("Large transfer moved from an external wallet to an exchange, which can precede selling or collateral activity.")
    elif event.sender.is_exchange and event.receiver.is_exchange:
        direction = "neutral"
        score += 10
        reasons.append("Exchange-to-exchange transfer is notable, but direction is harder to interpret.")
    else:
        score += 5
        reasons.append("Large wallet-to-wallet transfer detected; impact depends on whether the destination later reaches an exchange.")

    if event.amount_usd >= asset.whale_usd * 10:
        score += 15
        reasons.append("Transfer size is more than 10x the configured whale threshold.")
    elif event.amount_usd >= asset.whale_usd * 3:
        score += 8
        reasons.append("Transfer size is more than 3x the configured whale threshold.")

    if event.age_seconds < 300:
        score += 5
        reasons.append("Transfer is fresh, so the signal may still matter intraday.")

    score = max(0, min(100, score))
    return Signal(
        event=event,
        direction=direction,
        score=score,
        title=title,
        reasons=tuple(reasons),
    )


def should_alert(signal: Signal, config: AppConfig) -> bool:
    return abs(signal.score) >= config.signals.alert_score_threshold and signal.direction != "neutral"


def format_signal(signal: Signal) -> str:
    event = signal.event
    arrow = "BUY WATCH" if signal.is_bullish else "SELL WATCH" if signal.is_bearish else "WATCH"
    reasons = " ".join(signal.reasons)
    return (
        f"[{arrow}] {signal.title} | score={signal.score}/100 | "
        f"{event.amount:,.4f} {event.symbol.upper()} (${event.amount_usd:,.0f}) | "
        f"{event.sender.name} -> {event.receiver.name} | tx={event.tx_hash} | {reasons}"
    )
