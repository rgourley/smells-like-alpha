"""Innate ranking: the untrained fly's verdict on eight reference setups.

Four trials per setup at 100 ms, because the receptor input is random. The
result is the spread across setups against the trial-to-trial noise.
"""

import numpy as np

from .common import SETUPS, Fly


def main() -> None:
    fly = Fly()
    memory = fly.memory()
    rows = []
    for name, setup in SETUPS.items():
        verdicts = [memory.verdict(fly.cells(setup, 100.0, 300 + trial)) for trial in range(4)]
        rows.append((name, float(np.mean(verdicts)), float(np.std(verdicts))))
    rows.sort(key=lambda r: -r[1])
    for name, mean, sd in rows:
        print(f"{name:36s} {mean:6.3f}  s.d. {sd:.3f}")
    spread, noise = rows[0][1] - rows[-1][1], float(np.mean([r[2] for r in rows]))
    print(f"\nspread across setups {spread:.3f}, mean trial-to-trial s.d. {noise:.3f}, ratio {spread / noise:.1f}")


if __name__ == "__main__":
    main()
