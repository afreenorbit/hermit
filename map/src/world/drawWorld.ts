/**
 * Paints the pixel world into an RGBA buffer, one art pixel per buffer pixel.
 * Owner: C. plan.md §7.2.
 *
 * Two grounds, chosen by the hosts' spread:
 *   city  three areas of one city — the land mask is all land at this scale, so
 *         we draw an abstract neighbourhood instead: grass, lakes, roads.
 *   wide  friends across the planet — the baked land/sea mask, with coasts.
 * Everything is a function of (lat, lon), so pan and zoom stay consistent.
 */
import { hash2, P, RGB } from '@hermit/ui';

import type { LandMask } from './worldGrid';
import { unproject, type Mode, type View } from './projection';

export interface Ground {
  data: ImageData;
  /** Pixel offsets of water, for the shimmer overlay. */
  water: Int32Array;
}

interface Palette {
  grass: number[];
  tuft: number;
  tree: number;
  road: number;
  water: number;
  waterHi: number;
  shore: number;
  sea: number;
  seaHi: number;
  land: number[];
  coast: number;
  grid: number;
}

const LIGHT: Palette = {
  grass: [P.leaf, P.leaf, P.leaf, P.teal],
  tuft: P.lime,
  tree: P.teal,
  road: P.mist,
  water: P.sea,
  waterHi: P.cyan,
  shore: P.sun,
  sea: P.mist,
  seaHi: P.paper,
  land: [P.leaf, P.lime],
  coast: P.teal,
  grid: P.dusk,
};

const DARK: Palette = {
  grass: [P.teal, P.teal, P.teal, P.navy],
  tuft: P.leaf,
  tree: P.navy,
  road: P.dusk,
  water: P.blue,
  waterHi: P.sea,
  shore: P.dusk,
  sea: P.navy,
  seaHi: P.blue,
  land: [P.teal, P.leaf],
  coast: P.night,
  grid: P.night,
};

/** Smooth value noise in [0, 1). */
function noise(x: number, y: number, seed: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const r = (a: number, b: number): number => (hash2(a, b, seed) & 0xffff) / 0x10000;
  const sx = xf * xf * (3 - 2 * xf);
  const sy = yf * yf * (3 - 2 * yf);
  const top = r(xi, yi) + (r(xi + 1, yi) - r(xi, yi)) * sx;
  const bot = r(xi, yi + 1) + (r(xi + 1, yi + 1) - r(xi, yi + 1)) * sx;
  return top + (bot - top) * sy;
}

function put(img: ImageData, i: number, c: number): void {
  const rgb = RGB[c]!;
  const o = i * 4;
  img.data[o] = rgb[0];
  img.data[o + 1] = rgb[1];
  img.data[o + 2] = rgb[2];
  img.data[o + 3] = 255;
}

/** World units for the city ground: ~160 m each. */
const CITY_UNIT_DEG = 0.0015;

export function drawGround(v: View, mode: Mode, dark: boolean, mask: LandMask | null): Ground {
  const img = new ImageData(v.w, v.h);
  const pal = dark ? DARK : LIGHT;
  const water: number[] = [];
  if (mode === 'city') drawCity(img, v, pal, water);
  else drawWide(img, v, pal, mask, water);
  return { data: img, water: Int32Array.from(water) };
}

