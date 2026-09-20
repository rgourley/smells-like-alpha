"""Verdict noise against a real change of state.

First, one symbol recovering from oversold to overbought: how far the verdict
moves. Second, the same unchanged setup on five days: how far the verdict
moves when nothing changed, as a mean of five presentations. Third, single
presentations of an unchanged setup, next to the mean of five, which is what
a live session uses. NOISE_FLOOR in memory.py is set against these.
"""

import numpy as np

from .common import SETUPS, Fly

TRIALS = 5
RECOVERY = [
    ("day 0, bought here", dict(rsi=24, bb_position=0.08, distance_from_sma50=-0.12, volume_ratio=2.4, price_change_5d=-0.09, rsi_trend="falling")),
    ("day 2, bouncing", dict(rsi=36, bb_position=0.28, distance_from_sma50=-0.07, volume_ratio=1.8, price_change_5d=0.02, rsi_trend="rising")),
    ("day 5, recovered", dict(rsi=52, bb_position=0.52, distance_from_sma50=0.00, volume_ratio=1.3, price_change_5d=0.06, rsi_trend="rising")),
    ("day 9, extended", dict(rsi=68, bb_position=0.80, distance_from_sma50=0.07, volume_ratio=1.1, price_change_5d=0.09, rsi_trend="rising")),
    ("day 12, overbought", dict(rsi=79, bb_position=0.94, distance_from_sma50=0.12, volume_ratio=1.0, price_change_5d=0.11, rsi_trend="rising")),
]


def main() -> None:
    fly = Fly()
    memory = fly.memory()
    mean = lambda reading, seed0: float(np.mean([memory.verdict(fly.cells(reading, 50.0, seed0 + t)) for t in range(TRIALS)]))

    print("a symbol recovering from oversold to overbought")
    base = mean(RECOVERY[0][1], 900)
    for tag, reading in RECOVERY:
        v = mean(reading, 900)
        print(f"  {tag:20s} verdict {v:+.3f}  change from purchase {v - base:+.3f}")

    print("\nthe same setup, unchanged, on five days")
    seen = [mean(RECOVERY[0][1], 2000 + day * 7) for day in range(5)]
    for day, v in enumerate(seen):
        print(f"  day {day}  verdict {v:+.3f}")
    print(f"\nrange across five unchanged days: {max(seen) - min(seen):.3f}")

    print("\nsingle presentations of an unchanged setup, 40 each")
    for name, reading in (("oversold, heavy volume, near lows", RECOVERY[0][1]), ("dead flat", SETUPS["dead flat"]),
                          ("overbought breakout", SETUPS["overbought breakout"])):
        v = np.array([memory.verdict(fly.cells(reading, 50.0, 5000 + k)) for k in range(40)])
        five = v.reshape(8, 5).mean(axis=1)   # what a session uses: the mean of five presentations
        print(f"  {name:36s} one presentation: s.d. {v.std():.2f}, mean change {np.abs(np.diff(v)).mean():.2f}"
              f"  |  mean of five: s.d. {five.std():.2f}, mean change {np.abs(np.diff(five)).mean():.2f}")


if __name__ == "__main__":
    main()
