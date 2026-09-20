"""Information retained by the Kenyon cell code.

200 synthetic setups, labeled positive when at least two of three conditions
hold: RSI below 45, volume ratio above 1.3, Bollinger position below 0.4. A
logistic regression predicts the label from the Kenyon cell response, scored
by ROC AUC under five-fold stratified cross-validation. Controls: the same
responses with cells shuffled per setup, a random sparse expansion of matched
size and sparseness, and the raw channel activations.

This measures what the representation preserves, not trading results.
Needs scikit-learn: pip install -e ".[experiments]"
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from flybrain.smell import channel_names, smell

from .common import Fly

N_SETUPS = 200


def make_setups(n: int, rng: np.random.Generator) -> list[dict[str, float | str]]:
    return [{
        "rsi": float(np.clip(rng.normal(52, 16), 5, 95)),
        "bb_position": float(np.clip(rng.beta(2, 2), 0, 1)),
        "distance_from_sma50": float(rng.normal(0.01, 0.07)),
        "volume_ratio": float(np.clip(rng.lognormal(0.1, 0.45), 0.3, 4.0)),
        "price_change_5d": float(rng.normal(0.0, 0.05)),
        "rsi_trend": str(rng.choice(["rising", "falling", "flat"])),
    } for _ in range(n)]


def label(setup: dict[str, float | str]) -> int:
    return int((setup["rsi"] < 45) + (setup["volume_ratio"] > 1.3) + (setup["bb_position"] < 0.4) >= 2)


def auc(X: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=4000, C=0.05))
    scores = cross_val_score(model, X, y, cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=0), scoring="roc_auc")
    return float(scores.mean()), float(scores.std())


def main() -> None:
    setups = make_setups(N_SETUPS, np.random.default_rng(17))
    y = np.array([label(s) for s in setups])
    print(f"{N_SETUPS} setups, {y.sum()} positive, {len(y) - y.sum()} negative")

    fly = Fly()
    channels = channel_names()
    inputs = np.array([[smell(s).get(c, 0.0) for c in channels] for s in setups])
    X = np.array([fly.counts(s, 100.0, 1000 + i).astype(float) for i, s in enumerate(setups)])
    print(f"Kenyon cells active per setup: {(X > 0).mean() * 100:.1f}%\n")

    shuffled = X.copy()
    for i in range(len(shuffled)):
        np.random.default_rng(i).shuffle(shuffled[i])

    rng = np.random.default_rng(99)
    weights = np.zeros((len(channels), X.shape[1]))
    for j in range(X.shape[1]):
        weights[rng.choice(len(channels), size=6, replace=False), j] = 1.0
    raw = inputs @ weights
    keep = int((X > 0).mean() * X.shape[1])
    expansion = np.zeros_like(raw)
    for i in range(len(raw)):
        top = np.argsort(raw[i])[-keep:]
        expansion[i, top] = raw[i, top]

    for name, data in (("raw inputs", inputs), ("random sparse expansion", expansion), ("connectome wiring", X), ("shuffled control", shuffled)):
        mean, sd = auc(data, y)
        print(f"{name:26s} ROC AUC {mean:.3f} +/- {sd:.3f}")
    print(f"{'chance':26s} ROC AUC 0.500")


if __name__ == "__main__":
    main()
