"""Cut the smell circuit out of the MaleCNS v1.0 connectome.

    python scripts/build_circuit.py /path/to/malecns

You do not need to run this. data/circuit/ already holds its output. It is
here so the slice can be checked and rebuilt.

The input folder holds four files made from the MaleCNS v1.0 release
(https://male-cns.janelia.org, CC BY 4.0):

  body-annotations.feather            one row per neuron: bodyId, type, class
  weights.feather                     body_pre, body_post, weight (synapse count)
  2026_Completeness_malecns.csv       the neurons the model keeps, in model order
  2026_Connectivity_malecns.parquet   the same connections, signed by transmitter

The slice keeps the olfactory receptor neurons, the projection neurons that
take input from them and feed Kenyon cells, every Kenyon cell, APL, the
mushroom body output neurons, and the PAM and PPL1 dopamine neurons. It keeps
the connections among them. Projection neurons are found by wiring, not by name.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "circuit"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    ann = pd.read_feather(src / "body-annotations.feather").drop_duplicates("bodyId")
    model_ids = pd.read_csv(src / "2026_Completeness_malecns.csv", index_col=0).index.to_numpy()
    counts = pd.read_feather(src / "weights.feather", columns=["body_pre", "body_post", "weight"])
    signed = pd.read_parquet(src / "2026_Connectivity_malecns.parquet",
                             columns=["Presynaptic_ID", "Postsynaptic_ID", "Excitatory x Connectivity"])

    types = ann["type"].fillna("")
    ids = lambda mask: set(int(b) for b in ann[mask]["bodyId"])
    receptors = ids(ann["class"] == "olfactory")
    kenyon = ids(types.str.match(r"KC"))
    keep = receptors | kenyon | ids(types.str.contains("APL", na=False))
    keep |= ids(types.str.match(r"MBON")) | ids(types.str.match(r"(PAM|PPL1)"))
    from_receptors = set(counts[counts.body_pre.isin(receptors)]["body_post"])
    to_kenyon = set(counts[counts.body_post.isin(kenyon)]["body_pre"])
    keep |= from_receptors & to_kenyon
    keep &= set(int(b) for b in model_ids)

    edges = signed[signed.Presynaptic_ID.isin(keep) & signed.Postsynaptic_ID.isin(keep)]
    edges = edges.rename(columns={"Presynaptic_ID": "pre", "Postsynaptic_ID": "post",
                                  "Excitatory x Connectivity": "weight"}).astype({"weight": "int32"})
    wired = set(edges.pre) | set(edges.post)

    # Annotation order is kept. The Kenyon cell order sets the index of every
    # cell in a fly's memory and in its replays, so it must not change.
    neurons = ann[ann.bodyId.isin(wired)][["bodyId", "type", "class"]]
    neurons = neurons.rename(columns={"bodyId": "body_id", "class": "cls"}).reset_index(drop=True)

    OUT.mkdir(parents=True, exist_ok=True)
    neurons.to_parquet(OUT / "neurons.parquet", compression="zstd", index=False)
    edges.reset_index(drop=True).to_parquet(OUT / "edges.parquet", compression="zstd", index=False)
    print(f"{len(neurons):,} neurons, {len(edges):,} connections -> {OUT}")


if __name__ == "__main__":
    main()
