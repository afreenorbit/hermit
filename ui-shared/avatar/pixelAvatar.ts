/**
 * host_id -> deterministic 8x8 symmetric pixel face. No photos, ever. Owner: C.
 *
 * Only the left half is generated; the right half mirrors it, which is what
 * makes random pixels read as a face.
 */
import { fnv1a, mulberry32 } from '../lib/hash';
import { blankGrid, EMPTY, P, type PixelGrid } from '../palette';

const SKIN: readonly number[] = [P.ember, P.sun, P.mist, P.lime, P.cyan, P.paper];
const HAIR: readonly number[] = [P.ink, P.night, P.dream, P.berry, P.navy, P.teal];
const BG: readonly number[] = [P.sea, P.leaf, P.dusk, P.dream, P.berry, P.blue];

const HEAD = [
  '..####..',
  '.######.',
  '########',
  '########',
  '########',
  '########',
  '.######.',
  '..####..',
];

function pick<T>(rand: () => number, list: readonly T[]): T {
  return list[Math.floor(rand() * list.length)] as T;
}

export interface AvatarOptions {
  /** Fill the square behind the head (houses, chips). */
  background?: boolean;
}

export function pixelAvatar(hostId: string, opts: AvatarOptions = {}): PixelGrid {
  const rand = mulberry32(fnv1a(`avatar:${hostId}`));
  const skin = pick(rand, SKIN);
  const hair = pick(rand, HAIR);
  const bg = pick(
    rand,
    BG.filter((c) => c !== hair),
  );
  const style = Math.floor(rand() * 4); // 0 cap, 1 long, 2 spiky, 3 antenna
  const eyes = Math.floor(rand() * 3); // 0 dot, 1 tall, 2 wide-set
  const mouth = Math.floor(rand() * 3); // 0 small, 1 wide, 2 smile
  const cheeks = rand() < 0.5;

  const g = blankGrid(8, 8);
  const set = (x: number, y: number, c: number): void => {
    if (x < 0 || y < 0 || x >= 8 || y >= 8) return;
    g.cells[y * 8 + x] = c;
    g.cells[y * 8 + (7 - x)] = c;
  };

  if (opts.background) for (let i = 0; i < 64; i++) g.cells[i] = bg;

  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 4; x++) if (HEAD[y]![x] === '#') set(x, y, skin);
  }

  // hair
  for (let x = 0; x < 4; x++) {
    set(x, 0, HEAD[0]![x] === '#' ? hair : opts.background ? bg : EMPTY);
    if (x >= 1) set(x, 1, hair);
  }
  if (style === 0) set(0, 2, hair);
  if (style === 1) for (let y = 2; y <= 5; y++) set(0, y, hair);
  if (style === 2) {
    set(1, 0, hair);
    set(3, 0, opts.background ? bg : EMPTY);
    set(2, 0, hair);
  }
  if (style === 3) {
    set(1, 1, skin);
    set(3, 0, hair);
  }

  // eyes
  if (eyes === 0) set(2, 3, P.ink);
  if (eyes === 1) {
    set(2, 3, P.ink);
    set(2, 4, P.ink);
  }
  if (eyes === 2) {
    set(1, 3, P.ink);
    set(2, 3, P.paper);
  }

  // mouth
  if (mouth === 0) set(3, 5, P.ink);
  if (mouth === 1) {
    set(2, 5, P.ink);
    set(3, 5, P.ink);
  }
  if (mouth === 2) {
    set(2, 5, P.ink);
    set(3, 6, P.ink);
  }

  if (cheeks) set(1, 5, P.berry);
  return g;
}

/** One stable accent colour per host, for chips and route highlights. */
export function hostAccent(hostId: string): number {
  return BG[fnv1a(`accent:${hostId}`) % BG.length] as number;
}
