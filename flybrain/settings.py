"""A fly's settings: the numbers that are ours and not the connectome's.

Every fly has them in fly.json under "settings". `flybrain new` writes the
defaults there, so they are in plain sight. A key left out takes its default.
Change them between sessions, not during one.

  presentations   how many times the fly smells each symbol per session. The
                  verdict is the mean. More is steadier and slower
  board_size      how many symbols the fly looks at per session: what it holds,
                  plus symbols drawn at random
  max_positions   the most positions it holds at once. It buys at most one per
                  session, so it stops buying when it reaches this
  max_fraction    the largest share of the account one position can take, at a
                  verdict of full_verdict or more
  full_verdict    the verdict that buys a full-size position
  learning_rate   how far one closed trade moves the connections it touches
  recovery        how far every connection moves back toward the connectome
                  each session
  noise_floor     a holding is sold when its verdict is this far below its
                  purchase verdict two sessions in a row. A pick this close to
                  the runner-up is bought at half size

The fly never borrows. An order is capped at the cash in the account, so
max_positions times max_fraction can be above 1 without leverage.
"""

from typing import TypedDict

from .config import FlyConfig


class Settings(TypedDict):
    presentations: int
    board_size: int
    max_positions: int
    max_fraction: float
    full_verdict: float
    learning_rate: float
    recovery: float
    noise_floor: float


DEFAULTS: Settings = {
    "presentations": 5,
    "board_size": 8,
    "max_positions": 6,
    "max_fraction": 0.15,
    "full_verdict": 6.0,
    "learning_rate": 0.05,
    "recovery": 0.02,
    "noise_floor": 0.36,
}


def settings_for(config: FlyConfig) -> Settings:
    """The fly's settings over the defaults. Raises on a key it does not know or a value that cannot work."""
    given = config.get("settings", {})
    unknown = sorted(set(given) - set(DEFAULTS))
    if unknown:
        raise SystemExit(f"fly.json has settings this version does not know: {', '.join(unknown)}. Known: {', '.join(DEFAULTS)}")
    s: Settings = {**DEFAULTS, **given}
    problems = []
    if s["presentations"] < 1:
        problems.append("presentations must be 1 or more")
    if s["max_positions"] < 1:
        problems.append("max_positions must be 1 or more")
    if s["board_size"] < s["max_positions"] + 2:
        problems.append(f"board_size must be at least max_positions + 2 ({s['max_positions'] + 2}), so new symbols arrive every session")
    if not 0 < s["max_fraction"] <= 1:
        problems.append("max_fraction must be above 0 and at most 1")
    if s["full_verdict"] <= 0:
        problems.append("full_verdict must be above 0")
    if not 0 < s["learning_rate"] < 1 or not 0 <= s["recovery"] < 1:
        problems.append("learning_rate must be between 0 and 1, and recovery from 0 to below 1")
    if s["noise_floor"] < 0:
        problems.append("noise_floor must be 0 or more")
    if problems:
        raise SystemExit("fly.json settings: " + "; ".join(problems))
    return s
