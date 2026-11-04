/**
 * Equirectangular projection that auto-fits the hosts' bounding box, so the
 * same component draws three areas of Bengaluru and three continents. Owner: C.
 * plan.md §3.2c, §7.2.
 */

export interface View {
  /** Longitude at the left edge of pixel 0. */
  minLon: number;
  /** Latitude at the top edge of pixel 0. */
  maxLat: number;
  /** Degrees per art pixel. */
  deg: number;
  w: number;
  h: number;
}

export type Mode = 'city' | 'wide';

export interface LatLon {
  lat: number;
  lon: number;
}

/** Below this span (degrees) the land mask is meaningless: draw a city instead. */
export const CITY_SPAN_DEG = 3;

export function modeFor(points: readonly LatLon[]): Mode {
  if (points.length === 0) return 'wide';
  const lons = points.map((p) => p.lon);
  const lats = points.map((p) => p.lat);
  const span = Math.max(
    Math.max(...lons) - Math.min(...lons),
    Math.max(...lats) - Math.min(...lats),
  );
  return span < CITY_SPAN_DEG ? 'city' : 'wide';
}

/**
 * Fit every point inside a w×h pixel viewport, leaving `padPx` on each side for
 * house sprites and name labels.
 */
export function fitView(
  points: readonly LatLon[],
  w: number,
  h: number,
  // Room for a house and its name tag: 36px on a desktop map, less on a
  // phone, where a fixed 36px left the friends huddled in the middle.
  padPx = Math.round(Math.max(14, Math.min(36, Math.min(w, h) * 0.22))),
  minSpanDeg = 0.05,
): View {
  if (points.length === 0) return { minLon: -180, maxLat: 90, deg: 360 / Math.max(1, w), w, h };
  const lons = points.map((p) => p.lon);
  const lats = points.map((p) => p.lat);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const lonSpan = Math.max(maxLon - minLon, minSpanDeg);
  const latSpan = Math.max(maxLat - minLat, minSpanDeg);
  const innerW = Math.max(8, w - 2 * padPx);
  const innerH = Math.max(8, h - 2 * padPx - 16); // labels hang below houses
  const deg = Math.max(lonSpan / innerW, latSpan / innerH);
  const cLon = (minLon + maxLon) / 2;
  const cLat = (minLat + maxLat) / 2;
  return { minLon: cLon - (w * deg) / 2, maxLat: cLat + (h * deg) / 2 + 8 * deg, deg, w, h };
}

export function project(v: View, p: LatLon): { x: number; y: number } {
  return { x: (p.lon - v.minLon) / v.deg, y: (v.maxLat - p.lat) / v.deg };
}

export function unproject(v: View, x: number, y: number): LatLon {
  return { lon: v.minLon + x * v.deg, lat: v.maxLat - y * v.deg };
}

/** Zoom by `factor` (>1 zooms in) keeping the pixel (cx, cy) fixed. */
export function zoomView(v: View, factor: number, cx = v.w / 2, cy = v.h / 2): View {
  const anchor = unproject(v, cx, cy);
  const deg = v.deg / factor;
  return { ...v, deg, minLon: anchor.lon - cx * deg, maxLat: anchor.lat + cy * deg };
}

export function panView(v: View, dxPx: number, dyPx: number): View {
  return { ...v, minLon: v.minLon - dxPx * v.deg, maxLat: v.maxLat + dyPx * v.deg };
}

/** Same geography, new pixel size (container resized). */
export function resizeView(v: View, w: number, h: number): View {
  const c = unproject(v, v.w / 2, v.h / 2);
  return { ...v, w, h, minLon: c.lon - (w * v.deg) / 2, maxLat: c.lat + (h * v.deg) / 2 };
}

/**
 * Houses are 16px wide; friends in one neighbourhood would stack. Push any two
 * that overlap apart, deterministically (input order = host_id order).
 */
export function spreadMarkers(
  points: Array<{ x: number; y: number }>,
  minDist = 22,
): Array<{ x: number; y: number }> {
  const out = points.map((p) => ({ ...p }));
  for (let iter = 0; iter < 24; iter++) {
    let moved = false;
    for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const a = out[i]!;
        const b = out[j]!;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let d = Math.hypot(dx, dy);
        if (d >= minDist) continue;
        if (d < 0.01) {
          // identical spot: fan out around a circle by index
          const ang = (j / out.length) * Math.PI * 2;
          dx = Math.cos(ang);
          dy = Math.sin(ang);
          d = 1;
        }
        const push = (minDist - d) / 2;
        a.x -= (dx / d) * push;
        a.y -= (dy / d) * push;
        b.x += (dx / d) * push;
        b.y += (dy / d) * push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return out.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) }));
}

/** Kilometres per pixel at a latitude — for the city scale bar. */
export function kmPerPx(v: View): number {
  const lat = v.maxLat - (v.h / 2) * v.deg;
  return v.deg * 111.32 * Math.cos((lat * Math.PI) / 180);
}
