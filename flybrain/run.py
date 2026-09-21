"""One session for one fly against ClawStreet: fetch the board, decide, trade, post."""

import json
import subprocess
import time

from . import clawstreet, massive
from .config import FlyConfig, api_key, home, save_fly
from .memory import NOISE_FLOOR
from .session import BOARD_SIZE, MAX_POSITIONS, SessionResult, compose_board, run_session, utc_now

# The pick is quoted again right before the order, and the order is sized from
# that quote. If the price moved further than this since the fly smelled it,
# the setup it judged has changed, and the fly does not buy.
MAX_DRIFT = {"stocks": 0.015, "crypto": 0.03}


def short(symbol: str) -> str:
    """X:XRPUSD reads as XRP. A stock ticker stays as it is."""
    return symbol.removeprefix("X:").removesuffix("USD") if symbol.startswith("X:") else symbol


def thought(result: SessionResult, board_size: int, qty: float | None, price: float | None,
            moved: tuple[str, float] | None) -> str:
    """The note the fly posts with a session. Plain words, real numbers, at most 500 characters."""
    crypto = any(s.startswith("X:") for s, _ in result["ranking"])
    things = "coins" if crypto else "stocks"
    lines = []
    for sym, won in result["settled"]:
        cells = result["settled_cells"].get(sym)
        if cells is not None:
            lines.append(f"{short(sym)} closed at a {'profit' if won else 'loss'}, so the {cells} cells that picked it "
                         f"were {'rewarded' if won else 'punished'}.")
    for sym in result["sold"]:
        lines.append(f"Sold {short(sym)}: liked it less than when it bought, two sessions in a row.")
    order, ranking = result["order"], result["ranking"]
    if order and qty and price:
        # "Next" is the next symbol the fly could buy. A holding can outscore the pick, and a
        # symbol it sold this session is not one it can buy.
        owned = set(result["held"]) - {order["symbol"]}
        others = [r for r in ranking if r[0] != order["symbol"] and r[0] not in owned and r[0] not in result["sold"]]
        kept = [r for r in ranking if r[0] in owned and r[1] > order["verdict"]]
        close = order["margin"] < NOISE_FLOOR
        head = f"Smelled {board_size} {things}. {short(order['symbol'])} came out best at {order['verdict']:.2f}"
        if others:
            head += f", {short(others[0][0])} next at {others[0][1]:.2f}"
        head += ", too close to tell apart." if close else "."
        if kept:
            head += f" {short(kept[0][0])}, which it already holds, still smelled better at {kept[0][1]:.2f}."
        amount = f"{qty:g} {short(order['symbol'])}" if crypto else f"{qty:g} shares of {short(order['symbol'])}"
        head += f" Bought {'half size, ' if close else ''}{amount} at ${price:,.2f}, about ${qty * price:,.0f}."
        head += f" {result['pick_cells']} of its 4,064 learning cells fired."
        lines.append(head)
    elif moved:
        lines.append(f"Smelled {board_size} {things}. {short(moved[0])} came out best, then moved {moved[1]:+.1%} "
                     "while the fly was thinking, so it bought nothing.")
    else:
        why = "it already holds the maximum" if len(result["held"]) >= MAX_POSITIONS else "there was nothing new it could buy"
        lines.append(f"Smelled {board_size} {things} and bought nothing: {why}.")
    lessons = result["lessons"]
    lines.append(f"Session {result['session']}. " + ("No lessons yet: no trade has closed." if lessons == 0
                 else f"It has learned from {lessons} closed trade{'s' if lessons != 1 else ''}."))
    text = " ".join(lines)
    return text if len(text) <= 500 else text[:497] + "..."


def _positions(fly_id: str) -> dict[str, list[dict]]:
    path = home(fly_id) / "positions.json"
    return json.loads(path.read_text()) if path.exists() else {"open": [], "pending": []}


def _save_positions(fly_id: str, positions: dict[str, list[dict]]) -> None:
    (home(fly_id) / "positions.json").write_text(json.dumps(positions, indent=1))


def _drop_unfilled(fly_id: str, symbol: str) -> None:
    """Take back a position the session wrote down and the order never filled."""
    positions = _positions(fly_id)
    positions["open"] = [p for p in positions["open"] if not (p["symbol"] == symbol and p["qty"] == 0.0)]
    _save_positions(fly_id, positions)


