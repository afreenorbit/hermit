/**
 * The art palette: 16 roles, coloured to match Tilli (cream paper, sage shell,
 * butter skin, peach heart, cocoa ink). Every sprite, shell, avatar and map
 * tile is a grid of indices into this array, so recolouring here restyles all
 * generated art at once. Owner: C. plan.md §3.6.
 *
 * Index roles are unchanged from the original Sweetie 16 layout; the export
 * name is kept so callers and contracts did not have to move.
 */

export const SWEETIE16 = [
  '#5b3d27', // 0 ink — cocoa outline
  '#8a6a9e', // 1 dream — plum night
  '#d97a6c', // 2 berry — rose
  '#f2a07f', // 3 ember — peach
  '#f8d98a', // 4 sun — butter
  '#e3e9b0', // 5 lime — pale sage
  '#a9b97a', // 6 leaf — sage
  '#7d9567', // 7 teal — deep sage
  '#55507a', // 8 navy — dusk indigo
  '#8a9fd0', // 9 blue — periwinkle
  '#9fcbe0', // 10 sea — sky
  '#d3ecf1', // 11 cyan — pale sky
  '#fffaf1', // 12 paper — cream
  '#eadfc8', // 13 mist — oat
  '#a48f77', // 14 dusk — cocoa grey
  '#6a5878', // 15 night — dusky plum
] as const;

/** Same array, by its new name. */
export const PALETTE = SWEETIE16;

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
