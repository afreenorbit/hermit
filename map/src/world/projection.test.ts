import { describe, expect, it } from 'vitest';

import {
  fitView,
  kmPerPx,
  modeFor,
  project,
  spreadMarkers,
  unproject,
  zoomView,
} from './projection';
import { arcPixels, buildRoute } from './route';

const BLR = [
  { lat: 12.9719, lon: 77.6412 },
  { lat: 12.9166, lon: 77.4826 },
  { lat: 12.9352, lon: 77.6245 },
];
const WIDE = [
  { lat: 12.97, lon: 77.59 },
  { lat: 52.52, lon: 13.4 },
  { lat: 43.65, lon: -79.38 },
];

describe('projection auto-fit', () => {
  it('draws a city for one city and a planet for three continents', () => {
    expect(modeFor(BLR)).toBe('city');
    expect(modeFor(WIDE)).toBe('wide');
  });

  it.each([
    ['city', BLR],
    ['wide', WIDE],
  ])('keeps every %s host inside the padded viewport', (_, pts) => {
    const v = fitView(pts, 200, 120, 30);
    for (const p of pts) {
      const { x, y } = project(v, p);
      expect(x).toBeGreaterThanOrEqual(29);
      expect(x).toBeLessThanOrEqual(171);
      expect(y).toBeGreaterThanOrEqual(10);
      expect(y).toBeLessThanOrEqual(110);
    }
  });

  it('round-trips project/unproject and zooms around a fixed point', () => {
    const v = fitView(WIDE, 200, 120);
    const back = unproject(v, project(v, WIDE[1]!).x, project(v, WIDE[1]!).y);
    expect(back.lat).toBeCloseTo(52.52, 6);
    const z = zoomView(v, 2, 50, 40);
    expect(unproject(z, 50, 40).lon).toBeCloseTo(unproject(v, 50, 40).lon, 6);
    expect(z.deg).toBeCloseTo(v.deg / 2, 9);
  });

  it('gives a city-scale km per pixel', () => {
    const v = fitView(BLR, 200, 120);
    expect(kmPerPx(v)).toBeGreaterThan(0.01);
    expect(kmPerPx(v)).toBeLessThan(1);
  });

  it('pushes overlapping houses apart deterministically', () => {
    const out = spreadMarkers([
      { x: 50, y: 50 },
      { x: 50, y: 50 },
      { x: 52, y: 50 },
    ]);
    expect(out).toEqual(
      spreadMarkers([
        { x: 50, y: 50 },
        { x: 50, y: 50 },
        { x: 52, y: 50 },
      ]),
    );
    for (let i = 0; i < out.length; i++)
      for (let j = i + 1; j < out.length; j++)
        expect(Math.hypot(out[i]!.x - out[j]!.x, out[i]!.y - out[j]!.y)).toBeGreaterThanOrEqual(20);
  });
});

describe('route', () => {
  it('rasterises a connected arc from start to end', () => {
    const pts = arcPixels({ x: 0, y: 0 }, { x: 40, y: 10 }, 8);
    expect(pts[0]).toEqual({ x: 0, y: 0 });
    expect(pts[pts.length - 1]).toEqual({ x: 40, y: 10 });
    for (let i = 1; i < pts.length; i++) {
      expect(Math.abs(pts[i]!.x - pts[i - 1]!.x)).toBeLessThanOrEqual(1);
      expect(Math.abs(pts[i]!.y - pts[i - 1]!.y)).toBeLessThanOrEqual(1);
    }
  });

  it('bows repeat trips further out so every hop stays visible', () => {
    const pos = new Map([
      ['a', { x: 20, y: 60 }],
      ['b', { x: 140, y: 60 }],
    ]);
    const segs = buildRoute(
      [
        { seq: 1, host: 'a', departure: 'graceful' },
        { seq: 2, host: 'b', departure: 'graceful' },
        { seq: 3, host: 'a', departure: 'bedtime' },
        { seq: 4, host: 'b', departure: 'present' },
      ],
      pos,
    );
    expect(segs).toHaveLength(3);
    // signed bow of each hop at its middle, relative to the straight line (y = 54)
    const bow = (i: number) => {
      const pts = segs[i]!.points;
      return pts[Math.floor(pts.length / 2)]!.y - 54;
    };
    // a→b bows one way, b→a the other, the second a→b further than the first
    expect(Math.sign(bow(0))).toBe(-Math.sign(bow(1)));
    expect(Math.sign(bow(2))).toBe(Math.sign(bow(0)));
    expect(Math.abs(bow(2))).toBeGreaterThan(Math.abs(bow(0)));
  });
});
