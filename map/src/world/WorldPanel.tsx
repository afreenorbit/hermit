/**
 * The world: pastel pixel ground, dotted route, houses with pixel faces, and
 * Tilli waddling along the latest hop. Owner: C. plan.md §7.2.
 */
import {
  BrainBadge,
  crispScale,
  formatDay,
  formatDwell,
  HOUSE,
  HOUSE_WINDOW,
  P,
  pixelAvatar,
  PixelButton,
  RGB,
  Tilli,
  toImageData,
  useDevicePixelRatio,
  useFrame,
} from '@hermit/ui';
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent } from 'react';

import { nameOf, type Derived } from '../lib/derive';
import { drawGround, shimmer } from './drawWorld';
import {
  fitView,
  kmPerPx,
  modeFor,
  panView,
  project,
  resizeView,
  spreadMarkers,
  zoomView,
  type View,
} from './projection';
import { buildRoute, ROUTE_COLOR, type Pt } from './route';
import { loadLandMask, type LandMask } from './worldGrid';

interface Props {
  derived: Derived;
  stops: Parameters<typeof buildRoute>[0];
  dark: boolean;
  reduced: boolean;
  currentHost: string | null;
  selectedHost: string | null;
  onSelectHost: (host: string | null) => void;
}

const MAX_ZOOM = 16;

function putPx(img: ImageData, x: number, y: number, c: number): void {
  if (x < 0 || y < 0 || x >= img.width || y >= img.height) return;
  const rgb = RGB[c]!;
  const o = (y * img.width + x) * 4;
  img.data[o] = rgb[0];
  img.data[o + 1] = rgb[1];
  img.data[o + 2] = rgb[2];
  img.data[o + 3] = 255;
}

