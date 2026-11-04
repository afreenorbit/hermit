/** Draws any PixelGrid crisply at an integer device scale. Owner: C. */
import { useLayoutEffect, useRef, type CSSProperties } from 'react';

import type { PixelGrid } from '../palette';
import { toCanvas, type DrawOptions } from '../shell/adapters';
import { crispScale, useDevicePixelRatio } from './hooks';

export interface PixelCanvasProps {
  grid: PixelGrid;
  /** Target CSS pixels per art pixel; rounded to whole device pixels. */
  scale?: number;
  className?: string;
  style?: CSSProperties;
  label?: string;
  draw?: DrawOptions;
}

export function PixelCanvas({ grid, scale = 4, className, style, label, draw }: PixelCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const dpr = useDevicePixelRatio();
  const { device, css } = crispScale(scale, dpr);

  useLayoutEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    canvas.width = grid.w * device;
    canvas.height = grid.h * device;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    toCanvas(grid, ctx, device, draw);
  }, [grid, device, draw]);

  return (
    <canvas
      ref={ref}
      data-pixel
      className={className}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ width: grid.w * css, height: grid.h * css, imageRendering: 'pixelated', ...style }}
    />
  );
}
