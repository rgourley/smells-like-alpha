# The replay format

A session writes one JSON file to `flies/<id>/replays/`, named by the minute it ran, such as `2026-09-20T0400.json`. A rehearsal ends in `.dry.json`. `index.json` in the same folder lists the files, oldest first. The viewer plays the last one.

```json
{ "fly": "001", "when": "2026-09-20T04:00:08+00:00", "dry": false, "events": [ ... ] }
```

Each event has `step` (its position, from 0) and `type`. Events appear in the order they happened.

| Type | Fields |
| --- | --- |
| `start` | `session`, `held` (symbols), `drift`, `universe` (`stocks` or `crypto`), `cadence` (`daily` or `<N>h`) |
| `board` | `stocks`: per symbol, `reading` (the six indicators), `price`, `bars` (up to 20 candles as `[open, high, low, close]`) |
| `settle` | `symbol`, `profitable`, `cells` (how many learned), `opened`, `compartment` (`reward` or `punishment`) |
| `forget` | `drift` after recovery |
| `sniff` | `symbol`, `held`, `channels` (activation per smell channel, 0 to 1), `cells` (indices, 0 to 4063, of the Kenyon cells that fired in most of the presentations), `verdict` (the mean over the presentations) |
| `reconsider` | `symbol`, `verdict_then`, `verdict_now`, `cooling` (sessions in a row below the purchase verdict) |
| `sell` | `symbol`, `reason` |
| `rank` | `order`: `[symbol, verdict]` pairs, best first |
| `buy` | `symbol`, `dollars`, `verdict`, `margin` (over the next symbol the fly could buy), `smell` (the strongest channels, in words) |
| `end` | `held`, `pending` (sold, result not known yet), `drift` |
| `thought` | `body` (the note posted to ClawStreet), `qty`, `price`. `qty` and `price` are null when the session placed no order |

`drift` is the mean distance of the fly's synapses from their connectome values. It is 0 for a fly that has not learned anything.

A reading holds `rsi`, `bb_position`, `distance_from_sma50`, `volume_ratio`, `price_change_5d` and `rsi_trend` (`rising`, `falling` or `flat`). A missing value is null.
