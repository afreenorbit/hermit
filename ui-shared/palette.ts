/**
 * Sweetie 16 (Lospec) — the only art palette. Every sprite, shell, avatar and
 * map tile is a grid of indices into this array. Owner: C. plan.md §3.6.
 */

export const SWEETIE16 = [
  '#1a1c2c', // 0 ink
  '#5d275d', // 1 dream
  '#b13e53', // 2 berry
  '#ef7d57', // 3 ember
  '#ffcd75', // 4 sun
  '#a7f070', // 5 lime
  '#38b764', // 6 leaf
  '#257179', // 7 teal
  '#29366f', // 8 navy
  '#3b5dc9', // 9 blue
  '#41a6f6', // 10 sea
  '#73eff7', // 11 cyan
  '#f4f4f4', // 12 paper
  '#94b0c2', // 13 mist
  '#566c86', // 14 dusk
  '#333c57', // 15 night
] as const;

export const P = {
  ink: 0,
  dream: 1,
  berry: 2,
  ember: 3,
  sun: 4,
  lime: 5,
  leaf: 6,
  teal: 7,
  navy: 8,
  blue: 9,
  sea: 10,
  cyan: 11,
  paper: 12,
  mist: 13,
  dusk: 14,
  night: 15,
} as const;

/** A transparent cell. */
export const EMPTY = -1;

/** Row-major grid of palette indices; `EMPTY` is transparent. */
export interface PixelGrid {
  w: number;
  h: number;
  cells: number[];
}

export function blankGrid(w: number, h: number): PixelGrid {
  return { w, h, cells: new Array<number>(w * h).fill(EMPTY) };
}

export function colorOf(index: number): string | null {
  return index < 0 ? null : (SWEETIE16[index] ?? null);
}

/**
 * Parse ASCII pixel art. Each character is looked up in `key`; anything not in
 * the key (usually `.`) is transparent.
 */
export function gridFromRows(rows: readonly string[], key: Record<string, number>): PixelGrid {
  const h = rows.length;
  const w = Math.max(...rows.map((r) => r.length));
  const grid = blankGrid(w, h);
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const v = key[row[x] as string];
      if (v !== undefined) grid.cells[y * w + x] = v;
    }
  });
  return grid;
}

/** Shared key for hand-drawn glyphs. */
export const ART_KEY: Record<string, number> = {
  k: P.ink,
  p: P.dream,
  r: P.berry,
  e: P.ember,
  s: P.sun,
  g: P.lime,
  l: P.leaf,
  t: P.teal,
  n: P.navy,
  u: P.blue,
  b: P.sea,
  c: P.cyan,
  w: P.paper,
  m: P.mist,
  d: P.dusk,
  h: P.night,
};
