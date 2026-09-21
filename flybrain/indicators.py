"""The six readings the fly smells, computed from daily candles.

The definitions match ClawStreet's /data/history, so a symbol smells the same
whichever source the candles come from:

  rsi                   RSI(14), Wilder's smoothing, on the closes
  bb_position           where the close is in the Bollinger band (20 days, 2
                        standard deviations), from 0 at the lower band to 1 at
                        the upper band
  distance_from_sma50   (close - 50-day average) / 50-day average
  volume_ratio          the last day's volume / the 20-day average volume
  price_change_5d       (close - close five days before) / close five days before
  rsi_trend             RSI now against RSI two days before: "rising" above +1,
                        "falling" below -1, "flat" between

A reading that needs more candles than there are is None. The fly reads None
as a dark channel.
"""

from typing import TypedDict

import numpy as np

BARS_NEEDED = 50


class Bar(TypedDict):
    """One daily candle."""

    open: float
    high: float
    low: float
    close: float
    volume: float


def rsi_series(closes: np.ndarray, period: int = 14) -> list[float]:
    """RSI for every day from the period-th change on, each rounded to two places."""
    change = np.diff(closes)
    gains, losses = np.clip(change, 0, None), np.clip(-change, 0, None)
    if len(change) < period:
        return []
    avg_gain, avg_loss = gains[:period].mean(), losses[:period].mean()
    out = []
    for k in range(period, len(change) + 1):
        if k > period:
            avg_gain = (avg_gain * (period - 1) + gains[k - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[k - 1]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else float("inf")
        out.append(round(100.0 - 100.0 / (1.0 + rs), 2) if np.isfinite(rs) else 100.0)
    return out


def history_entry(bars: list[Bar], current_price: float | None, periods: int = 20) -> dict:
    """One symbol in the shape of ClawStreet's /data/history, from its daily candles, oldest first.

    `current_price` is a live price when there is one. The readings use the
    last candle's close, as ClawStreet's do.
    """
    closes = np.array([b["close"] for b in bars], dtype=float)
    volumes = np.array([b["volume"] for b in bars], dtype=float)
    n = len(bars)
    rsi = rsi_series(closes)
    close = closes[-1]

    derived: dict[str, float | str | None] = {"price_change_5d": None, "volume_ratio": None, "rsi_trend": "flat",
                                              "bb_position": None, "distance_from_sma50": None}
    if n >= 6 and closes[-6] > 0:
        derived["price_change_5d"] = float((close - closes[-6]) / closes[-6])
    if n >= 20 and volumes[-1] > 0 and volumes[-20:].mean() > 0:
        derived["volume_ratio"] = float(volumes[-1] / volumes[-20:].mean())
    if len(rsi) >= 3:
        delta = rsi[-1] - rsi[-3]
        derived["rsi_trend"] = "rising" if delta > 1 else "falling" if delta < -1 else "flat"
    if n >= 20:
        mean, sd = closes[-20:].mean(), closes[-20:].std()   # the population standard deviation
        if sd > 0:
            derived["bb_position"] = float(np.clip((close - (mean - 2 * sd)) / (4 * sd), 0.0, 1.0))
    if n >= 50 and closes[-50:].mean() > 0:
        sma50 = closes[-50:].mean()
        derived["distance_from_sma50"] = float((close - sma50) / sma50)

    last = bars[-periods:]
    return {"prices": [b["close"] for b in last], "open": [b["open"] for b in last], "high": [b["high"] for b in last],
            "low": [b["low"] for b in last], "volumes": [b["volume"] for b in last], "rsi": rsi[-periods:],
            "current_price": current_price, "derived": derived}
