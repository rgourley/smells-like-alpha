"""One trading session, recorded so it can be played back.

The steps, in order:

  settle      give each closed trade's result to the Kenyon cells that fired
              when the fly chose it
  forget      move every synapse a little back toward the connectome
  smell       run every symbol on the board through the circuit, five times each
  reconsider  smell each holding again; two sessions in a row with a verdict
              below the purchase verdict, and the fly sells it
  buy         the best symbol the fly does not hold, sized by the verdict
  remember    write the synapses, the positions and the replay to disk

Every step writes an event to the replay. docs/replay-format.md lists them.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import numpy as np

from .brain import Brain
from .config import FlyConfig, home
from .memory import FlyMemory, OpenPosition, from_connectome
from .settings import Settings, settings_for
from .smell import channel_map, describe, individual_gains, smell, to_rates

PRESENTATION_MS = 50.0
# The receptor spikes are random, so one presentation is a noisy reading. The
# fly smells each symbol several times. The verdict is the mean. The cells it
# remembers are the ones that fired in most of the presentations.
#
# Spikes are not dollars. A position is a share of the account, set by the
# verdict against full_verdict. The untrained fly's strongest verdicts, for an
# overbought breakout, are between 5 and 6.5. flybrain/settings.py has every
# number a fly can set.

Reading = dict[str, float | str | None]


class Order(TypedDict):
    symbol: str
    dollars: float
    verdict: float
    margin: float


class SessionResult(TypedDict):
    session: int
    lessons: int
    settled: list[tuple[str, bool]]
    settled_cells: dict[str, int]
    ranking: list[tuple[str, float]]
    sold: list[str]
    order: Order | None
    held: list[str]
    pick_cells: int
    replay: Path | None
    # Why the session placed no order: "full", "no_cash" or "nothing_new". None when it placed one.
    no_order: str | None
    max_positions: int
    noise_floor: float


@dataclass(frozen=True)
class Candidate:
    """One symbol on the board, as the fly saw it."""

    symbol: str
    activations: dict[str, float]
    cells: np.ndarray     # boolean per Kenyon cell: fired in most of the presentations
    verdict: float        # mean verdict over the presentations


def reading_from_history(entry: dict) -> Reading:
    """The six readings, from one symbol's entry in ClawStreet's /data/history response."""
    derived = entry.get("derived") or {}
    rsi = entry.get("rsi") or []
    return {
        "rsi": rsi[-1] if rsi else None,
        "bb_position": derived.get("bb_position"),
        "distance_from_sma50": derived.get("distance_from_sma50"),
        "volume_ratio": derived.get("volume_ratio"),
        "price_change_5d": derived.get("price_change_5d"),
        "rsi_trend": derived.get("rsi_trend"),
    }


def bars_from_history(entry: dict, n: int = 20) -> list[list[float]]:
    """The last n candles as [open, high, low, close], for the viewer's chart cards."""
    o, h, l, c = (entry.get(k) or [] for k in ("open", "high", "low", "prices"))
    return [[float(a), float(b), float(d), float(e)] for a, b, d, e in list(zip(o, h, l, c))[-n:]]


def compose_board(held: set[str], universe: list[str], seed: int, size: int) -> list[str]:
    """Holdings keep their places. The other places go to symbols drawn from the universe.

    A holding must be on the board so the fly smells it again and can sell
    it. max_positions is below the board size, so new symbols arrive every session.
    """
    rng = np.random.default_rng(seed)
    fresh = [s for s in universe if s not in held]
    picks = rng.choice(fresh, size=max(0, size - len(held)), replace=False)
    return sorted(held) + [str(s) for s in picks]


def size_order(verdict: float, runner_up: float, account: float, cash: float, settings: Settings) -> float:
    """Dollars to spend, from the verdict.

    The verdict against full_verdict sets the share of the account, up to
    max_fraction. When the margin over the next symbol is below noise_floor,
    the fly could not tell them apart, and the amount is halved. The fly never
    borrows: the amount is capped at the cash in the account.
    """
    dollars = account * settings["max_fraction"] * min(1.0, max(verdict, 0.0) / settings["full_verdict"])
    if verdict - runner_up < settings["noise_floor"]:
        dollars /= 2
    return float(round(min(dollars, max(cash, 0.0)), 2))


def write_replay(fly_id: str, when: datetime, dry: bool, events: list[dict]) -> Path:
    """Save a replay under flies/<id>/replays/ and list it in index.json, oldest first."""
    folder = home(fly_id) / "replays"
    folder.mkdir(parents=True, exist_ok=True)
    name = when.strftime("%Y-%m-%dT%H%M") + (".dry" if dry else "") + ".json"
    (folder / name).write_text(json.dumps({"fly": fly_id, "when": when.isoformat(timespec="seconds"),
                                           "dry": dry, "events": events}, indent=1))
    index = folder / "index.json"
    listed: list[str] = json.loads(index.read_text()) if index.exists() else []
    if not dry:
        # A real session replaces the rehearsals before it.
        for old in [n for n in listed if n.endswith(".dry.json")]:
            (folder / old).unlink(missing_ok=True)
        listed = [n for n in listed if not n.endswith(".dry.json")]
    if name not in listed:
        listed.append(name)
    index.write_text(json.dumps(listed))
    return folder / name


