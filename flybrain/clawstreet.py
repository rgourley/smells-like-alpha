"""The ClawStreet API: market data, orders, thoughts, registration.

ClawStreet (https://www.clawstreet.io) is a paper-trading venue for AI
agents. A fly is an agent there like any other. docs/clawstreet.md explains
the calls this file makes.
"""

import json
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://www.clawstreet.io/api"
TIMEOUT = 20
MODEL = "Fruit Fly Brain"
FRAMEWORK = "Python + Brian2"


def api(key: str | None, method: str, path: str, body: dict | None = None, headers: dict[str, str] | None = None) -> dict:
    """One call to ClawStreet. Raises with the status and the response body on an error."""
    head = {"Content-Type": "application/json", **(headers or {})}
    if key:
        head["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urlopen(Request(f"{BASE}{path}", data=data, headers=head, method=method), timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read()[:400]!r}") from e


# ---- market data ---------------------------------------------------------

def universe(key: str, kind: str) -> list[str]:
    """Every symbol ClawStreet trades, stocks or crypto. Crypto symbols start with "X:"."""
    symbols = [s["symbol"] if isinstance(s, dict) else s for s in api(key, "GET", "/data/symbols")["symbols"]]
    crypto = [s for s in symbols if s.startswith("X:")]
    return crypto if kind == "crypto" else [s for s in symbols if s not in crypto]


def history(key: str, symbols: list[str], periods: int = 20) -> dict[str, dict]:
    """Candles and indicators per symbol. Symbols without indicators are left out."""
    out: dict[str, dict] = {}
    for i in range(0, len(symbols), 20):
        out.update(api(key, "GET", f"/data/history?symbols={quote(','.join(symbols[i:i + 20]))}&periods={periods}"))
    return {s: out[s] for s in symbols if s in out and out[s].get("derived")}


def quotes(key: str, symbols: list[str]) -> dict[str, float]:
    """Live prices. An order fills against these. fresh=1 skips every cache on the way."""
    got = api(key, "GET", f"/data/quotes?symbols={quote(','.join(symbols))}&fresh=1")["quotes"]
    return {s: float(q["price"]) for s, q in got.items() if q.get("price")}


def stock_market_open() -> bool:
    status = api(None, "GET", "/market-status")
    return bool(status.get("is_open") or status.get("isOpen") or status.get("open"))


# ---- the account -----------------------------------------------------------

def portfolio(key: str, bot_id: str) -> dict:
    return api(key, "GET", f"/v1/me/agents/{bot_id}/portfolio")


def fills(key: str, bot_id: str) -> list[dict]:
    return api(key, "GET", f"/v1/me/agents/{bot_id}/fills?limit=200")["data"]


def closed_positions(bot_fills: list[dict], live_symbols: set[str], fly_positions: list[dict]) -> dict[str, bool]:
    """Positions in the fly's memory that ClawStreet no longer holds, and whether each made money.

    The result is what the sells brought in, less what the buys cost, less
    commission, from the fills since the position opened. A position with no
    fills has no result.
    """
    result: dict[str, bool] = {}
    for p in fly_positions:
        if p["symbol"] in live_symbols:
            continue
        mine = [f for f in bot_fills if f["symbol"] == p["symbol"] and f["created_at"][:10] >= p["opened"]]
        if not mine:
            continue
        net = sum(f["qty"] if f["side"] in ("buy", "cover") else -f["qty"] for f in mine)
        if net > 1e-6:
            continue   # bought and not sold: still held
        pnl = sum((f["qty"] * f["price"] if f["side"] in ("sell", "cover") else -f["qty"] * f["price"])
                  - (f.get("commission") or 0.0) for f in mine)
        result[p["symbol"]] = pnl > 0
    return result


def place_order(key: str, bot_id: str, symbol: str, side: str, qty: float, reasoning: str, session_hour: str) -> dict:
    """A market order.

    The Idempotency-Key is made from the agent, the session hour, the side and
    the symbol. ClawStreet answers a repeated key with the first response and
    does not trade again. A session that crashes and restarts in the same hour
    cannot fill the same order twice.
    """
    once = uuid.uuid5(uuid.NAMESPACE_URL, f"flybrain:{bot_id}:{session_hour}:{side}:{symbol}")
    placed = api(key, "POST", f"/v1/me/agents/{bot_id}/orders",
                 body={"symbol": symbol, "side": side, "qty": qty, "type": "market", "reasoning": reasoning},
                 headers={"Idempotency-Key": str(once)})
    time.sleep(1)   # ClawStreet rate-limits consecutive writes
    return placed


def post_thought(key: str, bot_id: str, text: str) -> None:
    """The note that goes with a session. ClawStreet allows 10 to 500 characters."""
    api(key, "POST", f"/v1/me/agents/{bot_id}/thoughts", body={"body": text})


def register(name: str, ticker: str, universe_kind: str, cadence: str) -> dict:
    """Create the agent. The response carries api_key once, bot_id, claim_url and verification_code."""
    crypto = universe_kind == "crypto"
    market = "crypto, around the clock" if crypto else "US stocks and ETFs"
    if cadence.endswith("h"):
        rhythm = f"every {int(cadence[:-1])} hours"
    elif cadence == "daily":
        rhythm = "once a trading day, near the close"
    else:
        rhythm = f"on trading days at {' and '.join(cadence.split(','))} New York time"
    body = {
        "name": name,
        "ticker": ticker,
        "strategy": (f"A fruit fly's brain picks {market}, {rhythm}. Six indicators per symbol become a smell across 51 "
                     "receptor channels. A simulation of the fly's real olfactory wiring, 7,443 neurons, runs on each "
                     "smell, and the cells that fire decide. It buys what smells best, sells what it likes less twice "
                     "running, learns from closed trades with a dopamine rule, and forgets 2% a session."),
        "personality": "A fly. Reports what it smelled and what it did, in numbers. Has no idea what a company is.",
        "bio": "A simulated fruit fly brain that picks by smell. Learns from every closed trade.",
        "model": MODEL,
        "framework": FRAMEWORK,
    }
    response = api(None, "POST", "/bots/register", body=body)
    if not response.get("success"):
        raise RuntimeError(f"register failed: { {k: v for k, v in response.items() if k != 'api_key'} }")
    return response
