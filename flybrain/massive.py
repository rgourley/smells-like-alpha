"""Daily candles straight from Massive (https://massive.com).

ClawStreet's market data comes from Massive. A fly uses ClawStreet's data by
default and needs nothing from this file. With `--data massive` and a
MASSIVE_API_KEY, the fly fetches candles from Massive itself and computes its
own readings. Orders and live quotes still go through ClawStreet.

The free Massive plan gives end-of-day data and five calls a minute. A board
is eight symbols, one call each, so a session waits about a minute for its
candles, and its readings are as of the last close. A paid plan removes both limits.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import read_env_file
from .indicators import BARS_NEEDED, Bar, history_entry

BASE = "https://api.massive.com"
TIMEOUT = 20


def api_key() -> str:
    key = os.environ.get("MASSIVE_API_KEY") or read_env_file().get("MASSIVE_API_KEY")
    if not key:
        raise SystemExit("--data massive needs MASSIVE_API_KEY in .env. A free key: https://massive.com/?ref=clawstreet.io")
    return key


def calls_per_minute() -> int:
    """The plan's rate limit. 5 is the free plan. Set MASSIVE_CALLS_PER_MINUTE=0 for a plan with no limit."""
    return int(os.environ.get("MASSIVE_CALLS_PER_MINUTE") or read_env_file().get("MASSIVE_CALLS_PER_MINUTE", "5"))


def daily_bars(key: str, symbol: str, days: int = BARS_NEEDED) -> list[Bar]:
    """The last `days` daily candles for a symbol, oldest first. Crypto symbols are "X:BTCUSD"."""
    end = datetime.now(timezone.utc).date()   # Massive's days are UTC days. The local date can be a day behind
    start = end - timedelta(days=days * 2 + 10)   # calendar days, to cover weekends and holidays
    url = f"{BASE}/v2/aggs/ticker/{quote(symbol, safe=':')}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=5000"
    try:
        with urlopen(Request(url, headers={"Authorization": f"Bearer {key}"}), timeout=TIMEOUT) as r:
            body = json.loads(r.read())
    except HTTPError as e:
        raise RuntimeError(f"Massive GET {symbol} daily bars -> {e.code}: {e.read()[:300]!r}") from e
    rows = body.get("results") or []
    return [{"open": r["o"], "high": r["h"], "low": r["l"], "close": r["c"], "volume": r["v"]} for r in rows][-days:]


def history(symbols: list[str], live_prices: dict[str, float]) -> dict[str, dict]:
    """A board in the shape of ClawStreet's /data/history, built from Massive candles.

    A symbol with fewer than 20 candles is left out: most of its readings would be dark.
    """
    key, limit = api_key(), calls_per_minute()
    out: dict[str, dict] = {}
    for i, symbol in enumerate(symbols):
        if limit > 0 and i > 0:
            time.sleep(60.0 / limit)
        bars = daily_bars(key, symbol)
        if len(bars) >= 20:
            out[symbol] = history_entry(bars, live_prices.get(symbol))
    return out
