from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PriceError(RuntimeError):
    """Raised when price data cannot be fetched."""


COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "TRX": "tron",
}


class CoinGeckoPriceFetcher:
    base_url = "https://api.coingecko.com/api/v3/simple/price"

    def current_usd(self, symbol: str) -> float:
        coin_id = COINGECKO_IDS.get(symbol.upper())
        if coin_id is None:
            raise PriceError(f"No CoinGecko id configured for {symbol}")

        params = urlencode({"ids": coin_id, "vs_currencies": "usd"})
        payload = _get_json(f"{self.base_url}?{params}")
        try:
            return float(payload[coin_id]["usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceError(f"Price response did not include USD price for {symbol}") from exc


class EventValuePriceFetcher:
    """Offline price source for dry runs: amount_usd divided by amount."""

    def current_usd_from_event(self, amount_usd: float, amount: float) -> float | None:
        if amount <= 0:
            return None
        return amount_usd / amount


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "whale-watch/0.1"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise PriceError(f"HTTP {exc.code} from price provider") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PriceError(f"Could not fetch price data: {exc}") from exc
