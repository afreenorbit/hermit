import { describe, expect, it } from 'vitest';

import { EMPTY, P } from '../palette';
import {
  borrowedShell,
  pieceColors,
  renderShellGrid,
  type ShellPieceInput,
} from './renderShellGrid';
import { toSVG } from './adapters';

const piece = (i: number, over: Partial<ShellPieceInput> = {}): ShellPieceInput => ({
  id: `pc_${i}`,
  brain_provider: (['claude-code', 'codex', 'opencode'] as const)[i % 3]!,
  temp_c: 22,
  dwell_s: 3600 + i * 600,
  departure: 'graceful',
  seed: 1000 + i * 7,
  local_hour: (i * 5) % 24,
  ...over,
});

const filled = (cells: number[]) => cells.filter((c) => c !== EMPTY).length;

describe('renderShellGrid', () => {
  it('draws nothing for an empty journey', () => {
    const g = renderShellGrid([], { size: 24 });
    expect(g.w).toBe(24);
    expect(g.cells).toHaveLength(24 * 24);
    expect(filled(g.cells)).toBe(0);
  });

  it('is deterministic', () => {
    const pieces = Array.from({ length: 8 }, (_, i) => piece(i));
    expect(renderShellGrid(pieces, { size: 48 })).toEqual(renderShellGrid(pieces, { size: 48 }));
  });

  it('draws one piece, owned by that piece', () => {
    const g = renderShellGrid([piece(0)], { size: 24 });
    expect(filled(g.cells)).toBeGreaterThan(10);
    expect(new Set(g.owners.filter((o) => o >= 0))).toEqual(new Set([0]));
  });

  it('grows as pieces arrive and every piece stays visible', () => {
    const counts = [1, 3, 8].map((n) =>
      filled(
        renderShellGrid(
          Array.from({ length: n }, (_, i) => piece(i)),
          { size: 48 },
        ).cells,
      ),
    );
    expect(counts[0]!).toBeLessThan(counts[1]!);
    expect(counts[1]!).toBeLessThan(counts[2]!);

    const g = renderShellGrid(
      Array.from({ length: 8 }, (_, i) => piece(i)),
      { size: 48 },
    );
    for (let i = 0; i < 8; i++) expect(g.owners).toContain(i);
  });

  it('fits sixty pieces in the grid without overflowing', () => {
    const pieces = Array.from({ length: 60 }, (_, i) => piece(i));
    const g = renderShellGrid(pieces, { size: 48 });
    expect(g.cells).toHaveLength(48 * 48);
    expect(new Set(g.owners.filter((o) => o >= 0)).size).toBeGreaterThan(50);
  });

  it('gives each departure its own outline', () => {
    const inks = (departure: ShellPieceInput['departure']) =>
      renderShellGrid([piece(0, { departure, brain_provider: 'other' })], {
        size: 48,
      }).cells.filter((c) => c === P.ink).length;
    const graceful = inks('graceful');
    const bedtime = inks('bedtime');
    const manual = inks('manual');
    expect(graceful).toBeGreaterThan(0);
    expect(bedtime).toBeLessThan(graceful); // dotted inner walls
    expect(manual).toBeLessThan(graceful); // dusk inner walls
    const many = (departure: ShellPieceInput['departure']) =>
      renderShellGrid(
        Array.from({ length: 6 }, (_, i) => piece(i, { departure, brain_provider: 'other' })),
        {
          size: 48,
        },
      );
    const solid = many('graceful');
    const cracked = many('abrupt');
    expect(cracked.cells).not.toEqual(solid.cells); // broken walls + cracks
    // the silhouette never breaks: same filled area either way
    expect(filled(cracked.cells)).toBe(filled(solid.cells));
  });

  it('colours by local hour of arrival, shaded by temperature', () => {
    expect(pieceColors(piece(0, { local_hour: 2, temp_c: 20 }))).toEqual([P.dream, P.night]);
    expect(pieceColors(piece(0, { local_hour: 11, temp_c: 20 }))).toEqual([P.leaf, P.sea]);
    expect(pieceColors(piece(0, { local_hour: 11, temp_c: 30 }))).toEqual([P.lime, P.cyan]);
    expect(pieceColors(piece(0, { local_hour: 11, temp_c: 2 }))).toEqual([P.teal, P.blue]);
  });

  it('has a borrowed shell for before any favor', () => {
    expect(filled(borrowedShell(24).cells)).toBeGreaterThan(50);
  });

  it('serialises to crisp SVG', () => {
    const svg = toSVG(renderShellGrid([piece(0)], { size: 24 }), 2);
    expect(svg).toContain('shape-rendering="crispEdges"');
    expect(svg).toContain('width="48"');
  });
});
