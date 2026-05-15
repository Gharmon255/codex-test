from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

from .alerts import AlertError, AlertManager
from .config import apply_threshold_multipliers, load_config
from .fetchers import FetchError, MockFetcher, WhaleAlertFetcher, dedupe_events
from .learner import safe_review_due_signals
from .prices import CoinGeckoPriceFetcher, EventValuePriceFetcher, PriceError
from .signals import format_signal, score_event, should_alert
from .store import SignalStore


def _entry_price(event, price_fetcher: CoinGeckoPriceFetcher | None, dry_price_fetcher: EventValuePriceFetcher) -> float | None:
    if price_fetcher is None:
        return dry_price_fetcher.current_usd_from_event(event.amount_usd, event.amount)
    try:
        return price_fetcher.current_usd(event.symbol)
    except PriceError as exc:
        print(f"price error: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track BTC, ETH, and TRX whale transfers.")
    parser.add_argument("--config", default="config.example.toml", help="Path to TOML config file.")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic mock events.")
    parser.add_argument("--review-only", action="store_true", help="Review old signals, tune thresholds, and exit.")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    store = SignalStore(config.learning.database_path) if config.learning.enabled else None
    if store is not None:
        config = apply_threshold_multipliers(config, store.get_threshold_multipliers())

    if args.review_only:
        if store is None:
            print("learning is disabled")
            return 0
        for message in safe_review_due_signals(config, store):
            print(message)
        return 0

    fetcher = MockFetcher() if args.dry_run or config.bot.dry_run else WhaleAlertFetcher(config)
    price_fetcher = None if args.dry_run or config.bot.dry_run else CoinGeckoPriceFetcher()
    dry_price_fetcher = EventValuePriceFetcher()
    alerts = AlertManager(config.alerts)
    seen_hashes: set[str] = set()

    while True:
        if store is not None:
            for message in safe_review_due_signals(config, store):
                print(message)

        start = datetime.now(timezone.utc) - timedelta(minutes=config.bot.lookback_minutes)
        try:
            events = dedupe_events(fetcher.fetch(start), seen_hashes)
        except FetchError as exc:
            print(f"fetch error: {exc}", file=sys.stderr)
            if args.once:
                return 2
            time.sleep(config.bot.poll_seconds)
            continue

        for event in events:
            signal = score_event(event, config)
            if signal is None:
                continue
            if store is not None:
                store.record_signal(signal, _entry_price(event, price_fetcher, dry_price_fetcher))
            if should_alert(signal, config):
                try:
                    alerts.send(signal)
                except AlertError as exc:
                    print(f"alert error: {exc}", file=sys.stderr)
            elif config.alerts.console:
                print(format_signal(signal))

        if args.once:
            return 0
        time.sleep(config.bot.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
