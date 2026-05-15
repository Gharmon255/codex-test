from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AlertConfig
from .models import Signal
from .signals import format_signal


class AlertError(RuntimeError):
    """Raised when an alert destination fails."""


class AlertManager:
    def __init__(self, config: AlertConfig) -> None:
        self.config = config

    def send(self, signal: Signal) -> None:
        message = format_signal(signal)
        if self.config.console:
            print(message)
        if self.config.webhook_url:
            _post_json(self.config.webhook_url, {"text": message, "signal": _signal_payload(signal)})
        if self.config.telegram_url and self.config.telegram_chat_id:
            payload = urlencode({"chat_id": self.config.telegram_chat_id, "text": message}).encode("utf-8")
            _post_bytes(self.config.telegram_url, payload, "application/x-www-form-urlencoded")


def _post_json(url: str, payload: dict) -> None:
    _post_bytes(url, json.dumps(payload).encode("utf-8"), "application/json")


def _post_bytes(url: str, payload: bytes, content_type: str) -> None:
    request = Request(url, data=payload, headers={"Content-Type": content_type, "User-Agent": "whale-watch/0.1"})
    try:
        with urlopen(request, timeout=20):
            return
    except HTTPError as exc:
        raise AlertError(f"Alert destination returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise AlertError(f"Could not send alert: {exc}") from exc


def _signal_payload(signal: Signal) -> dict:
    event = signal.event
    return {
        "direction": signal.direction,
        "score": signal.score,
        "title": signal.title,
        "symbol": event.symbol.upper(),
        "amount": event.amount,
        "amount_usd": event.amount_usd,
        "tx_hash": event.tx_hash,
        "from": event.sender.name,
        "to": event.receiver.name,
        "reasons": list(signal.reasons),
    }
