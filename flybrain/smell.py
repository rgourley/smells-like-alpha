"""Turn a symbol's indicators into a smell.

Nothing here identifies the company. Two symbols with the same readings
produce the same smell, so the fly learns setups, not names. A lesson from
one symbol applies to any other symbol in the same technical state.

Each feature has a row of channels that covers its range. A low reading and a
high reading activate different channels. Bands overlap, so nearby values
smell nearly alike and distant values share nothing. That overlap is what
makes a learned association generalize.

Channels the data cannot fill stay dark. The fly reads a dark channel as
nothing there, not as a reading of zero.
"""

from dataclasses import dataclass

import numpy as np

from .circuit import Circuit

MAX_HZ = 100.0
WIDTH = 0.75          # band overlap, in units of band spacing


@dataclass(frozen=True)
class Feature:
    """One indicator and the band centers that carry it."""

    name: str
    centers: tuple[float, ...]
    label: str


def _spread(lo: float, hi: float, n: int) -> tuple[float, ...]:
    return tuple(float(x) for x in np.linspace(lo, hi, n))


# Bands are fixed. RSI 30 means the same thing in March and in September, so a
# lesson stays true. In a market where every symbol is oversold, most of the
# board falls into the same bands.
FEATURES: tuple[Feature, ...] = (
    Feature("rsi", _spread(15, 85, 8), "RSI"),
    Feature("bb_position", _spread(0.0, 1.0, 8), "position in Bollinger band"),
    Feature("distance_from_sma50", _spread(-0.20, 0.20, 8), "distance from 50-day average"),
    Feature("volume_ratio", tuple(float(x) for x in np.geomspace(0.5, 3.0, 8)), "volume vs average"),
    Feature("price_change_5d", _spread(-0.15, 0.15, 8), "5-day return"),
    Feature("sentiment", _spread(-1.0, 1.0, 4), "news sentiment"),
)

# These readings are categories in the data, so they need no bands.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "rsi_trend": ("rising", "falling", "flat"),
    "earnings": ("tomorrow", "this week", "later", "none"),
}


def channel_names() -> list[str]:
    """Every channel, in a fixed order. The order must not change between runs."""
    names = []
    for feature in FEATURES:
        names += [f"{feature.name}[{i}]" for i in range(len(feature.centers))]
    for field, values in CATEGORIES.items():
        names += [f"{field}={v}" for v in values]
    return names


def smell(reading: dict[str, float | str | None]) -> dict[str, float]:
    """Turn one symbol's readings into channel activations, 0 to 1.

    A value lights the band it falls in and partly lights the bands next to
    it. A missing value leaves its channels dark.
    """
    out: dict[str, float] = {}
    for feature in FEATURES:
        value = reading.get(feature.name)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        centers = np.asarray(feature.centers, dtype=float)
        spacing = float(np.mean(np.diff(centers))) or 1.0
        strength = np.exp(-(((float(value) - centers) / (WIDTH * spacing)) ** 2))
        peak = strength.max()
        if peak <= 0:
            continue
        for i, s in enumerate(strength / peak):
            if s > 0.02:
                out[f"{feature.name}[{i}]"] = float(s)

    for field, values in CATEGORIES.items():
        got = reading.get(field)
        if got in values:
            out[f"{field}={got}"] = 1.0
    return out


def channel_map(circuit: Circuit) -> dict[str, list[int]]:
    """Give each channel a glomerulus, and list that glomerulus's receptor neurons.

    Channels and glomeruli are both sorted by name, so the assignment is the
    same on every run. It carries no meaning beyond being fixed.
    """
    glomerulus = circuit.types[circuit.receptor]
    bodies = circuit.body_ids[circuit.receptor]
    glomeruli = sorted(g for g in set(glomerulus) if g)
    names = channel_names()
    if len(names) > len(glomeruli):
        raise ValueError(f"{len(names)} channels needed, {len(glomeruli)} glomeruli available")
    return {name: [int(b) for b in bodies[glomerulus == glom]] for name, glom in zip(names, glomeruli)}


def individual_gains(seed: int | None, sigma: float) -> dict[str, float]:
    """A gain per channel that makes one fly differ from the next.

    Real flies with the same genes still differ in how strongly each
    glomerulus responds, and that gives each fly its own odor preferences
    (Honegger et al., PNAS 2020). A seed gives a fly a fixed set of gains,
    log-normal around 1. No seed gives every channel a gain of 1, which is the
    connectome as published.
    """
    names = channel_names()
    if seed is None or sigma <= 0:
        return {name: 1.0 for name in names}
    rng = np.random.default_rng(seed)
    return {name: float(g) for name, g in zip(names, rng.lognormal(0.0, sigma, len(names)))}


def to_rates(activations: dict[str, float], channels: dict[str, list[int]],
             gains: dict[str, float]) -> dict[int, float]:
    """Turn channel activations into a firing rate in Hz per receptor neuron."""
    rates: dict[int, float] = {}
    for name, strength in activations.items():
        for body_id in channels.get(name, ()):
            rates[body_id] = strength * gains[name] * MAX_HZ
    return rates


def describe(activations: dict[str, float]) -> str:
    """Say what a symbol smells of, in words."""
    by_feature: dict[str, list[str]] = {}
    for name, strength in sorted(activations.items(), key=lambda kv: -kv[1]):
        head = name.split("[")[0].split("=")[0]
        by_feature.setdefault(head, []).append(f"{name} {strength:.2f}")
    labels = {f.name: f.label for f in FEATURES}
    return "\n".join(f"{labels.get(head, head)}: " + ", ".join(parts[:2]) for head, parts in by_feature.items())
