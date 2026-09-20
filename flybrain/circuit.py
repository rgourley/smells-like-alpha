"""The wiring of the smell circuit, read from data/circuit/.

7,443 neurons and the connections among them, from the MaleCNS v1.0
connectome (FlyEM at HHMI Janelia, Google Research, Cambridge Connectomics
Group, CC BY 4.0). scripts/build_circuit.py makes the two files.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "circuit"


@dataclass(frozen=True)
class Circuit:
    """Neurons by position, and connections as index arrays.

    `weight` is the synapse count of a connection. It is positive for an
    excitatory connection and negative for an inhibitory one.
    """

    body_ids: np.ndarray
    types: np.ndarray
    receptor: np.ndarray      # boolean per neuron: an olfactory receptor neuron
    pre: np.ndarray
    post: np.ndarray
    weight: np.ndarray

    def where(self, pattern: str, contains: bool = False) -> np.ndarray:
        """Positions of the neurons whose type matches a regular expression."""
        types = pd.Series(self.types)
        mask = types.str.contains(pattern) if contains else types.str.match(pattern)
        return np.flatnonzero(mask.to_numpy())

    def count(self, pre: np.ndarray, post: np.ndarray) -> pd.DataFrame:
        """Connections from one set of positions to another, with synapse counts."""
        mask = np.isin(self.pre, pre) & np.isin(self.post, post)
        return pd.DataFrame({"pre": self.pre[mask], "post": self.post[mask],
                             "count": np.abs(self.weight[mask])})


@lru_cache(maxsize=1)
def load() -> Circuit:
    neurons = pd.read_parquet(DATA / "neurons.parquet")
    edges = pd.read_parquet(DATA / "edges.parquet")
    body_ids = neurons["body_id"].to_numpy()
    position = {int(b): i for i, b in enumerate(body_ids)}
    return Circuit(
        body_ids=body_ids,
        types=neurons["type"].fillna("").to_numpy(),
        receptor=(neurons["cls"] == "olfactory").to_numpy(),
        pre=edges["pre"].map(position).to_numpy(),
        post=edges["post"].map(position).to_numpy(),
        weight=edges["weight"].to_numpy(),
    )


def kenyon_cells(circuit: Circuit) -> np.ndarray:
    """Positions of the Kenyon cells. This order indexes a fly's memory and its replays."""
    return circuit.where(r"KC")
