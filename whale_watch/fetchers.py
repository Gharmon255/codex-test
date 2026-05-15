from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AppConfig
from .models import WalletLabel, WhaleEvent


class FetchError(RuntimeError):
    """Raised when a whale data provider cannot be reached or parsed."""


class WhaleAlertFetcher:
    base_url = "https://api.whale-alert.io/v1/transactions"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, start: datetime | None = None) -> list[WhaleEvent]:
        if not self.config.whale_alert.api_key:
            raise FetchError("Missing Whale Alert API key. Set WHALE_ALERT_API_KEY or config whale_alert.api_key.")

        since = start or datetime.now(timezone.utc) - timedelta(minutes=self.config.bot.lookback_minutes)
        params = {
            "api_key": self.config.whale_alert.api_key,
            "min_value": int(self.config.whale_alert.min_usd_value),
            "start": int(since.timestamp()),
        }
        payload = _get_json(f"{self.base_url}?{urlencode(params)}")
        if payload.get("result") != "success":
            raise FetchError(f"Whale Alert returned: {payload.get('message', payload)}")

        symbols = {asset.symbol for asset in self.config.assets.values()}
        return [
            event
            for tx in payload.get("transactions", [])
            if (event := _parse_whale_alert_transaction(tx)) is not None
            and event.symbol.lower() in symbols
        ]


class MockFetcher:
    """Deterministic demo events for dry runs and local testing."""

    def fetch(self, start: datetime | None = None) -> list[WhaleEvent]:
        now = datetime.now(timezone.utc)
        return [
            WhaleEvent(
                tx_hash="mock-btc-outflow",
                blockchain="bitcoin",
                symbol="btc",
                amount=1250,
                amount_usd=82_500_000,
                timestamp=now,
                sender=WalletLabel("bc1qexchange", "Binance", "exchange"),
                receiver=WalletLabel("bc1qcoldwallet", "Unknown wallet", "unknown"),
            ),
            WhaleEvent(
                tx_hash="mock-eth-inflow",
                blockchain="ethereum",
                symbol="eth",
                amount=38_000,
                amount_usd=118_000_000,
                timestamp=now,
                sender=WalletLabel("0xwhale", "Unknown whale", "unknown"),
                receiver=WalletLabel("0xcoinbase", "Coinbase", "exchange"),
            ),
            WhaleEvent(
                tx_hash="mock-trx-transfer",
                blockchain="tron",
                symbol="trx",
                amount=350_000_000,
                amount_usd=42_000_000,
                timestamp=now,
                sender=WalletLabel("TWhale", "Unknown whale", "unknown"),
                receiver=WalletLabel("TExchange", "OKX", "exchange"),
            ),
        ]


def dedupe_events(events: Iterable[WhaleEvent], seen_hashes: set[str]) -> list[WhaleEvent]:
    fresh: list[WhaleEvent] = []
    for event in events:
        if event.tx_hash in seen_hashes:
            continue
        seen_hashes.add(event.tx_hash)
        fresh.append(event)
    return fresh


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "whale-watch/0.1"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} from data provider") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"Could not fetch provider data: {exc}") from exc


def _parse_whale_alert_transaction(tx: dict) -> WhaleEvent | None:
    symbol = str(tx.get("symbol", "")).lower()
    if not symbol:
        return None

    sender = tx.get("from", {}) or {}
    receiver = tx.get("to", {}) or {}
    timestamp = datetime.fromtimestamp(int(tx.get("timestamp", 0)), tz=timezone.utc)

    return WhaleEvent(
        tx_hash=str(tx.get("hash", "")),
        blockchain=str(tx.get("blockchain", "")),
        symbol=symbol,
        amount=float(tx.get("amount", 0.0)),
        amount_usd=float(tx.get("amount_usd", 0.0)),
        timestamp=timestamp,
        sender=WalletLabel(
            address=str(sender.get("address", "")),
            owner=sender.get("owner"),
            owner_type=sender.get("owner_type"),
        ),
        receiver=WalletLabel(
            address=str(receiver.get("address", "")),
            owner=receiver.get("owner"),
            owner_type=receiver.get("owner_type"),
        ),
        raw=tx,
    )