function drawCity(img: ImageData, v: View, pal: Palette, water: number[]): void {
  const unitPerPx = v.deg / CITY_UNIT_DEG;
  const roadEvery = 40; // units between roads
  for (let y = 0; y < v.h; y++) {
    for (let x = 0; x < v.w; x++) {
      const i = y * v.w + x;
      const p = unproject(v, x + 0.5, y + 0.5);
      const gx = p.lon / CITY_UNIT_DEG;
      const gy = p.lat / CITY_UNIT_DEG;

      // lakes — Bengaluru has a lot of them
      const lake = noise(gx / 18, gy / 18, 11) * 0.7 + noise(gx / 6, gy / 6, 12) * 0.3;
      if (lake > 0.76) {
        put(img, i, pal.water);
        water.push(i);
        continue;
      }
      if (lake > 0.735) {
        put(img, i, pal.shore);
        continue;
      }

      // roads: exactly 1px wide at any zoom — a road crosses this pixel
      const wx = gx + noise(gy / 40, 0, 21) * 10;
      const wy = gy + noise(gx / 40, 0, 22) * 10;
      const half = unitPerPx / 2;
      const crossX = Math.floor((wx - half) / roadEvery) !== Math.floor((wx + half) / roadEvery);
      const crossY = Math.floor((wy - half) / roadEvery) !== Math.floor((wy + half) / roadEvery);
      if (crossX || crossY) {
        put(img, i, pal.road);
        continue;
      }

      // grass with tufts and the odd tree
      const cell = hash2(Math.floor(gx), Math.floor(gy), 5);
      if (cell % 53 === 0) {
        put(img, i, pal.tree);
        continue;
      }
      if (cell % 37 === 0) {
        put(img, i, pal.tuft);
        continue;
      }
      const shade = noise(gx / 9, gy / 9, 3);
      const g = pal.grass[(x + y) % 2 === 0 && shade > 0.68 ? 3 : 0]!;
      put(img, i, g);
    }
  }
}

function drawWide(
  img: ImageData,
  v: View,
  pal: Palette,
  mask: LandMask | null,
  water: number[],
): void {
  const land = new Uint8Array(v.w * v.h);
  for (let y = 0; y < v.h; y++) {
    for (let x = 0; x < v.w; x++) {
      const p = unproject(v, x + 0.5, y + 0.5);
      const lat = Math.max(-89.9, Math.min(89.9, p.lat));
      const lon = ((((p.lon + 180) % 360) + 360) % 360) - 180;
      // Without the mask (offline), fall back to noise continents.
      const isLand = mask ? mask.isLand(lat, lon) : noise(lon / 25, lat / 25, 7) > 0.58;
      land[y * v.w + x] = isLand ? 1 : 0;
    }
  }
  const gridDeg = v.deg * v.w > 120 ? 30 : v.deg * v.w > 40 ? 10 : 5;
  for (let y = 0; y < v.h; y++) {
    for (let x = 0; x < v.w; x++) {
      const i = y * v.w + x;
      if (land[i]) {
        const coast =
          (x > 0 && !land[i - 1]) ||
          (x < v.w - 1 && !land[i + 1]) ||
          (y > 0 && !land[i - v.w]) ||
          (y < v.h - 1 && !land[i + v.w]);
        put(
          img,
          i,
          coast ? pal.coast : pal.land[(x + y) % 2 === 0 && hash2(x, y, 9) % 3 === 0 ? 1 : 0]!,
        );
        continue;
      }
      // faint graticule on the sea, every other pixel
      const p = unproject(v, x, y);
      const pr = unproject(v, x + 1, y + 1);
      const onMeridian = Math.floor(p.lon / gridDeg) !== Math.floor(pr.lon / gridDeg);
      const onParallel = Math.floor(p.lat / gridDeg) !== Math.floor(pr.lat / gridDeg);
      if ((onMeridian || onParallel) && (x + y) % 2 === 0) put(img, i, pal.grid);
      else put(img, i, pal.sea);
      water.push(i);
    }
  }
}

/** Two-frame shimmer on a sparse, stable subset of water pixels. */
export function shimmer(
  target: ImageData,
  ground: Ground,
  tick: number,
  dark: boolean,
  mode: Mode,
): void {
  const pal = dark ? DARK : LIGHT;
  const hi = mode === 'wide' ? pal.seaHi : pal.waterHi;
  for (let k = 0; k < ground.water.length; k++) {
    const i = ground.water[k]!;
    const h = hash2(i, 0, 77);
    if (h % 61 === 0 && ((h >> 8) + tick) % 2 === 0) put(target, i, hi);
  }
}
