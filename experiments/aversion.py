"""Trials to aversion: consecutive losses needed to turn a positive verdict negative."""

from flybrain.memory import DECAY_RATE, LEARNING_RATE

from .common import SETUPS, Fly

CHOSEN = ("dead flat", "overbought breakout", "oversold, heavy volume, near lows")


def main() -> None:
    fly = Fly()
    print(f"learning rate {LEARNING_RATE}, recovery {DECAY_RATE} per session\n")
    for name in CHOSEN:
        cells = fly.cells(SETUPS[name], 50.0, 77)
        for recover in (False, True):
            memory = fly.memory()
            start, losses = memory.verdict(cells), 0
            while memory.verdict(cells) >= 0 and losses < 200:
                memory.learn(list(cells.nonzero()[0]), profitable=False)
                if recover:
                    memory.forget()
                losses += 1
            print(f"{name:36s} {'with recovery' if recover else 'no recovery  '}  initial verdict {start:+.2f}  losses {losses}")


if __name__ == "__main__":
    main()
