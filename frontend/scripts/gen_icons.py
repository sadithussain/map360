"""Generate placeholder PWA icons (solid indigo with a white map-pin glyph).

Pure-Python PNG writer so no image libraries are required. Run from the
frontend directory: ``python scripts/gen_icons.py``. Replace the output icons
with branded artwork before production.
"""

import math
import struct
import zlib
from pathlib import Path

BG = (79, 70, 229)  # indigo (#4f46e5)
FG = (255, 255, 255)
PUBLIC = Path(__file__).resolve().parent.parent / "public"


def _pin_color(x: int, y: int, size: int) -> tuple[int, int, int]:
    """Return the pixel color for a simple ring + dot map-pin glyph."""
    cx, cy = size / 2, size * 0.42
    r = size * 0.22
    ring = size * 0.06
    dist = math.hypot(x - cx, y - cy)
    if abs(dist - r) <= ring or dist <= size * 0.05:
        return FG
    # Stem below the ring.
    if abs(x - cx) <= ring and cy + r * 0.4 <= y <= size * 0.82:
        return FG
    return BG


def write_png(path: Path, size: int) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type: none
        for x in range(size):
            raw.extend(_pin_color(x, y, size))
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    PUBLIC.mkdir(parents=True, exist_ok=True)
    write_png(PUBLIC / "pwa-192x192.png", 192)
    write_png(PUBLIC / "pwa-512x512.png", 512)
