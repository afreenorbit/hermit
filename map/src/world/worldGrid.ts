/** Loads the baked land/sea mask (scripts/make_pixel_world.py). Owner: C. */

export const GRID_COLS = 1440;
export const GRID_ROWS = 720;
const CELL = 0.25;

export interface LandMask {
  isLand(lat: number, lon: number): boolean;
}

export function maskFromBytes(bytes: Uint8Array): LandMask {
  return {
    isLand(lat, lon) {
      const col = ((Math.floor((lon + 180) / CELL) % GRID_COLS) + GRID_COLS) % GRID_COLS;
      const row = Math.min(GRID_ROWS - 1, Math.max(0, Math.floor((90 - lat) / CELL)));
      const bit = row * GRID_COLS + col;
      return ((bytes[bit >> 3] ?? 0) & (0x80 >> (bit & 7))) !== 0;
    },
  };
}

let pending: Promise<LandMask | null> | null = null;

/** Fetched once, only when a wide view needs it (~130 KB). */
export function loadLandMask(base = import.meta.env.BASE_URL): Promise<LandMask | null> {
  pending ??= fetch(`${base}data/world-grid.bin`)
    .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
    .then((buf) => maskFromBytes(new Uint8Array(buf)))
    .catch(() => null);
  return pending;
}