export function WorldPanel({
  derived,
  stops,
  dark,
  reduced,
  currentHost,
  selectedHost,
  onSelectHost,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [box, setBox] = useState({ w: 640, h: 440 });
  const dpr = useDevicePixelRatio();
  const { css } = crispScale(box.w < 640 ? 3 : 4, dpr);
  const W = Math.max(40, Math.floor(box.w / css));
  const H = Math.max(40, Math.floor(box.h / css));

  const hosts = useMemo(
    () => [...derived.hosts.values()].sort((a, b) => a.host_id.localeCompare(b.host_id)),
    [derived],
  );
  const mode = useMemo(() => modeFor(hosts), [hosts]);
  const fit = useMemo(() => fitView(hosts, W, H), [hosts, W, H]);
  const [view, setView] = useState<View>(fit);
  const [zoom, setZoom] = useState(1);
  /** True until the user pans or zooms; resizes then re-fit instead of keeping the view. */
  const [fitted, setFitted] = useState(true);
  const [mask, setMask] = useState<LandMask | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const tick = useFrame(6, !reduced);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setBox({ w: Math.floor(width), h: Math.floor(height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Re-fit when the data changes; keep the user's view across a resize.
  useEffect(() => {
    if (fitted) setView(fit);
    else setView((v) => resizeView(v, W, H));
  }, [fit, fitted, W, H]);

  useEffect(() => {
    if (mode !== 'wide') return;
    let live = true;
    void loadLandMask().then((m) => live && setMask(m));
    return () => {
      live = false;
    };
  }, [mode]);

  const ground = useMemo(() => drawGround(view, mode, dark, mask), [view, mode, dark, mask]);

  const pos = useMemo(() => {
    const raw = hosts.map((h) => project(view, h));
    const spread = spreadMarkers(raw, 24);
    return new Map<string, Pt>(hosts.map((h, i) => [h.host_id, spread[i]!]));
  }, [hosts, view]);

  const route = useMemo(() => buildRoute(stops, pos), [stops, pos]);
  const avatars = useMemo(
    () => new Map(hosts.map((h) => [h.host_id, pixelAvatar(h.host_id, { background: true })])),
    [hosts],
  );

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || ground.data.width !== view.w) return;
    canvas.width = view.w;
    canvas.height = view.h;
    const img = new ImageData(new Uint8ClampedArray(ground.data.data), view.w, view.h);
    if (!reduced) shimmer(img, ground, tick, dark, mode);

    // route: dots with a 1px ink shadow so they read on any ground
    const focus = selectedHost ?? hover;
    route.forEach((seg) => {
      const dim = focus && seg.from !== focus && seg.to !== focus;
      const color = dim ? (dark ? P.night : P.dusk) : ROUTE_COLOR[seg.departure];
      seg.points.forEach((p, i) => {
        if (i % 2) return;
        putPx(img, p.x + 1, p.y + 1, P.ink);
        putPx(img, p.x, p.y, color);
      });
    });

    // houses
    hosts.forEach((h) => {
      const p = pos.get(h.host_id);
      if (!p) return;
      const ox = p.x - 8;
      const oy = p.y - 16;
      const isNow = h.host_id === currentHost;
      if (isNow && (reduced || tick % 2 === 0)) {
        for (let x = -1; x <= 16; x++) {
          putPx(img, ox + x, oy - 1, P.sun);
          putPx(img, ox + x, oy + 16, P.sun);
        }
        for (let y = -1; y <= 16; y++) {
          putPx(img, ox - 1, oy + y, P.sun);
          putPx(img, ox + 16, oy + y, P.sun);
        }
      }
      toImageData(HOUSE, img, ox, oy);
      const av = avatars.get(h.host_id);
      if (av) toImageData(av, img, ox + HOUSE_WINDOW.x, oy + HOUSE_WINDOW.y);
    });

    ctx.putImageData(img, 0, 0);
  }, [
    ground,
    route,
    hosts,
    pos,
    avatars,
    tick,
    reduced,
    dark,
    mode,
    currentHost,
    view,
    selectedHost,
    hover,
  ]);

  // Tilli walks the latest hop, then rests at the door.
  const walker = useMemo(() => {
    const last = route[route.length - 1];
    if (!last || last.points.length < 2) return null;
    const n = last.points.length;
    const step = reduced ? n - 1 : Math.min(n - 1, tick % (n + 18));
    const p = last.points[step]!;
    return {
      x: p.x,
      y: p.y,
      walking: step < n - 1,
      left: last.points[n - 1]!.x < last.points[0]!.x,
    };
  }, [route, tick, reduced]);

  // --- interaction -------------------------------------------------------
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const zoomBy = (f: number, cx?: number, cy?: number): void => {
    const next = Math.min(MAX_ZOOM, Math.max(1, zoom * f));
    if (next === zoom) return;
    setZoom(next);
    setFitted(next === 1);
    setView((v) => (next === 1 ? fit : zoomView(v, next / zoom, cx, cy)));
  };
  const reset = (): void => {
    setZoom(1);
    setFitted(true);
    setView(fit);
  };
  const onDown = (e: PointerEvent<HTMLCanvasElement>): void => {
    drag.current = { x: e.clientX, y: e.clientY, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: PointerEvent<HTMLCanvasElement>): void => {
    const d = drag.current;
    if (!d) return;
    const dx = (e.clientX - d.x) / css;
    const dy = (e.clientY - d.y) / css;
    if (Math.abs(dx) + Math.abs(dy) < 1) return;
    d.moved = true;
    d.x = e.clientX;
    d.y = e.clientY;
    setView((v) => panView(v, Math.round(dx), Math.round(dy)));
    setFitted(false);
  };
  const onUp = (): void => {
    if (drag.current && !drag.current.moved) onSelectHost(null);
    drag.current = null;
  };

  const km = kmPerPx(view);
  const bar = useMemo(() => {
    const target = km * 40;
    const steps = [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
    const nice = [...steps].reverse().find((n) => n <= target) ?? 0.2;
    return { km: nice, px: Math.round(nice / km) };
  }, [km]);

  const city = hosts[0]?.city;
  const label = mode === 'city' ? `CITY VIEW · ${hosts.length} AREAS` : 'WORLD VIEW';

  return (
    <div className="world">
      <div
        ref={wrapRef}
        className="world__stage hm-focusable"
        tabIndex={0}
        aria-label={`Map of Hermit's route. ${label}. Arrow keys pan, plus and minus zoom, F fits.`}
        onKeyDown={(e) => {
          const k = e.key;
          if (k === '+' || k === '=') zoomBy(2);
          else if (k === '-' || k === '_') zoomBy(0.5);
          else if (k === 'f' || k === 'F' || k === '0') reset();
          else if (k.startsWith('Arrow')) {
            const d = 12;
            setView((v) =>
              panView(
                v,
                k === 'ArrowLeft' ? d : k === 'ArrowRight' ? -d : 0,
                k === 'ArrowUp' ? d : k === 'ArrowDown' ? -d : 0,
              ),
            );
            setFitted(false);
          } else return;
          e.preventDefault();
        }}
        onWheel={(e) => {
          if (!e.ctrlKey && !e.metaKey) return;
          e.preventDefault();
          const rect = e.currentTarget.getBoundingClientRect();
          zoomBy(
            e.deltaY < 0 ? 2 : 0.5,
            (e.clientX - rect.left) / css,
            (e.clientY - rect.top) / css,
          );
        }}
      >
        <canvas
          ref={canvasRef}
          data-pixel
          className="world__canvas"
          aria-hidden
          style={{ width: view.w * css, height: view.h * css }}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onDoubleClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            zoomBy(2, (e.clientX - rect.left) / css, (e.clientY - rect.top) / css);
          }}
        />

        {hosts.map((h) => {
          const p = pos.get(h.host_id);
          if (!p) return null;
          const stats = derived.perHost[h.host_id];
          const on = selectedHost === h.host_id;
          const left = (p.x - 8) * css;
          const top = (p.y - 16) * css;
          if (left < -64 || top < -64 || left > view.w * css + 64 || top > view.h * css + 64)
            return null;
          return (
            <div key={h.host_id} className="world__marker" style={{ left, top, width: 16 * css }}>
              <button
                type="button"
                className={`world__house${on ? ' is-on' : ''}`}
                style={{ width: 16 * css, height: 16 * css }}
                aria-pressed={on}
                aria-label={`${h.display_name}, ${h.city}. Hosted ${stats?.hosted ?? 0} times. ${on ? 'Showing only their stops.' : 'Show only their stops.'}`}
                onClick={() => onSelectHost(on ? null : h.host_id)}
                onPointerEnter={() => setHover(h.host_id)}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover(h.host_id)}
                onBlur={() => setHover(null)}
              />
              <span className={`world__name${h.host_id === currentHost ? ' is-now' : ''}`}>
                {h.host_id === currentHost && <span className="world__here">HERE</span>}
                {h.display_name.toUpperCase()}
              </span>
              {hover === h.host_id && stats && (
                <div className="hm-tip world__tip" role="tooltip" style={{ left: 8 * css, top: 0 }}>
                  <strong>{h.display_name}</strong>
                  <div className="world__tipline">{h.city}</div>
                  <div className="world__tipbadge">
                    <BrainBadge provider={h.brain_provider} />
                  </div>
                  <div className="world__tipline">
                    Hosted {stats.hosted}× · {formatDwell(stats.dwellS)} in all
                  </div>
                  <div className="world__tipline">
                    Favors given {stats.given} · done {stats.received}
                  </div>
                  {stats.lastHosted && (
                    <div className="world__tipline">Last visit {formatDay(stats.lastHosted)}</div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {walker && (
          <div
            className="world__walker"
            style={{ left: walker.x * css, top: walker.y * css }}
            aria-hidden
          >
            <Tilli
              mood={walker.walking ? 'walk' : 'happy'}
              size={css >= 4 ? 52 : 42}
              flip={walker.left}
              marks={false}
              label=""
            />
          </div>
        )}

        <span className="world__mode">{mode === 'city' && city ? `${label}` : label}</span>

        <div className="world__controls">
          <PixelButton
            variant="ghost"
            size="sm"
            icon="plus"
            label="Zoom in"
            onClick={() => zoomBy(2)}
            disabled={zoom >= MAX_ZOOM}
          />
          <PixelButton
            variant="ghost"
            size="sm"
            icon="minus"
            label="Zoom out"
            onClick={() => zoomBy(0.5)}
            disabled={zoom <= 1}
          />
          <PixelButton variant="ghost" size="sm" icon="fit" label="Fit all friends" onClick={reset}>
            FIT
          </PixelButton>
        </div>

        <div className="world__scale" aria-hidden>
          <span className="world__bar" style={{ width: bar.px * css }} />
          <span>{bar.km >= 1 ? `${bar.km} KM` : `${bar.km * 1000} M`}</span>
        </div>
      </div>

      <ul className="world__legend" aria-label="Route colours">
        {(['graceful', 'bedtime', 'abrupt'] as const).map((d) => (
          <li key={d}>
            <span className={`world__dot world__dot--${d}`} aria-hidden />
            {d === 'graceful'
              ? 'left gracefully'
              : d === 'bedtime'
                ? 'left at bedtime'
                : 'lid slammed'}
          </li>
        ))}
        <li>
          <span className="world__dot world__dot--hermit" aria-hidden />
          Tilli’s latest hop
        </li>
      </ul>

      <ul className="hm-sr">
        {hosts.map((h) => (
          <li key={h.host_id}>
            {nameOf(derived, h.host_id)} lives in {h.city}; hosted Hermit{' '}
            {derived.perHost[h.host_id]?.hosted ?? 0} times.
          </li>
        ))}
      </ul>
    </div>
  );
}
