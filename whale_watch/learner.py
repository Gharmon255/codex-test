from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .prices import CoinGeckoPriceFetcher, PriceError
from .store import SignalStore


@dataclass(frozen=True)
class ReviewResult:
    symbol: str
    direction: str
    move_percent: float
    outcome: str


def review_due_signals(config: AppConfig, store: SignalStore, price_fetcher: CoinGeckoPriceFetcher) -> list[ReviewResult]:
    results: list[ReviewResult] = []
    for signal in store.due_signals(config.learning.follow_up_minutes):
        if signal.entry_price_usd is None:
            continue
        current_price = price_fetcher.current_usd(signal.symbol)
        move_percent = ((current_price - signal.entry_price_usd) / signal.entry_price_usd) * 100
        outcome = _outcome(signal.direction, move_percent, config.learning.min_move_percent)
        store.mark_reviewed(signal.id, current_price, outcome, move_percent)
        results.append(ReviewResult(signal.symbol, signal.direction, move_percent, outcome))
    return results


def tune_thresholds(config: AppConfig, store: SignalStore) -> list[str]:
    notes: list[str] = []
    current = store.get_threshold_multipliers()
    step = config.learning.tune_step_percent / 100

    for summary in store.outcome_summary(config.learning.min_samples):
        symbol = summary["symbol"]
        rate = summary["success_rate"]
        multiplier = current.get(symbol, 1.0)
        next_multiplier = multiplier

        if rate < config.learning.low_success_rate:
            next_multiplier = multiplier * (1 + step)
            action = "raising"
        elif rate > config.learning.high_success_rate:
            next_multiplier = multiplier * (1 - step / 2)
            action = "lowering"
        else:
            continue

        if config.learning.auto_tune:
            store.set_threshold_multiplier(symbol, next_multiplier)
            notes.append(
                f"{symbol}: {action} whale threshold multiplier from {multiplier:.2f} to {next_multiplier:.2f} "
                f"after {summary['samples']} reviewed {summary['direction']} signals "
                f"({rate:.0%} success rate)."
            )
        else:
            notes.append(
                f"{symbol}: consider {action} whale threshold multiplier from {multiplier:.2f} to {next_multiplier:.2f}; "
                f"{summary['samples']} reviewed {summary['direction']} signals had {rate:.0%} success rate."
            )

    return notes


def safe_review_due_signals(config: AppConfig, store: SignalStore) -> list[str]:
    try:
        results = review_due_signals(config, store, CoinGeckoPriceFetcher())
    except PriceError as exc:
        return [f"learning review skipped: {exc}"]

    messages = [
        f"reviewed {result.symbol} {result.direction}: {result.move_percent:+.2f}% -> {result.outcome}"
        for result in results
    ]
    messages.extend(tune_thresholds(config, store))
    return messages


def _outcome(direction: str, move_percent: float, min_move_percent: float) -> str:
    if direction == "bullish" and move_percent >= min_move_percent:
        return "success"
    if direction == "bearish" and move_percent <= -min_move_percent:
        return "success"
    if abs(move_percent) < min_move_percent:
        return "neutral"
    return "miss"
