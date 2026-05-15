from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class WalletLabel:
    address: str
    owner: str | None = None
    owner_type: str | None = None

    @property
    def is_exchange(self) -> bool:
        return (self.owner_type or "").lower() == "exchange"

    @property
    def name(self) -> str:
        return self.owner or self.address[:12]


@dataclass(frozen=True)
class WhaleEvent:
    tx_hash: str
    blockchain: str
    symbol: str
    amount: float
    amount_usd: float
    timestamp: datetime
    sender: WalletLabel
    receiver: WalletLabel
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return max(0.0, (datetime.now(timezone.utc) - self.timestamp).total_seconds())


@dataclass(frozen=True)
class Signal:
    event: WhaleEvent
    direction: str
    score: int
    title: str
    reasons: tuple[str, ...]

    @property
    def is_bullish(self) -> bool:
        return self.direction == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.direction == "bearish"
