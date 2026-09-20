"""What the fly remembers between sessions.

Two numbers per Kenyon cell: how strongly it drives the reward-side output
neurons, and how strongly it drives the punishment-side ones. Both start at
the values the connectome gives. They move only when a trade closes.

The memory also holds the open positions, each with the Kenyon cells that
fired when the fly chose it. When a position closes, the result goes to those
cells, not to the cells that fire today.

Nothing here is fitted to market data. The synapses move by a fixed rule in
response to one closed trade at a time.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .circuit import Circuit, kenyon_cells

# Settings. They are not from the connectome.
LEARNING_RATE = 0.05     # how far one result moves the synapses it touches
DECAY_RATE = 0.02        # how far every synapse drifts back each session
# The typical change in the verdict between two presentations of an unchanged
# setup. It is 0.2 for a quiet setup and 0.8 for an overbought breakout
# (python -m experiments.noise).
NOISE_FLOOR = 0.36


@dataclass
class OpenPosition:
    """A trade the fly has made and does not yet know the result of."""

    symbol: str
    opened: str
    qty: float
    price: float
    cells: list[int]      # Kenyon cells that fired when the fly chose it
    verdict: float        # the verdict at purchase
    smell: dict[str, float] = field(default_factory=dict)
    cooling: int = 0      # sessions in a row with a verdict below the purchase verdict


class FlyMemory:
    """The fly's learned state. It loads at the start of a session and saves at the end."""

    def __init__(self, baseline_reward: np.ndarray, baseline_punish: np.ndarray, home: Path) -> None:
        self.home = home
        self.state_path = home / "memory.npz"
        self.positions_path = home / "positions.json"
        self.baseline_reward = baseline_reward
        self.baseline_punish = baseline_punish
        self.to_reward = baseline_reward.copy()
        self.to_punish = baseline_punish.copy()
        self.sessions = 0
        self.lessons = 0        # closed trades the fly has learned from
        self.positions: list[OpenPosition] = []
        # Sold, result not known yet. Kept so the result still reaches the cells that chose the trade.
        self.pending: list[OpenPosition] = []

    # ---- persistence -------------------------------------------------

    def load(self) -> None:
        if self.state_path.exists():
            saved = np.load(self.state_path)
            if len(saved["to_reward"]) != len(self.to_reward):
                raise ValueError(f"{self.state_path} holds {len(saved['to_reward'])} cells, the circuit has {len(self.to_reward)}")
            self.to_reward = saved["to_reward"]
            self.to_punish = saved["to_punish"]
            self.sessions = int(saved["sessions"])
            self.lessons = int(saved["lessons"]) if "lessons" in saved else 0
        if self.positions_path.exists():
            raw = json.loads(self.positions_path.read_text())
            self.positions = [OpenPosition(**p) for p in raw["open"]]
            self.pending = [OpenPosition(**p) for p in raw["pending"]]

    def save(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self.state_path, to_reward=self.to_reward, to_punish=self.to_punish,
                            sessions=self.sessions, lessons=self.lessons)
        self.positions_path.write_text(json.dumps({
            "open": [asdict(p) for p in self.positions],
            "pending": [asdict(p) for p in self.pending],
        }, indent=1))

    # ---- the fly's opinion -------------------------------------------

    def verdict(self, cells: np.ndarray) -> float:
        """Reward-side drive minus punishment-side drive, summed over the cells that fired."""
        return float(self.to_reward[cells].sum() - self.to_punish[cells].sum())

    # ---- learning ----------------------------------------------------

    def learn(self, cells: list[int], profitable: bool) -> None:
        """Dopamine depresses the opposite side, for the cells that fired.

        A profit weakens their drive onto the punishment side, so the verdict
        for that smell rises. A loss weakens their drive onto the reward side.
        Only the cells that fired change, so the lesson belongs to that setup.
        """
        index = np.asarray(cells, dtype=int)
        if index.size == 0:
            return
        if profitable:
            self.to_punish[index] *= (1.0 - LEARNING_RATE)
        else:
            self.to_reward[index] *= (1.0 - LEARNING_RATE)

    def forget(self) -> None:
        """Move every synapse a little back toward its connectome value.

        The learning rule only weakens synapses. This recovery keeps them away
        from zero. It also makes a lesson fade unless new trades confirm it.
        """
        self.to_reward += DECAY_RATE * (self.baseline_reward - self.to_reward)
        self.to_punish += DECAY_RATE * (self.baseline_punish - self.to_punish)

    # ---- positions ---------------------------------------------------

    def open(self, position: OpenPosition) -> None:
        self.positions.append(position)

    def close(self, symbol: str, profitable: bool) -> OpenPosition | None:
        """Settle a trade and give the result to the cells that chose it.

        The search covers open and pending positions. A position the fly
        decided to sell leaves the open list before its result arrives.
        """
        for bucket in (self.pending, self.positions):
            for i, p in enumerate(bucket):
                if p.symbol == symbol:
                    self.learn(p.cells, profitable)
                    self.lessons += 1
                    return bucket.pop(i)
        return None

    def reconsider(self, symbol: str, verdict_today: float) -> bool:
        """Compare a holding with the verdict it was bought on.

        Returns True when the verdict has been below the purchase verdict by
        more than NOISE_FLOOR for two sessions in a row. One low verdict can
        be noise. Two in a row means the setup changed.
        """
        for p in self.positions:
            if p.symbol == symbol:
                p.cooling = p.cooling + 1 if verdict_today < p.verdict - NOISE_FLOOR else 0
                return p.cooling >= 2
        return False

    def sell(self, symbol: str) -> OpenPosition | None:
        """Move a holding to pending. The result reaches its cells when the trade closes."""
        for i, p in enumerate(self.positions):
            if p.symbol == symbol:
                self.pending.append(self.positions.pop(i))
                return p
        return None

    def held(self) -> set[str]:
        return {p.symbol for p in self.positions}

    def drift(self) -> float:
        """How far the fly has moved from the connectome it started with."""
        moved = np.abs(self.to_reward - self.baseline_reward) + np.abs(self.to_punish - self.baseline_punish)
        return float(moved.mean())


def from_connectome(circuit: Circuit, home: Path) -> FlyMemory:
    """Build an untrained memory from the wiring.

    An output neuron is on the reward side when it gets more synapses from
    PAM dopamine neurons than from PPL1, and on the punishment side when it
    gets more from PPL1. Nothing is assigned by hand.
    """
    kc, mbon = kenyon_cells(circuit), circuit.where(r"MBON")
    from_pam = circuit.count(circuit.where(r"PAM"), mbon).groupby("post")["count"].sum()
    from_ppl = circuit.count(circuit.where(r"PPL1"), mbon).groupby("post")["count"].sum()
    reward_side = [m for m in mbon if from_pam.get(m, 0) > from_ppl.get(m, 0)]
    punish_side = [m for m in mbon if from_ppl.get(m, 0) > from_pam.get(m, 0)]

    def drive(side: list[int]) -> np.ndarray:
        onto = circuit.count(kc, np.array(side)).groupby("pre")["count"].sum()
        return np.array([onto.get(i, 0) for i in kc], dtype=float)

    to_reward, to_punish = drive(reward_side), drive(punish_side)
    scale = max(to_reward.max(), to_punish.max(), 1.0)
    return FlyMemory(to_reward / scale, to_punish / scale, home)
