"""Pack the fly's body meshes into one file for the viewer.

    python scripts/build_body_pack.py /path/to/stl/folder

You do not need to run this. viewer/model/body.bin and body.json already hold
its output. The input is the folder of NeuroMechFly STL meshes (flygym, EPFL,
Apache-2.0), one per body part named in viewer/model/rig.json.

An STL stores every triangle's three corners in full, so a vertex shared by
six triangles is written six times. The pack stores each vertex once, plus
indices, in the viewer's frame and units: MuJoCo (x, y, z) in meters becomes
three.js (y, z, x) in millimeters. The browser then makes one request in place
of 39, and the server compresses a .bin file, which it does not do for .stl.

body.json: {"parts": {name: {"vertices": [byte offset, count], "indices": [byte offset, count], "wide": bool}}}
body.bin:  float32 positions and uint16 indices (uint32 when "wide"), each block on a 4-byte boundary.
"""

import json
import sys
from pathlib import Path

import numpy as np

MODEL = Path(__file__).resolve().parent.parent / "viewer" / "model"


def read_stl(path: Path) -> np.ndarray:
    """Triangle corners from a binary STL, as an (n, 3, 3) float32 array."""
    raw = path.read_bytes()
    count = int(np.frombuffer(raw, dtype="<u4", count=1, offset=80)[0])
    record = np.dtype([("normal", "<f4", 3), ("corners", "<f4", (3, 3)), ("attr", "<u2")])
    return np.frombuffer(raw, dtype=record, count=count, offset=84)["corners"]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    source = Path(sys.argv[1])
    rig = json.loads((MODEL / "rig.json").read_text())
    names = sorted(set(rig["mesh"].values()))

    blob, parts = bytearray(), {}
    for name in names:
        corners = read_stl(source / f"{name}.stl").reshape(-1, 3)
        # The viewer's frame and units. The arithmetic is in float32, as the viewer did it.
        points = (corners[:, [1, 2, 0]] * np.float32(1000)).astype(np.float32)
        # Corners closer than 0.00001 mm are one vertex, so normals come out smooth.
        keys = np.trunc(points.astype(np.float64) * 1e5).astype(np.int64)
        _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        order = np.argsort(first)                      # keep vertices in the order they first appear
        rank = np.empty_like(order); rank[order] = np.arange(len(order))
        vertices, indices = points[first[order]], rank[inverse.reshape(-1)]
        wide = len(vertices) > 65535
        entry = {"wide": bool(wide)}
        for key, data in (("vertices", vertices.astype("<f4")), ("indices", indices.astype("<u4" if wide else "<u2"))):
            blob.extend(b"\0" * (-len(blob) % 4))
            entry[key] = [len(blob), int(len(data))]
            blob.extend(data.tobytes())
        parts[name] = entry

    (MODEL / "body.bin").write_bytes(bytes(blob))
    (MODEL / "body.json").write_text(json.dumps({"parts": parts}, separators=(",", ":")))
    print(f"{len(names)} parts, {sum(p['vertices'][1] for p in parts.values()):,} vertices, "
          f"{sum(p['indices'][1] for p in parts.values()) // 3:,} triangles -> {len(blob) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
