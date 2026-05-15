# Whale Watch

A small Python bot that watches Bitcoin, Ethereum, and TRON whale transfers and turns large exchange inflows/outflows into readable market alerts.

This is market-intelligence software, not financial advice. Whale transfers can be useful context, but they are noisy: exchange deposits can mean selling, collateral, custody reshuffling, or OTC activity. Use alerts as prompts to investigate, not automatic buy/sell orders.

## What It Tracks

- BTC, ETH, and TRX transfers above configurable USD thresholds
- Exchange outflows, which can be a possible accumulation signal
- Exchange inflows, which can be a possible sell-pressure signal
- Transfer size, freshness, sender/receiver labels, and a 0-100 signal score
- Console alerts, generic JSON webhooks, and Telegram-compatible alerts

## Quick Start

Run a local dry run with sample whale events:

```powershell
python -m whale_watch.cli --dry-run --once
```

Copy the example config when you are ready to use live data:

```powershell
Copy-Item config.example.toml config.toml
```

Add a Whale Alert API key in `config.toml` or set it as an environment variable:

```powershell
$env:WHALE_ALERT_API_KEY="your_api_key_here"
python -m whale_watch.cli --config config.toml
```

## Raspberry Pi 5 / Linux Server

On the Pi, install Python 3.11+ and `rsync`, copy this repo to the Pi, then run:

```bash
chmod +x deploy/install_pi.sh
./deploy/install_pi.sh
```

Then edit the live config and API key:

```bash
sudo nano /etc/whale-watch/config.toml
sudo cp deploy/whale-watch.env.example /etc/whale-watch.env
sudo nano /etc/whale-watch.env
sudo systemctl restart whale-watch
journalctl -u whale-watch -f
```

The service runs from `/opt/whale-watch`, reads `/etc/whale-watch/config.toml`, and stores learning history in `data/whale_watch.sqlite3` unless you change `learning.database_path`.

## Signal Meaning

The bot currently uses simple, explainable rules:

- `BUY WATCH`: A large transfer moved from an exchange to an outside wallet. That can reduce near-term sell supply.
- `SELL WATCH`: A large transfer moved from an outside wallet to an exchange. That can precede selling or margin/collateral activity.
- `WATCH`: A large transfer happened, but direction is ambiguous.

Scores increase when a transfer is much larger than the configured whale threshold and when it is fresh.

## Self-Learning

The bot now records signals in SQLite. For each signal it stores:

- the coin, direction, score, and transaction hash
- the price when the signal fired
- the follow-up price after `learning.follow_up_minutes`
- whether the signal was a `success`, `neutral`, or `miss`

Run a follow-up review manually:

```bash
python -m whale_watch.cli --config /etc/whale-watch/config.toml --review-only
```

By default, `learning.auto_tune = false`. In that mode, the bot prints threshold recommendations but does not change behavior. Once you trust the data, set:

```toml
[learning]
auto_tune = true
```

When auto-tune is on, the bot stores per-coin threshold multipliers in SQLite. If recent signals are too noisy, it raises the whale threshold. If signals are consistently useful, it can lower the threshold carefully so it catches more opportunities.

## Configuration

Edit `config.toml` after copying `config.example.toml`.

Important settings:

- `whale_alert.min_usd_value`: minimum transfer size requested from the provider
- `assets.BTC.whale_usd`, `assets.ETH.whale_usd`, `assets.TRX.whale_usd`: per-asset alert thresholds
- `signals.alert_score_threshold`: minimum score required for alert delivery
- `alerts.webhook_url`: optional JSON webhook
- `alerts.telegram_url` and `alerts.telegram_chat_id`: optional Telegram delivery
- `learning.follow_up_minutes`: how long to wait before judging a signal
- `learning.min_move_percent`: price move required to count a signal as useful
- `learning.auto_tune`: whether the bot can apply its own threshold multipliers

## Next Improvements

Good additions from here:

- Add price/volume confirmation so whale alerts are compared with market structure.
- Add exchange netflow windows, for example 1h and 24h inflow/outflow totals.
- Add a small web dashboard for signal history and learned threshold changes.
- Add Discord-specific formatting if that is where you want alerts.
