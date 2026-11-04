/**
 * The shell: pure, deterministic pixel generation from the pieces a journey made.
 * Owner: C. Phase 6.5 / plan.md §3.6.
 *
 * Pieces spiral outward from the center, oldest first. Colour comes from
 * temperature, dither pattern from the brain, segment length from dwell time,
 * outline from how Hermit left. The same grid is drawn on the critter's back,
 * in the map's shell panel and on the postcard.
 */

export interface ShellGrid {
  w: number;
  h: number;
  /** One palette index per cell, row-major. */
  cells: number[];
}

export interface ShellPiece {
  id: string;
  brain_provider: 'claude-code' | 'codex' | 'opencode' | 'other';
  temp_c: number | null;
  dwell_s: number;
  departure: 'graceful' | 'bedtime' | 'abrupt' | 'manual';
  seed: number;
}

export function renderShellGrid(
  _pieces: readonly ShellPiece[],
  _opts: { size: 24 | 48 } = { size: 24 },
): ShellGrid {
  throw new Error('TODO(C): Phase 6.5');
}
