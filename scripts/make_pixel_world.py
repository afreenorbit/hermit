"""Bake a land/sea mask into map/public/data/world-grid.bin. Owner: C. Phase 7.2.

Format (read by map/src/world/worldGrid.ts):
  0.25 degree cells, 1440 columns x 720 rows, row 0 = the band just below 90N,
  column 0 = the band just east of 180W. Bit-packed row-major, most significant
  bit first; 1 = land. 1440 * 720 / 8 = 129,600 bytes, no header.

Source: the public-domain `global-land-mask` package (GLOBE 1 km dataset).
Each cell is land if the majority of a 3x3 sample inside it is land, which
keeps small islands without letting coastlines bloat.

    pip install global-land-mask numpy
    python scripts/make_pixel_world.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from global_land_mask import globe

CELL = 0.25
COLS = int(360 / CELL)
ROWS = int(180 / CELL)
OUT = Path(__file__).resolve().parents[1] / "map" / "public" / "data" / "world-grid.bin"


def bake() -> np.ndarray:
    offsets = (np.arange(3) + 0.5) / 3 * CELL
    lons = -180 + np.arange(COLS)[:, None] * CELL + offsets[None, :]  # (COLS, 3)
    lats = 90 - np.arange(ROWS)[:, None] * CELL - offsets[None, :]  # (ROWS, 3)
    # (ROWS, 3, COLS, 3) sample grid -> majority vote per cell
    lat_g = np.broadcast_to(lats[:, :, None, None], (ROWS, 3, COLS, 3))
    lon_g = np.broadcast_to(lons[None, None, :, :], (ROWS, 3, COLS, 3))
    land = globe.is_land(lat_g.reshape(-1), lon_g.reshape(-1)).reshape(ROWS, 3, COLS, 3)
    return land.sum(axis=(1, 3)) >= 5


def main() -> None:
    mask = bake()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(np.packbits(mask.astype(np.uint8), axis=None, bitorder="big").tobytes())
    print(f"wrote {OUT.relative_to(OUT.parents[3])}: {COLS}x{ROWS}, {mask.mean():.1%} land")


if __name__ == "__main__":
    main()
