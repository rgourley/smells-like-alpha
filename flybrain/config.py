"""Where a fly lives on disk, and how it finds its API key.

Each fly has a folder, flies/<id>/, that git ignores:

  fly.json         name, ticker, universe, cadence, bot_id, key, individuality, settings, after_session
  memory.npz       its synapses
  positions.json   what it holds and what it has sold
  replays/         one file per session, and index.json
  last_slot.txt    the last session slot that ran

The API key is never in fly.json. fly.json says where the key is:
"env:NAME" reads the variable NAME from the environment or from .env, and
"keychain:ITEM" reads the item ITEM from the macOS keychain.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
FLIES = ROOT / "flies"
ENV_FILE = ROOT / ".env"


class Individuality(TypedDict):
    seed: int | None
    sigma: float


class FlyConfig(TypedDict, total=False):
    name: str
    ticker: str
    universe: str            # "stocks" or "crypto"
    cadence: str             # "daily", New York times "12:30,15:30", or "<N>h"
    bot_id: str | None
    key: str                 # "env:NAME" or "keychain:ITEM"
    individuality: Individuality
    settings: dict[str, float]   # see flybrain/settings.py. A key left out takes its default
    after_session: list[str]  # a command to run after each session; "{replay}" becomes the replay path
    equity: float
    return_pct: float | None


def home(fly_id: str) -> Path:
    return FLIES / fly_id


def fly_ids() -> list[str]:
    return sorted(p.parent.name for p in FLIES.glob("*/fly.json"))


def load_fly(fly_id: str) -> FlyConfig:
    path = home(fly_id) / "fly.json"
    if not path.exists():
        raise SystemExit(f"no fly {fly_id}: {path} is missing. Make one with: flybrain new {fly_id}")
    return json.loads(path.read_text())


def save_fly(fly_id: str, config: FlyConfig) -> None:
    home(fly_id).mkdir(parents=True, exist_ok=True)
    (home(fly_id) / "fly.json").write_text(json.dumps(config, indent=1))


def read_env_file() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    pairs = (line.split("=", 1) for line in ENV_FILE.read_text().splitlines() if "=" in line and not line.lstrip().startswith("#"))
    return {k.strip(): v.strip().strip('"').strip("'") for k, v in pairs}


def api_key(config: FlyConfig) -> str | None:
    kind, _, name = config["key"].partition(":")
    if kind == "env":
        return os.environ.get(name) or read_env_file().get(name)
    if kind == "keychain":
        out = subprocess.run(["security", "find-generic-password", "-s", name, "-w"], capture_output=True, text=True)
        return out.stdout.strip() or None
    raise ValueError(f'key must start with "env:" or "keychain:", got {config["key"]!r}')


def store_api_key(config: FlyConfig, secret: str) -> str:
    """Save a new key where fly.json says keys live. Returns a description of the place."""
    kind, _, name = config["key"].partition(":")
    if kind == "keychain":
        subprocess.run(["security", "add-generic-password", "-s", name, "-a", "fly", "-w", secret, "-U"], check=True, capture_output=True)
        return f"the macOS keychain item {name}"
    if kind == "env":
        with ENV_FILE.open("a") as f:
            f.write(f"{name}={secret}\n")
        ENV_FILE.chmod(0o600)
        return f"{ENV_FILE} as {name}"
    raise ValueError(f'key must start with "env:" or "keychain:", got {config["key"]!r}')
