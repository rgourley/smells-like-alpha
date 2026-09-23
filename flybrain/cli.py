"""The flybrain command.

    flybrain new 001 --universe crypto --cadence 4h      a fly with a generated name
    flybrain new 001 --name "My Fly" --ticker MYFLY      or name it yourself
    flybrain register 001     create the agent on ClawStreet and store its key
    flybrain run 001          a rehearsal: decides, prints, sends nothing
    flybrain run 001 --go     a real session: places the order and posts the note
    flybrain loop 001 --go    stay running and trade on the fly's schedule
    flybrain view             the 3D viewer on http://localhost:8790
    flybrain check            confirm the brain runs on this machine
"""

import argparse
import re
import secrets
import time
import zlib

from . import clawstreet
from .config import FlyConfig, api_key, fly_ids, home, load_fly, save_fly, store_api_key
from .run import after_session, run_once
from .schedule import due, mark_slot
from .session import utc_now
from .settings import DEFAULTS
from .view import serve

INDIVIDUAL_SIGMA = 0.2
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0, O, 1, I or L, so a code reads the same aloud


def generated_code() -> str:
    """Four characters. ClawStreet names are unique, and this gives about 900,000 of them."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))


def new(args: argparse.Namespace) -> None:
    if (home(args.fly) / "fly.json").exists():
        raise SystemExit(f"fly {args.fly} already exists")
    code = generated_code()
    name, ticker = args.name or f"Fly {code}", (args.ticker or f"FLY{code}").upper()
    if not 3 <= len(name) <= 50 or not 2 <= len(ticker) <= 12:
        raise SystemExit("ClawStreet needs a name of 3 to 50 characters and a ticker of 2 to 12")
    times = re.fullmatch(r"(\d\d:\d\d)(,\d\d:\d\d)*", args.cadence)
    if args.universe == "stocks" and args.cadence != "daily" and not times:
        raise SystemExit('a stock fly trades daily, or at listed New York times such as "12:30,15:30". '
                         "Use --universe crypto for an hourly cadence.")
    if args.universe == "crypto" and not re.fullmatch(r"\d{1,2}h", args.cadence):
        raise SystemExit('a crypto fly runs on an "<N>h" cadence, such as 4h.')
    config: FlyConfig = {
        "name": name, "ticker": ticker, "universe": args.universe, "cadence": args.cadence,
        "bot_id": None, "key": f"env:CLAWSTREET_API_KEY_{args.fly.upper()}",
        # The name sets the seed, so the same name always gives the same fly.
        "individuality": {"seed": None if args.published_wiring else zlib.crc32(name.encode()), "sigma": INDIVIDUAL_SIGMA},
        # The defaults, written out so they are in plain sight. flybrain/settings.py says what each one does.
        "settings": dict(DEFAULTS),
    }
    save_fly(args.fly, config)
    print(f"made {name} ({ticker}) in {home(args.fly) / 'fly.json'}. Next: flybrain register {args.fly}")


def register(args: argparse.Namespace) -> None:
    config = load_fly(args.fly)
    if config.get("bot_id"):
        raise SystemExit(f"{config['name']} is already registered as {config['bot_id']}")
    response = clawstreet.register(config["name"], config["ticker"], config["universe"], config["cadence"])
    place = store_api_key(config, response["api_key"])   # first, before anything else can fail
    config["bot_id"] = response["bot_id"]
    save_fly(args.fly, config)
    print(f"registered {config['name']} ({config['ticker']}) as {response['bot_id']}")
    print(f"the API key is in {place}. ClawStreet shows it once, so keep that file.")
    print(f"claim the agent here, signed in to ClawStreet: {response['claim_url']}  (code {response.get('verification_code')})")
    print(f"its public page: https://www.clawstreet.io/agents/{response['bot_id']}")


def run(args: argparse.Namespace) -> None:
    config = load_fly(args.fly)
    result = run_once(args.fly, config, live=args.go, record=args.record or args.go, board_seed=args.seed, data=args.data)
    after_session(config, result)


def loop(args: argparse.Namespace) -> None:
    print(f"fly {args.fly} is on its schedule ({load_fly(args.fly)['cadence']}). Ctrl+C to stop.")
    while True:
        config = load_fly(args.fly)
        slot, why = due(args.fly, config, utc_now())
        if slot:
            result = run_once(args.fly, config, live=args.go, record=True, data=args.data)
            mark_slot(args.fly, slot)
            after_session(config, result)
        elif args.verbose:
            print(f"{utc_now():%Y-%m-%d %H:%M} UTC: {why}")
        time.sleep(300)


def check(_: argparse.Namespace) -> None:
    """Load the circuit, smell one setup twice, and confirm the brain works on this machine."""
    import numpy as np

    from .brain import Brain
    from .smell import channel_map, individual_gains, smell, to_rates

    brain = Brain()
    reading = {"rsi": 76.0, "bb_position": 0.93, "distance_from_sma50": 0.13, "volume_ratio": 2.1, "price_change_5d": 0.11, "rsi_trend": "rising"}
    rates = to_rates(smell(reading), channel_map(brain.circuit), individual_gains(None, 0.0))
    first, again = (brain.present(rates, 50.0, seed=7)[brain.kc] > 0 for _ in range(2))
    share = first.mean() * 100
    if not np.array_equal(first, again):
        raise SystemExit("the same seed gave two different answers")
    if not 0.5 < share < 8:
        raise SystemExit(f"{share:.1f}% of the learning cells fired. The expected range is 0.5% to 8%")
    print(f"ok: {len(brain.circuit.body_ids):,} neurons, {int(first.sum())} of {len(brain.kc):,} learning cells fired ({share:.1f}%), repeatable")


def flies(_: argparse.Namespace) -> None:
    for fly_id in fly_ids():
        c = load_fly(fly_id)
        state = "registered" if c.get("bot_id") else "not registered"
        print(f"{fly_id}  {c['name']}  {c['universe']}, {c['cadence']}  {state}, key {'found' if api_key(c) else 'missing'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="flybrain", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="make a fly")
    p.add_argument("fly", help='a short id for the fly, such as "001"')
    p.add_argument("--name", help='3 to 50 characters, shown on ClawStreet and unique there. The default is generated, such as "Fly K7Q2"')
    p.add_argument("--ticker", help="2 to 12 characters. The default follows the name")
    p.add_argument("--universe", choices=["stocks", "crypto"], default="crypto")
    p.add_argument("--cadence", default="4h", help='"daily", New York times such as "12:30,15:30", or "<N>h" such as "4h"')
    p.add_argument("--published-wiring", action="store_true", help="use the connectome as published, with no individual variation")
    p.set_defaults(fn=new)

    p = sub.add_parser("register", help="create the agent on ClawStreet")
    p.add_argument("fly")
    p.set_defaults(fn=register)

    p = sub.add_parser("run", help="one session")
    p.add_argument("fly")
    p.add_argument("--go", action="store_true", help="place the order and post the note")
    p.add_argument("--record", action="store_true", help="save the replay of a rehearsal, for the viewer")
    p.add_argument("--seed", type=int, default=None, help="board seed. The default is the minute")
    p.add_argument("--data", choices=["clawstreet", "massive"], default="clawstreet", help="where the candles come from")
    p.set_defaults(fn=run)

    p = sub.add_parser("loop", help="run sessions on the fly's schedule until stopped")
    p.add_argument("fly")
    p.add_argument("--go", action="store_true", help="place orders and post notes")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--data", choices=["clawstreet", "massive"], default="clawstreet", help="where the candles come from")
    p.set_defaults(fn=loop)

    p = sub.add_parser("view", help="the 3D viewer")
    p.add_argument("--port", type=int, default=8790)
    p.set_defaults(fn=lambda a: serve(a.port))

    sub.add_parser("flies", help="list the flies on this machine").set_defaults(fn=flies)
    sub.add_parser("check", help="confirm the brain runs on this machine. Needs no account").set_defaults(fn=check)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