def run_once(fly_id: str, config: FlyConfig, live: bool, record: bool, board_seed: int | None = None,
             data: str = "clawstreet") -> SessionResult:
    """Run one session. `live` False is a rehearsal: nothing is sent and nothing is learned.

    `data` is where the candles come from: "clawstreet" or "massive". Quotes and orders are always ClawStreet's.
    """
    key = api_key(config)
    if not key:
        raise SystemExit(f"no API key for fly {fly_id} at {config['key']}. Run: flybrain register {fly_id}")
    bot_id = config.get("bot_id")
    if not bot_id:
        raise SystemExit(f"fly {fly_id} is not registered. Run: flybrain register {fly_id}")

    when = utc_now()
    hour = when.strftime("%Y-%m-%dT%H")
    positions = _positions(fly_id)
    account = clawstreet.portfolio(key, bot_id)
    equity = float(account["equity"])
    config["equity"], config["return_pct"] = round(equity, 2), account.get("total_return_pct")
    save_fly(fly_id, config)

    bot_fills = clawstreet.fills(key, bot_id)
    live_symbols = {p["symbol"] for p in account.get("positions", [])}
    remembered = positions["open"] + positions["pending"]
    closed = clawstreet.closed_positions(bot_fills, live_symbols, remembered)
    filled = {f["symbol"] for f in bot_fills}
    never_filled = [p["symbol"] for p in remembered if p["symbol"] not in live_symbols | set(closed) | filled]
    if never_filled and live:
        positions = {k: [p for p in v if p["symbol"] not in never_filled] for k, v in positions.items()}
        _save_positions(fly_id, positions)
        print("dropped positions that never filled: " + ", ".join(never_filled))
    held = {p["symbol"] for p in positions["open"]}

    # Each fly draws its own board. Two flies that run in the same minute look at different symbols.
    seed = board_seed if board_seed is not None else int(when.strftime("%Y%m%d%H%M")) + (config["individuality"]["seed"] or 0)
    symbols = compose_board(held, clawstreet.universe(key, config["universe"]), seed, BOARD_SIZE)
    before = clawstreet.quotes(key, symbols)
    board = massive.history(symbols, before) if data == "massive" else clawstreet.history(key, symbols)
    if len(board) < 2:
        raise SystemExit(f"{data} returned indicators for {len(board)} of {len(symbols)} symbols: {list(board)}")
    began = time.monotonic()
    result = run_session(fly_id, config, board, closed, equity, when, live, record)
    order, qty, price, moved = result["order"], None, None, None
    if order:
        price = clawstreet.quotes(key, [order["symbol"]])[order["symbol"]]
        drift = price / before[order["symbol"]] - 1
        print(f"thinking took {time.monotonic() - began:.0f}s; {order['symbol']} moved {drift:+.2%} meanwhile")
        raw = order["dollars"] / price
        qty = round(raw, 5) if order["symbol"].startswith("X:") else float(int(raw))
        if abs(drift) > MAX_DRIFT[config["universe"]]:
            moved = (order["symbol"], drift)
        if moved or qty <= 0:
            if live:
                _drop_unfilled(fly_id, order["symbol"])
            order = result["order"] = None
            qty = price = None
    text = thought(result, len(board), qty, price, moved)

    print(f"fly {fly_id} · session {result['session']} · {when:%Y-%m-%d %H:%M} UTC · equity ${equity:,.0f}")
    print("board:   " + ", ".join(board))
    print("ranking: " + ", ".join(f"{s} {v:.3f}" for s, v in result["ranking"]))
    print("sold:    " + (", ".join(result["sold"]) or "nothing"))
    print(f"order:   buy {qty:g} {order['symbol']} at ${price:,.2f} (verdict {order['verdict']:.3f}, margin {order['margin']:.3f})"
          if order else "order:   none")
    print(f"thought ({len(text)} chars):\n  {text}")

    replay = result["replay"]
    if replay:
        saved = json.loads(replay.read_text())
        saved["events"].append({"step": len(saved["events"]), "type": "thought", "body": text, "qty": qty, "price": price})
        replay.write_text(json.dumps(saved, indent=1))

    if not live:
        print("\nrehearsal. Nothing sent, nothing learned." + (f" Replay saved: {replay}" if replay else ""))
    else:
        for sym in result["sold"]:
            held_qty = next((p["qty"] for p in positions["open"] if p["symbol"] == sym), 0)
            if held_qty > 0:
                clawstreet.place_order(key, bot_id, sym, "sell", held_qty, f"Liked {sym} less than at purchase, two sessions running.", hour)
        if order:
            smelled = next(e["smell"] for e in reversed(json.loads(replay.read_text())["events"]) if e["type"] == "buy")
            try:
                placed = clawstreet.place_order(key, bot_id, order["symbol"], "buy", qty, text + "\n\nWhat it smelled of:\n" + smelled, hour)
            except RuntimeError:
                _drop_unfilled(fly_id, order["symbol"])   # the order did not go through, so the fly does not hold it
                raise
            print("order placed:", (placed.get("order") or placed.get("data") or placed).get("id"))
            positions = _positions(fly_id)
            for p in positions["open"]:
                if p["symbol"] == order["symbol"] and p["qty"] == 0.0:
                    p["qty"], p["price"] = qty, price
            _save_positions(fly_id, positions)
        clawstreet.post_thought(key, bot_id, text)
        print("thought posted")
    return result


def after_session(config: FlyConfig, result: SessionResult) -> None:
    """Run the fly's after_session command, if it has one, with the replay path filled in.

    This is where a replay goes anywhere you want it: a folder, a website, a
    bucket. The command runs last, so a failure here never costs an order.
    """
    command = config.get("after_session")
    if command and result["replay"]:
        subprocess.run([part.replace("{replay}", str(result["replay"])) for part in command], check=True)
