/**
 * "Who did something for whom." Pixel faces on a circle, one pixel line per
 * pair of friends, thicker with more favors, coloured by whoever gave more.
 * Owner: C. plan.md §7.3.
 */
import {
  blankGrid,
  EMPTY,
  hostAccent,
  P,
  PixelCanvas,
  useMediaQuery,
  pixelAvatar,
  type PixelGrid,
} from '@hermit/ui';
import { useMemo, useState } from 'react';

import { nameOf, type Derived } from '../lib/derive';

const W = 84;
const H = 60;

interface Edge {
  a: string;
  b: string;
  ab: number;
  ba: number;
}

function line(g: PixelGrid, x0: number, y0: number, x1: number, y1: number, c: number): void {
  x0 = Math.round(x0);
  y0 = Math.round(y0);
  x1 = Math.round(x1);
  y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0);
  const dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    if (x0 >= 0 && y0 >= 0 && x0 < g.w && y0 < g.h) g.cells[y0 * g.w + x0] = c;
    if (x0 === x1 && y0 === y1) return;
    const e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
}

export function FriendshipWeb({ derived }: { derived: Derived }) {
  // 84 art px wide: 4x is 336px, too wide for a 375px phone once padded.
  const SCALE = useMediaQuery('(max-width: 420px)') ? 3 : 4;
  const [focus, setFocus] = useState<string | null>(null);
  const ids = derived.hostIds;

  const nodes = useMemo(() => {
    const n = ids.length;
    const r = n <= 3 ? 19 : 21;
    return ids.map((id, i) => {
      const a = -Math.PI / 2 + (i / Math.max(1, n)) * Math.PI * 2;
      return {
        id,
        x: Math.round(W / 2 + Math.cos(a) * r * 1.35),
        y: Math.round(H / 2 + 2 + Math.sin(a) * r),
      };
    });
  }, [ids]);

  const edges = useMemo(() => {
    const m = new Map<string, Edge>();
    for (const p of derived.pairs) {
      const [a, b] = p.from < p.to ? [p.from, p.to] : [p.to, p.from];
      const e = m.get(`${a}|${b}`) ?? { a, b, ab: 0, ba: 0 };
      if (p.from === a) e.ab += p.count;
      else e.ba += p.count;
      m.set(`${a}|${b}`, e);
    }
    return [...m.values()];
  }, [derived.pairs]);

  const grid = useMemo(() => {
    const g = blankGrid(W, H);
    const at = new Map(nodes.map((n) => [n.id, n]));
    for (const e of edges) {
      const A = at.get(e.a);
      const B = at.get(e.b);
      if (!A || !B) continue;
      const lit = !focus || focus === e.a || focus === e.b;
      const color = lit ? hostAccent(e.ab >= e.ba ? e.a : e.b) : P.dusk;
      const thick = Math.min(3, e.ab + e.ba);
      const nx = -(B.y - A.y);
      const ny = B.x - A.x;
      const len = Math.hypot(nx, ny) || 1;
      for (let t = 0; t < thick; t++) {
        const off = t - (thick - 1) / 2;
        line(
          g,
          A.x + (nx / len) * off,
          A.y + (ny / len) * off,
          B.x + (nx / len) * off,
          B.y + (ny / len) * off,
          color,
        );
      }
    }
    for (const n of nodes) {
      const face = pixelAvatar(n.id, { background: true });
      for (let y = -1; y <= 8; y++) {
        for (let x = -1; x <= 8; x++) {
          const gx = n.x - 4 + x;
          const gy = n.y - 4 + y;
          if (gx < 0 || gy < 0 || gx >= W || gy >= H) continue;
          const inside = x >= 0 && y >= 0 && x < 8 && y < 8;
          const v = inside ? (face.cells[y * 8 + x] ?? EMPTY) : P.ink;
          g.cells[gy * W + gx] =
            focus && focus !== n.id && inside ? (v === EMPTY ? EMPTY : P.dusk) : v;
        }
      }
    }
    return g;
  }, [nodes, edges, focus]);

  return (
    <figure className="web">
      <div className="web__stage" style={{ width: W * SCALE, height: H * SCALE }}>
        <PixelCanvas grid={grid} scale={SCALE} />
        {nodes.map((n) => {
          const s = derived.perHost[n.id];
          return (
            <button
              key={n.id}
              type="button"
              className="web__node"
              style={{
                left: (n.x - 5) * SCALE,
                top: (n.y - 5) * SCALE,
                width: 10 * SCALE,
                height: 10 * SCALE,
              }}
              onPointerEnter={() => setFocus(n.id)}
              onPointerLeave={() => setFocus(null)}
              onFocus={() => setFocus(n.id)}
              onBlur={() => setFocus(null)}
              aria-label={`${nameOf(derived, n.id)}: gave ${s?.given ?? 0} favors, did ${s?.received ?? 0}`}
            >
              <span className="web__name" style={{ top: n.y > H / 2 ? 10 * SCALE + 2 : -22 }}>
                {nameOf(derived, n.id).toUpperCase()}
              </span>
            </button>
          );
        })}
        {edges.map((e) => {
          const A = nodes.find((n) => n.id === e.a);
          const B = nodes.find((n) => n.id === e.b);
          if (!A || !B) return null;
          const lit = !focus || focus === e.a || focus === e.b;
          return (
            <span
              key={`${e.a}|${e.b}`}
              className={`web__count${lit ? '' : ' is-dim'}`}
              style={{ left: ((A.x + B.x) / 2) * SCALE, top: ((A.y + B.y) / 2) * SCALE }}
              aria-hidden
            >
              ×{e.ab + e.ba}
            </span>
          );
        })}
      </div>
      <figcaption className="web__caption">
        Who did something for whom.{' '}
        {focus
          ? `${nameOf(derived, focus)} gave ${derived.perHost[focus]?.given ?? 0} and did ${derived.perHost[focus]?.received ?? 0}.`
          : edges.length
            ? 'Hover a friend.'
            : 'No favors done yet.'}
      </figcaption>
    </figure>
  );
}
