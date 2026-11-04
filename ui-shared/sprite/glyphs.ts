/**
 * Small hand-drawn pixel glyphs: icons, effects, the map house and the tiny
 * walking Hermit. Owner: C. All original, Sweetie 16 only.
 *
 * Key: k ink, p dream, r berry, e ember, s sun, g lime, l leaf, t teal, n navy,
 *      u blue, b sea, c cyan, w paper, m mist, d dusk, h night, # currentColor.
 */
import { ART_KEY, blankGrid, gridFromRows, P, type PixelGrid } from '../palette';

/** Placeholder for "use the surrounding text colour" in icon grids. */
export const CURRENT = 99;
const KEY = { ...ART_KEY, '#': CURRENT };
const g = (rows: string[]): PixelGrid => gridFromRows(rows, KEY);

export const ICONS = {
  sun: g(['...s...', '.s.s.s.', '..sss..', 'sssssss', '..sss..', '.s.s.s.', '...s...']),
  partly: g(['..s....', 's.s.s..', '.sssww.', 'sswwwww', '.wwwwww', '.mwwwwm', '..mmmm.']),
  cloud: g(['.......', '..www..', '.wwwww.', 'wwwwwww', 'wwwwwww', 'mwwwwwm', '.mmmmm.']),
  fog: g(['.......', 'mmmmm..', '.......', '..mmmmm', '.......', 'mmmmm..', '.......']),
  rain: g(['..www..', '.wwwww.', 'wwwwwww', 'mmmmmmm', '.b..b..', '..b..b.', '.b..b..']),
  snow: g(['..www..', '.wwwww.', 'wwwwwww', 'mmmmmmm', '.w...w.', '...w...', '.w...w.']),
  storm: g(['..ddd..', '.ddddd.', 'ddddddd', 'hhhshhh', '...s...', '..s....', '.s.....']),
  unknown: g(['..###..', '.#...#.', '.....#.', '....#..', '...#...', '.......', '...#...']),
  moon: g(['..###..', '.##....', '##.....', '##.....', '##.....', '.##....', '..###..']),
  bolt: g(['...##..', '..##...', '.##....', '#####..', '..##...', '.##....', '##.....']),
  check: g(['.......', '......#', '.....##', '#...##.', '##.##..', '.###...', '..#....']),
  cross: g(['.......', '#.....#', '.#...#.', '..#.#..', '...#...', '..#.#..', '.#...#.']),
  star: g(['...#...', '...#...', '.#####.', '..###..', '..#.#..', '.#...#.', '.......']),
  heart: g(['.......', '.##.##.', '#######', '#######', '.#####.', '..###..', '...#...']),
  quest: g(['..###..', '..###..', '..###..', '..###..', '...#...', '.......', '..###..']),
  note: g(['....##.', '....#.#', '....#..', '....#..', '.###...', '####...', '.##....']),
  close: g(['#.....#', '.#...#.', '..#.#..', '...#...', '..#.#..', '.#...#.', '#.....#']),
  play: g(['.#.....', '.##....', '.###...', '.####..', '.###...', '.##....', '.#.....']),
  chat: g(['#######', '#.....#', '#.#.#.#', '#.....#', '###.###', '..##...', '..#....']),
  house: g(['...#...', '..###..', '.#####.', '#######', '.#.#.#.', '.#.#.#.', '.#####.']),
  shell: g(['..###..', '.#...#.', '#..#..#', '#.#.#.#', '#..##.#', '.#...#.', '..####.']),
  route: g(['#......', '.#.....', '..#.#..', '.....#.', '....#..', '...#...', '..#....']),
  plus: g(['.......', '...#...', '...#...', '.#####.', '...#...', '...#...', '.......']),
  minus: g(['.......', '.......', '.......', '.#####.', '.......', '.......', '.......']),
  fit: g(['##...##', '#.....#', '.......', '...#...', '.......', '#.....#', '##...##']),
  sound: g(['...#...', '..##.#.', '####..#', '####.#.', '####..#', '..##.#.', '...#...']),
  mute: g(['...#...', '..##...', '####.#.', '####..#', '####.#.', '..##...', '...#...']),
  camera: g(['.......', '.##....', '#######', '##...##', '##.#.##', '##...##', '#######']),
  people: g(['.#...#.', '###.###', '.#...#.', '###.###', '###.###', '#.#.#.#', '.......']),
  chain: g(['.......', '##..##.', '#.##.#.', '#.##.#.', '.##..##', '.......', '.......']),
  clock: g(['.#####.', '#..#..#', '#..#..#', '#..##.#', '#.....#', '#.....#', '.#####.']),
} as const;

