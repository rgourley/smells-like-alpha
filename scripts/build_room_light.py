"""Halve the room-light HDR for the viewer.

    python scripts/build_room_light.py /path/to/lythwood_room_1k.hdr

You do not need to run this. viewer/textures/room_light_512.hdr already holds
its output. The source is Poly Haven's Lythwood Room panorama (CC0) at 1024 by
512. The viewer only uses it to light the scene and to tint reflections, and
three.js blurs it before use, so 512 by 256 lights the scene the same way at
a quarter of the size.

The pixels are averaged in linear light, 2 by 2, and written back as
run-length encoded Radiance RGBE, the format the viewer's loader reads.
"""

import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "viewer" / "textures" / "room_light_512.hdr"


def read_rgbe(path: Path) -> np.ndarray:
    """A run-length encoded Radiance file as linear float RGB, shape (height, width, 3)."""
    raw = path.read_bytes()
    head_end = raw.index(b"\n\n") + 2
    line_end = raw.index(b"\n", head_end)
    _, h, _, w = raw[head_end:line_end].split()
    height, width, p = int(h), int(w), line_end + 1
    rgbe = np.empty((height, width, 4), dtype=np.uint8)
    for y in range(height):
        if raw[p] != 2 or raw[p + 1] != 2 or (raw[p + 2] << 8 | raw[p + 3]) != width:
            raise ValueError(f"{path} scanline {y} is not new-style run-length encoded")
        p += 4
        for c in range(4):
            x = 0
            while x < width:
                n = raw[p]; p += 1
                if n > 128:
                    rgbe[y, x:x + n - 128, c] = raw[p]; p += 1; x += n - 128
                else:
                    rgbe[y, x:x + n, c] = np.frombuffer(raw, dtype=np.uint8, count=n, offset=p); p += n; x += n
    exponent = rgbe[..., 3].astype(np.int32)
    scale = np.where(exponent > 0, np.ldexp(1.0, exponent - 136), 0.0)
    return rgbe[..., :3].astype(np.float64) * scale[..., None]


def to_rgbe(rgb: np.ndarray) -> np.ndarray:
    brightest = rgb.max(axis=-1)
    mantissa, exponent = np.frexp(brightest)
    scale = np.where(brightest > 1e-32, mantissa * 256.0 / np.maximum(brightest, 1e-32), 0.0)
    out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.clip(rgb * scale[..., None], 0, 255).astype(np.uint8)
    out[..., 3] = np.where(brightest > 1e-32, exponent + 128, 0).astype(np.uint8)
    return out


def encode_channel(row: np.ndarray) -> bytes:
    """One channel of one scanline: runs of 4 or more as (128 + n, value), the rest as (n, bytes)."""
    out, x, n = bytearray(), 0, len(row)
    while x < n:
        run = 1
        while x + run < n and run < 127 and row[x + run] == row[x]:
            run += 1
        if run >= 4:
            out += bytes((128 + run, int(row[x]))); x += run
            continue
        start = x
        while x < n and x - start < 128:
            run = 1
            while x + run < n and run < 4 and row[x + run] == row[x]:
                run += 1
            if run >= 4:
                break
            x += 1
        out += bytes((x - start,)) + row[start:x].tobytes()
    return bytes(out)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    rgb = read_rgbe(Path(sys.argv[1]))
    h, w = rgb.shape[:2]
    half = rgb.reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3))
    rgbe = to_rgbe(half)
    body = bytearray()
    for row in rgbe:
        body += bytes((2, 2, (w // 2) >> 8, (w // 2) & 255))
        for c in range(4):
            body += encode_channel(row[:, c])
    OUT.write_bytes(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n" + f"-Y {h // 2} +X {w // 2}\n".encode() + bytes(body))
    back = read_rgbe(OUT)
    print(f"{w}x{h} -> {w // 2}x{h // 2}, {OUT.stat().st_size / 1e6:.2f} MB. Largest error after the round trip: "
          f"{np.abs(back - half).max() / half.max() * 100:.3f}% of the brightest pixel")


if __name__ == "__main__":
    main()
