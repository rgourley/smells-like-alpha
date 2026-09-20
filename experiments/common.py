"""An untrained fly and the reference setups, shared by the experiments."""

import tempfile
from pathlib import Path

import numpy as np

from flybrain.brain import Brain
from flybrain.memory import FlyMemory, from_connectome
from flybrain.smell import channel_map, individual_gains, smell, to_rates

SETUPS: dict[str, dict[str, float | str]] = {
    "oversold, heavy volume, near lows": dict(rsi=24, bb_position=0.08, distance_from_sma50=-0.12, volume_ratio=2.4, price_change_5d=-0.09, rsi_trend="falling"),
    "overbought breakout": dict(rsi=76, bb_position=0.93, distance_from_sma50=0.13, volume_ratio=2.1, price_change_5d=0.11, rsi_trend="rising"),
    "quiet drift up": dict(rsi=58, bb_position=0.62, distance_from_sma50=0.03, volume_ratio=0.9, price_change_5d=0.02, rsi_trend="rising"),
    "quiet drift down": dict(rsi=44, bb_position=0.38, distance_from_sma50=-0.03, volume_ratio=0.9, price_change_5d=-0.02, rsi_trend="falling"),
    "dead flat": dict(rsi=50, bb_position=0.50, distance_from_sma50=0.00, volume_ratio=1.0, price_change_5d=0.00, rsi_trend="flat"),
    "capitulation": dict(rsi=14, bb_position=0.02, distance_from_sma50=-0.19, volume_ratio=3.6, price_change_5d=-0.16, rsi_trend="falling"),
    "blow-off top": dict(rsi=88, bb_position=0.99, distance_from_sma50=0.18, volume_ratio=3.2, price_change_5d=0.15, rsi_trend="rising"),
    "squeeze, no volume": dict(rsi=52, bb_position=0.48, distance_from_sma50=0.01, volume_ratio=0.4, price_change_5d=0.00, rsi_trend="flat"),
}


class Fly:
    """The published wiring, untrained. `memory()` gives a fresh memory each time."""

    def __init__(self) -> None:
        self.brain = Brain()
        self.channels = channel_map(self.brain.circuit)
        self.gains = individual_gains(None, 0.0)

    def memory(self) -> FlyMemory:
        return from_connectome(self.brain.circuit, Path(tempfile.mkdtemp()))

    def counts(self, reading: dict[str, float | str], ms: float, seed: int) -> np.ndarray:
        """Spike count per Kenyon cell for one presentation."""
        return self.brain.present(to_rates(smell(reading), self.channels, self.gains), ms, seed)[self.brain.kc]

    def cells(self, reading: dict[str, float | str], ms: float, seed: int) -> np.ndarray:
        """Which Kenyon cells fired, as a boolean per cell."""
        return self.counts(reading, ms, seed) > 0
