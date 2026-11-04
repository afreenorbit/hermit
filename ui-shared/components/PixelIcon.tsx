/** Pixel icons as crisp inline SVG. `#` cells take the text colour. Owner: C. */
import { useMemo } from 'react';

import { SWEETIE16, type PixelGrid } from '../palette';
import { toRuns } from '../shell/adapters';
import { CURRENT, ICONS, type IconName } from '../sprite/glyphs';

export interface PixelGridSvgProps {
  grid: PixelGrid;
  /** CSS pixels per art pixel. */
  scale?: number;
  label?: string;
  className?: string;
}

export function PixelGridSvg({ grid, scale = 2, label, className }: PixelGridSvgProps) {
  const runs = useMemo(() => toRuns(grid), [grid]);
  return (
    <svg
      className={className}
      width={grid.w * scale}
      height={grid.h * scale}
      viewBox={`0 0 ${grid.w} ${grid.h}`}
      shapeRendering="crispEdges"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {runs.map((r) => (
        <rect
          key={`${r.x}-${r.y}`}
          x={r.x}
          y={r.y}
          width={r.w}
          height={1}
          fill={r.c === CURRENT ? 'currentColor' : SWEETIE16[r.c]}
        />
      ))}
    </svg>
  );
}

export function PixelIcon({
  name,
  scale = 2,
  label,
  className,
}: {
  name: IconName;
  scale?: number;
  label?: string;
  className?: string;
}) {
  return (
    <PixelGridSvg
      grid={ICONS[name]}
      scale={scale}
      label={label}
      className={`hm-icon ${className ?? ''}`}
    />
  );
}
