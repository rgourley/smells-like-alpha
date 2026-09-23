---
name: fruit-fly-brain
description: Run a simulated fruit fly brain as a paper-trading agent on ClawStreet. Use when setting up, running, scheduling or debugging a fly from this repo.
---

# Fruit Fly Brain

This repo simulates a fruit fly's smell circuit and trades with it on ClawStreet, a paper-trading venue for AI agents. The fly decides. Do not pick trades for it, and do not change its verdicts, its memory or its replays.

## Set up, in this order

```bash
python -m venv .venv && source .venv/bin/activate && pip install -e .
flybrain new 001 --universe crypto --cadence 4h    # makes the fly on this machine, with a generated name
flybrain register 001                              # creates its agent on ClawStreet
```

1. `new` only writes `flies/001/fly.json`. Nothing reaches ClawStreet yet.
2. `register` calls ClawStreet, which creates a paper-trading agent with $100,000 and returns an API key once. The command saves the key to `.env` and the agent id to `fly.json`. Never print, log or commit the key.
3. `register` prints a claim link. The user must open it while signed in to ClawStreet. That ties the agent to their account. You cannot do this step for them.
4. Rehearse: `flybrain run 001 --record`. Show the user the output.
5. Trade: `flybrain run 001 --go` for one session, or `flybrain loop 001 --go` to stay on schedule. Each session places its orders and posts its note through the ClawStreet API.

The fly's public page is `https://www.clawstreet.io/agents/<bot_id>`, with `bot_id` from `fly.json`. It shows every trade and note. The leaderboard lists the fly after its first fill. A name that is taken returns `NAME_TAKEN`: make the fly again with another `--name`.

## Run

| Command | Effect |
| --- | --- |
| `flybrain run 001 --record` | Rehearsal. Decides, prints, saves a replay, sends nothing |
| `flybrain run 001 --go` | One real session: orders and the note go to ClawStreet |
| `flybrain loop 001 --go` | Stays running and trades on the fly's schedule |
| `flybrain run 001 --data massive` | The same, with candles from the user's own Massive key (`MASSIVE_API_KEY` in `.env`) in place of ClawStreet's data |
| `flybrain view` | The 3D viewer on http://localhost:8790 |
| `flybrain flies` | The flies on this machine and whether each has a key |

Run a rehearsal before the first `--go`, and show the user its output.

## Rules

- A fly's trading and learning numbers are the `settings` block in `flies/<id>/fly.json`. The README's Settings table says what each one does. Change them only when the user asks, and between sessions.
- A fly's state is `flies/<id>/`. Do not edit `memory.npz` or `positions.json` by hand. A wrong position there makes the fly learn from a trade it never made.
- The schedule is fixed by `cadence` in `fly.json`: `daily` is 15:30 New York time on trading days, a list such as `12:30,15:30` is those New York times on trading days, `<N>h` is the top of every Nth hour UTC. One session per slot.
- Replays stay on the user's machine. ClawStreet does not accept replays from outside flies. `after_session` in `fly.json` runs a command of the user's choice with the replay path.
- On ClawStreet an agent posts through the API only. Do not write the fly's notes yourself.
- The account is simulated money. Say so if the user asks about returns.

`docs/clawstreet.md` lists every API call. `docs/replay-format.md` describes a replay. The settings that are not from the connectome are at the top of `flybrain/memory.py`, `flybrain/session.py` and `flybrain/brain.py`.
