/**
 * The shell: pure, deterministic pixel generation from the pieces a journey made.
 * Owner: C. plan.md §3.6.
 *
 * Pieces are laid along a spiral tube from the apex outward, oldest first, so
 * the shell visibly grows. Four independent axes make each piece readable:
 *
 *   colour   local hour of arrival (night / dawn / day / dusk), shaded by temp_c
 *   pattern  brain: claude-code = checker, codex = stripes, opencode = waves
 *   length   log(dwell_s)
 *   outline  graceful = solid, bedtime = dotted, abrupt = cracked, manual = dusk
 *
 * The same grid is drawn on the critter's back, in the map's shell panel and on
 * the postcard, so the shell is one recognisable object everywhere.
 */
import { hash2 } from '../lib/hash';
import { hourBand, type BrainProvider, type Departure, type HourBand } from '../lib/format';
import { EMPTY, P, type PixelGrid } from '../palette';

export interface ShellPieceInput {
  id: string;
  brain_provider: BrainProvider;
  temp_c?: number | null;
  dwell_s: number;
  departure: Departure;
  seed: number;
  created_at?: string;
  /** Local hour of arrival, 0–24. Callers compute it (see `localHour`). */
  local_hour?: number | null;
}

/** @deprecated use ShellPieceInput */
export type ShellPiece = ShellPieceInput;

export interface ShellGrid extends PixelGrid {
  /** Index into `pieces` for every cell, or -1. Used for hover and focus. */
  owners: number[];
}

export interface ShellOptions {
  size: 24 | 48;
  /** Draw every piece in mist/dusk — Hermit's borrowed shell before it has any. */
  mono?: boolean;
}

const TWO_PI = Math.PI * 2;

const BAND: Record<HourBand, [number, number]> = {
  night: [P.dream, P.night],
  dawn: [P.ember, P.sun],
  day: [P.leaf, P.sea],
  dusk: [P.berry, P.dusk],
};

const LIGHTER: Record<number, number> = {
  [P.dream]: P.berry,
  [P.night]: P.dusk,
  [P.ember]: P.sun,
  [P.sun]: P.paper,
  [P.leaf]: P.lime,
  [P.sea]: P.cyan,
  [P.berry]: P.ember,
  [P.dusk]: P.mist,
};

const DARKER: Record<number, number> = {
  [P.dream]: P.navy,
  [P.night]: P.navy,
  [P.ember]: P.berry,
  [P.sun]: P.ember,
  [P.leaf]: P.teal,
  [P.sea]: P.blue,
  [P.berry]: P.dream,
  [P.dusk]: P.night,
};

export const HOT_C = 27;
export const COLD_C = 12;

/** Base colour pair [A, B] for a piece, after the temperature shade. */
export function pieceColors(piece: ShellPieceInput): [number, number] {
  const [a, b] = BAND[hourBand(pieceHour(piece))];
  const t = piece.temp_c;
  if (t != null && t >= HOT_C) return [LIGHTER[a] ?? a, LIGHTER[b] ?? b];
  if (t != null && t <= COLD_C) return [DARKER[a] ?? a, DARKER[b] ?? b];
  return [a, b];
}

export function pieceHour(piece: ShellPieceInput): number {
  if (piece.local_hour != null) return piece.local_hour;
  if (piece.created_at) {
    const d = new Date(piece.created_at);
    if (!Number.isNaN(d.getTime())) return d.getUTCHours() + d.getUTCMinutes() / 60;
  }
  return 12;
}

/** Arc length (radians) a piece takes along the spiral. */
export function segmentLength(dwellS: number): number {
  return 0.9 + 0.55 * Math.log(1 + Math.max(0, dwellS) / 300);
}

/** True when the brain's dither pattern puts colour B on this cell. */
export function patternB(brain: BrainProvider, x: number, y: number): boolean {
  switch (brain) {
    case 'claude-code':
      return (x + y) % 2 === 0;
    case 'codex':
      return y % 2 === 0;
    case 'opencode': {
      const wave = Math.round(Math.sin(x * 0.9) * 1.2);
      return (((x + y + wave) % 3) + 3) % 3 === 0;
    }
    default:
      return false;
  }
}

/**
 * Colour for an inner wall (between whorls or pieces), or null to show fill.
 * The outer silhouette is always solid ink so the shell reads at any size.
 */
function wallColor(dep: Departure, x: number, y: number, seed: number): number | null {
  switch (dep) {
    case 'graceful':
      return P.ink;
    case 'manual':
      return P.dusk;
    case 'bedtime':
      return (x + y) % 2 === 0 ? P.ink : null;
    case 'abrupt':
      return hash2(x, y, seed) % 3 === 0 ? null : P.ink;
  }
}

