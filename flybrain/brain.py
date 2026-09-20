"""The smell circuit as a spiking simulation in Brian2.

Neurons are leaky integrate-and-fire units. The equations and parameters are
from Shiu et al., "A Drosophila computational brain model reveals
sensorimotor processing", Nature 2024 (model code MIT, Philip Shiu and Nico
Spiller, see NOTICE.md). Every neuron uses the same parameters. The weight of
a connection is its synapse count times W_SYN.
"""

import os

import numpy as np
from brian2 import (BrianLogger, Hz, Network, NeuronGroup, PoissonGroup, SpikeMonitor,
                    Synapses, TimedArray, defaultclock, mV, ms, prefs, seed as seed_brian)

from .circuit import Circuit, kenyon_cells, load
from .config import read_env_file

# "numpy" needs no C compiler and runs on any machine. "cython" is faster and needs one.
prefs.codegen.target = os.environ.get("FLYBRAIN_CODEGEN") or read_env_file().get("FLYBRAIN_CODEGEN", "numpy")
BrianLogger.log_level_error()

PARAMS = {
    "v_0": -52 * mV,
    "v_rst": -52 * mV,
    "v_th": -45 * mV,
    "t_mbr": 20 * ms,
    "tau": 5 * ms,
    "t_rfc": 2.2 * ms,
    "t_dly": 1.8 * ms,
}
W_SYN = 0.275 * mV
F_POI = 250

EQS = """
dv/dt = (v_0 - v + g - inhib) / t_mbr : volt (unless refractory)
dg/dt = -g / tau                       : volt (unless refractory)
dtrace/dt = -trace / t_apl             : 1
inhib                                  : volt
rfc                                    : second
"""

# APL does not spike. It releases GABA continuously, in proportion to the
# Kenyon cell activity it sees. That feedback holds the mushroom body at a
# few percent active, so different odors activate different cells.
#
# APL_GAIN is the one number here that is not from the connectome. At 250 the
# circuit runs at about 4% of Kenyon cells active per odor, the level measured
# in real flies. The per-cell strengths come from the APL synapses in the data.
APL_GAIN = 250.0
T_APL = 100 * ms


class Brain:
    """The loaded circuit. Build one and show it every odor of a session."""

    def __init__(self, apl_gain: float = APL_GAIN) -> None:
        self.circuit: Circuit = load()
        self.n = len(self.circuit.body_ids)
        self.apl_gain = apl_gain
        self.kc = kenyon_cells(self.circuit)
        self.apl = self.circuit.where(r"APL", contains=True)

        body = self.circuit.body_ids
        to_apl = self.circuit.count(self.kc, self.apl).groupby("pre")["count"].sum()
        from_apl = self.circuit.count(self.apl, self.kc).groupby("post")["count"].sum()
        from_apl = from_apl / from_apl.mean()   # the gain sets the scale, not the raw count
        self.kc_drive = np.array([to_apl.get(i, 0) for i in self.kc], dtype=float)
        self.apl_strength = np.array([from_apl.get(i, 1.0) for i in self.kc], dtype=float)
        self.position = {int(b): i for i, b in enumerate(body)}

    def present(self, rates: dict[int, float], duration_ms: float, seed: int) -> np.ndarray:
        """Drive receptor neurons at the given rates and return spike counts per neuron.

        `rates` maps a receptor neuron's body id to a firing rate in Hz. The
        network starts from rest. The receptor spikes are random draws, so two
        seeds give two slightly different answers for the same odor.
        """
        seed_brian(seed)   # the same seed gives the same spikes
        stim_ids = sorted(rates)
        stim_index = np.array([self.position[b] for b in stim_ids])
        stim = TimedArray(np.array([[rates[b] for b in stim_ids]], dtype=np.float64) * Hz, dt=duration_ms * ms)

        defaultclock.dt = 0.1 * ms
        neu = NeuronGroup(self.n, EQS, method="euler", threshold="v > v_th",
                          reset="v = v_rst; g = 0 * mV; trace += 1", refractory="rfc",
                          namespace={**PARAMS, "t_apl": T_APL})
        neu.v = PARAMS["v_0"]
        neu.g = 0 * mV
        neu.inhib = 0 * mV
        neu.trace = 0
        neu.rfc = PARAMS["t_rfc"]
        neu.rfc[stim_index] = 0 * ms

        syn = Synapses(neu, neu, "w : volt", on_pre="g += w", delay=PARAMS["t_dly"])
        syn.connect(i=self.circuit.pre, j=self.circuit.post)
        syn.w = self.circuit.weight * W_SYN

        drive = PoissonGroup(len(stim_ids), rates="stim(t, i)", namespace={"stim": stim})
        feed = Synapses(drive, neu, on_pre="v_post += w_stim", namespace={"w_stim": W_SYN * F_POI})
        feed.connect(i=np.arange(len(stim_ids)), j=stim_index)

        monitor = SpikeMonitor(neu, record=False)
        net = Network(neu, syn, drive, feed, *self._graded_apl(neu), monitor)
        net.run(duration_ms * ms)
        return np.asarray(monitor.count[:], dtype=np.int64)

    def _graded_apl(self, neu: NeuronGroup) -> list:
        """APL as continuous feedback inhibition.

        Kenyon cell activity sums into APL. APL pushes back on every Kenyon
        cell in proportion to that total. The more cells fire, the harder they
        are damped, so only the most strongly driven cells stay active.
        """
        apl = NeuronGroup(1, "level : 1", namespace={})
        gather = Synapses(neu, apl, "level_post = w_k * trace_pre : 1 (summed)\nw_k : 1")
        gather.connect(i=self.kc, j=0)
        gather.w_k = self.kc_drive / max(float(np.mean(self.kc_drive)), 1e-9) / len(self.kc)

        spread = Synapses(apl, neu, "inhib_post = gain * w_a * level_pre * mV : volt (summed)\nw_a : 1",
                          namespace={"gain": self.apl_gain})
        spread.connect(i=0, j=self.kc)
        spread.w_a = self.apl_strength
        return [apl, gather, spread]
