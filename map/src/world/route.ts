/**
 * Hermit's route as dotted pixel arcs between consecutive stops. Owner: C.
 *
 * Three friends means the same pairs repeat, so each repeat bows further out
 * and a reverse trip bows to the other side — every hop stays visible.
 */
import { P, type StopDeparture } from '@hermit/ui';

export interface Pt {
  x: number;
  y: number;
}

export interface Segment {
  from: string;
  to: string;
  seq: number;
  departure: StopDeparture;
  points: Pt[];
}

export const ROUTE_COLOR: Record<StopDeparture, number> = {
  graceful: P.sun,
  bedtime: P.cyan,
  abrupt: P.berry,
  manual: P.mist,
  present: P.sun,
};

/** Rasterise a quadratic arc into unique integer pixels, start to end. */
export function arcPixels(a: Pt, b: Pt, bulge: number): Pt[] {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const cx = (a.x + b.x) / 2 + (-dy / len) * bulge;
  const cy = (a.y + b.y) / 2 + (dx / len) * bulge;
  const steps = Math.ceil(len * 1.6) + 2;
  const out: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const x = Math.round(u * u * a.x + 2 * u * t * cx + t * t * b.x);
    const y = Math.round(u * u * a.y + 2 * u * t * cy + t * t * b.y);
    const last = out[out.length - 1];
    if (!last || last.x !== x || last.y !== y) out.push({ x, y });
  }
  return out;
}

export function buildRoute(
  stops: ReadonlyArray<{ seq: number; host: string; departure: StopDeparture }>,
  pos: ReadonlyMap<string, Pt>,
): Segment[] {
  const sorted = [...stops].sort((a, b) => a.seq - b.seq);
  const seen = new Map<string, number>();
  const segs: Segment[] = [];
  for (let i = 0; i + 1 < sorted.length; i++) {
    const s = sorted[i]!;
    const n = sorted[i + 1]!;
    const a = pos.get(s.host);
    const b = pos.get(n.host);
    if (!a || !b || s.host === n.host) continue;
    const key = `${s.host}>${n.host}`;
    const k = seen.get(key) ?? 0;
    seen.set(key, k + 1);
    const len = Math.hypot(b.x - a.x, b.y - a.y);
    const bulge = Math.min(len * (0.14 + 0.1 * k), 18 + 10 * k);
    // shorten so dots stop at the house walls, not inside them
    const pts = arcPixels({ x: a.x, y: a.y - 6 }, { x: b.x, y: b.y - 6 }, bulge);
    segs.push({
      from: s.host,
      to: n.host,
      seq: n.seq,
      departure: s.departure,
      points: trim(pts, 7),
    });
  }
  return segs;
}

function trim(pts: Pt[], n: number): Pt[] {
  return pts.length > 2 * n + 2 ? pts.slice(n, pts.length - n) : pts;
}
