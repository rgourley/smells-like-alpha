"""Generalization: reward one setup eight times, then measure nearby setups.

The trained setup is moved in steps toward a very different one. The shift in
verdict at each step is given as a share of the trained setup's shift, next to
the share of Kenyon cells the step has in common with the trained setup.
"""

from flybrain.memory import LEARNING_RATE

from .common import Fly

PAIRINGS = 8
TRAINED = {"rsi": 28.0, "bb_position": 0.12, "distance_from_sma50": -0.09, "volume_ratio": 2.1, "price_change_5d": -0.07, "rsi_trend": "falling"}
AWAY = {"rsi": 78.0, "bb_position": 0.92, "distance_from_sma50": 0.11, "volume_ratio": 1.0, "price_change_5d": 0.09, "rsi_trend": "rising"}
STEPS = (0.0, 0.15, 0.3, 0.45, 0.6, 0.8, 1.0)


def blend(t: float) -> dict[str, float | str]:
    """The setup t of the way from TRAINED to AWAY."""
    return {k: (v if t < 0.5 else AWAY[k]) if isinstance(v, str) else v + (AWAY[k] - v) * t for k, v in TRAINED.items()}


def main() -> None:
    fly = Fly()
    patterns = {t: fly.cells(blend(t), 50.0, 77) for t in STEPS}
    trained = patterns[0.0]
    for label, profitable in (("reward", True), ("punish", False)):
        memory = fly.memory()
        before = {t: memory.verdict(p) for t, p in patterns.items()}
        for _ in range(PAIRINGS):
            memory.learn(list(trained.nonzero()[0]), profitable)
        peak = abs(memory.verdict(trained) - before[0.0])
        print(f"{label} the trained setup {PAIRINGS} times, learning rate {LEARNING_RATE}")
        print("distance  shared cells  shift as a share of the trained shift")
        for t, p in patterns.items():
            shared = (p & trained).sum() / max((p | trained).sum(), 1)
            print(f"{t:8.2f}  {shared * 100:11.0f}%  {abs(memory.verdict(p) - before[t]) / peak * 100:6.0f}%")
        print()


if __name__ == "__main__":
    main()