export type IconName = keyof typeof ICONS;

/** Brain marks, 5x5, drawn in currentColor on the badge. */
export const BRAIN_ICONS = {
  'claude-code': g(['#.#.#', '.###.', '#####', '.###.', '#.#.#']),
  codex: g(['.#.#.', '#...#', '#...#', '#...#', '.#.#.']),
  opencode: g(['#####', '#...#', '#.#.#', '#...#', '#####']),
  other: g(['.###.', '#...#', '..##.', '.....', '..#..']),
} as const;

/** 16x16 house; the avatar is composited into the window at (4, 7). */
export const HOUSE = gridFromRows(
  [
    '.......kk.......',
    '......kerk......',
    '.....kerrrk.....',
    '....kerrrrrk....',
    '...kerrrrrrrk...',
    '..kerrrrrrrrrk..',
    '.kkkkkkkkkkkkkk.',
    '.kwk........kwk.',
    '.kwk........kwk.',
    '.kwk........kmk.',
    '.kwk........kwk.',
    '.kmk........kwk.',
    '.kwk........kwk.',
    '.kwk........kmk.',
    '.kwk........kwk.',
    '.kkkkkkkkkkkkkk.',
  ],
  ART_KEY,
);
/** Top-left of the 8x8 window the host's avatar sits in. */
export const HOUSE_WINDOW = { x: 4, y: 7 } as const;

/** A 9x8 Hermit for the map, two walking frames. */
export const MINI_HERMIT = [
  gridFromRows(
    [
      '...k.k...',
      '..kwkwk..',
      '.kmmkkk..',
      'kmdmmeek.',
      'kmmdkeesk',
      '.kmkeeek.',
      '..krkrk..',
      '..k...k..',
    ],
    ART_KEY,
  ),
  gridFromRows(
    [
      '...k.k...',
      '..kwkwk..',
      '.kmmkkk..',
      'kmdmmeek.',
      'kmmdkeesk',
      '.kmkeeek.',
      '...krkr..',
      '...k.k...',
    ],
    ART_KEY,
  ),
] as const;

function frames(
  w: number,
  h: number,
  n: number,
  draw: (f: number, set: (x: number, y: number, c: number) => void) => void,
): PixelGrid[] {
  return Array.from({ length: n }, (_, f) => {
    const grid = blankGrid(w, h);
    draw(f, (x, y, c) => {
      if (x >= 0 && y >= 0 && x < w && y < h) grid.cells[y * w + x] = c;
    });
    return grid;
  });
}

/** Arrival puff, 5 frames, 20x8. */
export const DUST = frames(20, 8, 5, (f, set) => {
  const r = 2 + f * 1.6;
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI;
    const x = Math.round(10 + Math.cos(a) * r * 1.4);
    const y = Math.round(7 - Math.sin(a) * r * 0.55);
    const c = f >= 3 ? P.mist : i % 2 ? P.paper : P.mist;
    if (f < 4 || i % 2 === 0) set(x, y, c);
  }
});

/** Sleep z's, 3 frames, 12x12. */
export const ZZZ = frames(12, 12, 3, (f, set) => {
  const z = (ox: number, oy: number, s: number, c: number): void => {
    for (let i = 0; i < s; i++) {
      set(ox + i, oy, c);
      set(ox + i, oy + s - 1, c);
      set(ox + s - 1 - i, oy + i, c);
    }
  };
  z(1, 8 - f, 3, P.mist);
  if (f >= 1) z(5, 4 - f, 4, P.paper);
  if (f >= 2) z(8, 0, 3, P.mist);
});

/** Shell-piece sparkle, 6 frames, 11x11. */
export const SPARKLE = frames(11, 11, 6, (f, set) => {
  const size = [1, 2, 4, 5, 3, 1][f] ?? 1;
  for (let i = -size; i <= size; i++) {
    set(5 + i, 5, Math.abs(i) === size ? P.sun : P.paper);
    set(5, 5 + i, Math.abs(i) === size ? P.sun : P.paper);
  }
  if (f >= 2 && f <= 4) {
    set(2, 2, P.sun);
    set(8, 8, P.sun);
    set(8, 2, P.paper);
    set(2, 8, P.paper);
  }
});