def run_session(fly_id: str, config: FlyConfig, board: dict[str, dict], closed: dict[str, bool],
                account: float, cash: float, when: datetime, live: bool, record: bool) -> SessionResult:
    """One decision. `closed` maps a symbol to whether its trade made money.

    `account` is the equity a position is sized against. `cash` is what is free to spend.

    `live` False is a rehearsal: the fly decides and nothing changes on disk,
    except the replay when `record` is True.
    """
    events: list[dict] = []
    add = lambda kind, **fields: events.append({"step": len(events), "type": kind, **fields})

    settings = settings_for(config)
    brain = Brain()
    memory = from_connectome(brain.circuit, home(fly_id), settings["learning_rate"], settings["recovery"], settings["noise_floor"])
    memory.load()
    add("start", session=memory.sessions + 1, held=sorted(memory.held()), drift=round(memory.drift(), 5),
        universe=config["universe"], cadence=config["cadence"])
    add("board", stocks={sym: {"reading": reading_from_history(e), "price": e.get("current_price"),
                               "bars": bars_from_history(e)} for sym, e in board.items()})

    settled_cells: dict[str, int] = {}
    for symbol, profitable in closed.items():
        position = memory.close(symbol, profitable)
        if position:
            settled_cells[symbol] = len(position.cells)
            add("settle", symbol=symbol, profitable=profitable, cells=len(position.cells),
                opened=position.opened, compartment="reward" if profitable else "punishment")

    memory.forget()
    add("forget", drift=round(memory.drift(), 5))

    channels = channel_map(brain.circuit)
    gains = individual_gains(config["individuality"]["seed"], config["individuality"]["sigma"])
    seed = int(when.strftime("%y%m%d%H%M")) % (2**32 - 1000)   # the session minute, as a 32-bit seed
    looks = settings["presentations"]
    held = memory.held()
    candidates: list[Candidate] = []
    for i, (symbol, entry) in enumerate(board.items()):
        activations = smell(reading_from_history(entry))
        rates = to_rates(activations, channels, gains)
        fired = np.array([brain.present(rates, PRESENTATION_MS, seed + i * looks + k)[brain.kc] > 0 for k in range(looks)])
        verdict = float(np.mean([memory.verdict(f) for f in fired]))
        cells = fired.sum(axis=0) > looks / 2
        c = Candidate(symbol, activations, cells, verdict)
        candidates.append(c)
        add("sniff", symbol=symbol, held=symbol in held, channels={k: round(v, 3) for k, v in activations.items()},
            cells=[int(x) for x in np.flatnonzero(cells)], verdict=round(c.verdict, 3))

    sold: list[str] = []
    for c in candidates:
        if c.symbol not in held:
            continue
        then = next(p.verdict for p in memory.positions if p.symbol == c.symbol)
        should_sell = memory.reconsider(c.symbol, c.verdict)
        cooling = next(p.cooling for p in memory.positions if p.symbol == c.symbol)
        add("reconsider", symbol=c.symbol, verdict_then=round(then, 3), verdict_now=round(c.verdict, 3), cooling=cooling)
        if should_sell:
            memory.sell(c.symbol)
            sold.append(c.symbol)
            add("sell", symbol=c.symbol, reason="liked it less than at purchase, two sessions running")

    candidates.sort(key=lambda c: c.verdict, reverse=True)
    add("rank", order=[(c.symbol, round(c.verdict, 3)) for c in candidates])

    # The margin is against the next symbol the fly can buy. A holding can outscore the pick.
    taken = memory.held() | {p.symbol for p in memory.pending}
    eligible = [c for c in candidates if c.symbol not in taken]
    pick = eligible[0] if eligible else None
    runner_up = eligible[1].verdict if len(eligible) > 1 else 0.0

    order: Order | None = None
    no_order: str | None = "nothing_new" if not pick else "full" if len(memory.held()) >= settings["max_positions"] else None
    if pick and no_order is None:
        dollars = size_order(pick.verdict, runner_up, account, cash, settings)
        # An order under 1% of the account is not worth its commission.
        no_order = "no_cash" if dollars < account * 0.01 else None
        if no_order is None:
            order = {"symbol": pick.symbol, "dollars": dollars, "verdict": round(pick.verdict, 3),
                     "margin": round(pick.verdict - runner_up, 3)}
            add("buy", **order, smell=describe(pick.activations))
            if live:
                memory.open(OpenPosition(
                    symbol=pick.symbol, opened=when.date().isoformat(), qty=0.0,
                    price=float(board[pick.symbol].get("current_price") or 0.0),
                    cells=[int(i) for i in np.flatnonzero(pick.cells)], verdict=pick.verdict,
                    smell={k: round(v, 2) for k, v in pick.activations.items()}))

    add("end", held=sorted(memory.held()), pending=sorted(p.symbol for p in memory.pending), drift=round(memory.drift(), 5))

    if live:
        memory.sessions += 1
        memory.save()
    replay = write_replay(fly_id, when, not live, events) if live or record else None

    return {
        "session": memory.sessions if live else memory.sessions + 1,
        "lessons": memory.lessons,
        "settled": list(closed.items()),
        "settled_cells": settled_cells,
        "ranking": [(c.symbol, round(c.verdict, 3)) for c in candidates],
        "sold": sold,
        "order": order,
        "held": sorted(memory.held()),
        "pick_cells": int(pick.cells.sum()) if pick else 0,
        "replay": replay,
        "no_order": None if order else no_order,
        "max_positions": settings["max_positions"],
        "noise_floor": settings["noise_floor"],
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