export function renderShellGrid(
  pieces: readonly ShellPieceInput[],
  opts: ShellOptions = { size: 24 },
): ShellGrid {
  const size = opts.size;
  const n = size * size;
  const cells = new Array<number>(n).fill(EMPTY);
  const owners = new Array<number>(n).fill(-1);
  if (pieces.length === 0) return { w: size, h: size, cells, owners };

  // Lay pieces along the spiral, compressing if they would overflow the grid.
  const maxTurns = size >= 48 ? 3.4 : 2.8;
  let lens = pieces.map((p) => segmentLength(p.dwell_s));
  const total = lens.reduce((a, b) => a + b, 0);
  const cap = maxTurns * TWO_PI;
  if (total > cap) lens = lens.map((l) => (l * cap) / total);
  const T = Math.min(total, cap);
  const ends: number[] = [];
  let acc = 0;
  for (const l of lens) ends.push((acc += l));

  // A young shell is small and grows into the grid as pieces arrive.
  const R = size / 2 - 0.5;
  const c = R / (Math.max(T, 1.5 * TWO_PI) + TWO_PI);
  const cx = (size - 1) / 2;
  const cy = (size - 1) / 2;
  const whorl = new Array<number>(n).fill(-99);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - cx;
      const dy = y - cy;
      const u = Math.hypot(dx, dy) / c;
      // Start the spiral pointing up-left so the aperture faces the body.
      let theta = Math.atan2(dy, dx) + Math.PI * 0.75;
      theta = ((theta % TWO_PI) + TWO_PI) % TWO_PI;
      const k = Math.floor((u - theta) / TWO_PI);
      const t = theta + k * TWO_PI;
      let owner: number;
      if (k < 0) {
        // Inside the first turn: the apex. Solid, owned by the oldest piece.
        if (u > T + TWO_PI) continue;
        owner = 0;
      } else {
        if (t > T) continue;
        owner = ends.findIndex((e) => t < e);
        if (owner < 0) owner = pieces.length - 1;
      }
      const i = y * size + x;
      owners[i] = owner;
      whorl[i] = k;
    }
  }

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = y * size + x;
      const owner = owners[i] ?? -1;
      if (owner < 0) continue;
      const piece = pieces[owner]!;
      const k = whorl[i] ?? 0;

      let outer = false;
      let wall = false;
      for (const [nx, ny] of [
        [x - 1, y],
        [x + 1, y],
        [x, y - 1],
        [x, y + 1],
      ] as const) {
        if (nx < 0 || ny < 0 || nx >= size || ny >= size) {
          outer = true;
          break;
        }
        const j = ny * size + nx;
        const no = owners[j] ?? -1;
        const nk = whorl[j] ?? -99;
        if (no < 0) {
          outer = true;
          break;
        }
        if (nk < k || (nk === k && no < owner)) wall = true;
      }

      // Patterns need room: at 24px the tube is ~3px, so draw flat colour there.
      const [a, b] = opts.mono ? [P.mist, P.paper] : pieceColors(piece);
      const detail = size >= 48 && !opts.mono;
      const fill = detail && patternB(piece.brain_provider, x, y) ? b : a;

      if (outer) {
        cells[i] = P.ink;
      } else if (wall) {
        cells[i] = (opts.mono ? P.dusk : wallColor(piece.departure, x, y, piece.seed)) ?? fill;
      } else if (opts.mono && (x + y) % 5 === 0 && k >= 0) {
        cells[i] = b; // a little shine on the borrowed shell
      } else if (!opts.mono && piece.departure === 'abrupt' && isCrack(x, y, piece.seed)) {
        cells[i] = P.ink;
      } else {
        cells[i] = fill;
      }
    }
  }

  return { w: size, h: size, cells, owners };
}

/** A zig-zag hairline crack through abrupt pieces. */
function isCrack(x: number, y: number, seed: number): boolean {
  const phase = seed % 5;
  return (x + phase) % 5 === (y % 2 === 0 ? 0 : 1) && hash2(x, y, seed) % 2 === 0;
}

const BORROWED: ShellPieceInput[] = [0, 1, 2, 3].map((i) => ({
  id: `borrowed-${i}`,
  brain_provider: 'other',
  dwell_s: 3600,
  departure: 'graceful',
  seed: i,
}));

/** The plain shell Hermit wears before any favor has been done. */
export function borrowedShell(size: 24 | 48 = 24): ShellGrid {
  return renderShellGrid(BORROWED, { size, mono: true });
}

/** A small outlined swatch of one hour band × brain pattern, for legends. */
export function patternGrid(band: HourBand, brain: BrainProvider, size = 8): PixelGrid {
  const [a, b] = BAND[band];
  const cells = new Array<number>(size * size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const edge = x === 0 || y === 0 || x === size - 1 || y === size - 1;
      cells[y * size + x] = edge ? P.ink : patternB(brain, x, y) ? b : a;
    }
  }
  return { w: size, h: size, cells };
}
