/**
 * The pixel shell, with hover and keyboard focus per piece. Owner: C.
 *
 * Hovering a piece dims the others and calls `onActive`, so a page can show a
 * tooltip or scroll the matching quest card into view. Arrow keys walk the
 * pieces in journey order, which is the accessible path through the canvas.
 */
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from 'react';

import { renderShellGrid, type ShellGrid, type ShellPieceInput } from '../shell/renderShellGrid';
import { toCanvas } from '../shell/adapters';
import { crispScale, useDevicePixelRatio } from './hooks';

export interface ShellViewProps {
  pieces: readonly ShellPieceInput[];
  size?: 24 | 48;
  scale?: number;
  /** Controlled active piece (index into pieces). */
  active?: number | null;
  onActive?: (index: number | null) => void;
  /** Click or Enter on a piece. */
  onPick?: (index: number) => void;
  /** Accessible description of a piece, read when it is focused. */
  describe?: (index: number) => string;
  /** Floating content for the active piece. */
  tooltip?: (index: number) => ReactNode;
  label?: string;
  empty?: ReactNode;
}

export function ShellView({
  pieces,
  size = 48,
  scale = 6,
  active: controlled,
  onActive,
  onPick,
  describe,
  tooltip,
  label = 'Hermit’s shell',
  empty,
}: ShellViewProps) {
  const grid: ShellGrid = useMemo(() => renderShellGrid(pieces, { size }), [pieces, size]);
  const ref = useRef<HTMLCanvasElement>(null);
  const dpr = useDevicePixelRatio();
  const { device, css } = crispScale(scale, dpr);
  const [own, setOwn] = useState<number | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const active = controlled !== undefined ? controlled : own;

  const set = (i: number | null): void => {
    setOwn(i);
    onActive?.(i);
  };

  useLayoutEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    canvas.width = grid.w * device;
    canvas.height = grid.h * device;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    toCanvas(grid, ctx, device, {
      alpha: active == null ? undefined : (i) => (grid.owners[i] === active ? 1 : 0.28),
    });
  }, [grid, device, active]);

  // Anchor the tooltip on the active piece's centre of mass.
  useEffect(() => {
    if (active == null) return setPos(null);
    let sx = 0;
    let sy = 0;
    let n = 0;
    grid.owners.forEach((o, i) => {
      if (o !== active) return;
      sx += i % grid.w;
      sy += Math.floor(i / grid.w);
      n++;
    });
    setPos(n ? { x: ((sx / n + 0.5) * css) | 0, y: ((sy / n) * css) | 0 } : null);
  }, [active, grid, css]);

  if (pieces.length === 0 && empty) return <>{empty}</>;

  const pick = (e: PointerEvent<HTMLCanvasElement>): void => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * grid.w);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * grid.h);
    const o = grid.owners[y * grid.w + x] ?? -1;
    set(o >= 0 ? o : null);
  };

  return (
    <div className="hm-shellview" style={{ width: grid.w * css }}>
      <canvas
        ref={ref}
        data-pixel
        tabIndex={pieces.length ? 0 : -1}
        role="img"
        aria-label={`${label}: ${pieces.length} piece${pieces.length === 1 ? '' : 's'}. Use arrow keys to inspect each piece.`}
        aria-describedby={active != null ? 'hm-shell-live' : undefined}
        style={{ width: grid.w * css, height: grid.h * css }}
        onPointerMove={pick}
        onPointerDown={pick}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = Math.floor(((e.clientX - rect.left) / rect.width) * grid.w);
          const y = Math.floor(((e.clientY - rect.top) / rect.height) * grid.h);
          const o = grid.owners[y * grid.w + x] ?? -1;
          if (o >= 0) onPick?.(o);
        }}
        onPointerLeave={() => set(null)}
        onBlur={() => set(null)}
        onKeyDown={(e) => {
          if (!pieces.length) return;
          if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            set(active == null ? 0 : Math.min(pieces.length - 1, active + 1));
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            set(active == null ? pieces.length - 1 : Math.max(0, active - 1));
          } else if (e.key === 'Enter' && active != null) {
            e.preventDefault();
            onPick?.(active);
          } else if (e.key === 'Escape') {
            set(null);
          }
        }}
      />
      <span id="hm-shell-live" className="hm-sr" aria-live="polite">
        {active != null && describe ? describe(active) : ''}
      </span>
      {active != null && pos && tooltip && (
        <div
          className="hm-tip hm-shellview__tip"
          style={{ left: pos.x, top: pos.y }}
          role="tooltip"
        >
          {tooltip(active)}
        </div>
      )}
    </div>
  );
}
