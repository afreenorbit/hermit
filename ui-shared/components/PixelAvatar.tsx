/** 8x8 symmetric face generated from host_id. Owner: C. */
import { useMemo } from 'react';

import { pixelAvatar } from '../avatar/pixelAvatar';
import { PixelGridSvg } from './PixelIcon';

export function PixelAvatar({
  hostId,
  scale = 4,
  name,
  framed = true,
}: {
  hostId: string;
  scale?: number;
  name?: string;
  framed?: boolean;
}) {
  const grid = useMemo(() => pixelAvatar(hostId, { background: framed }), [hostId, framed]);
  return (
    <span className={`hm-avatar${framed ? ' hm-avatar--framed' : ''}`}>
      <PixelGridSvg grid={grid} scale={scale} label={name ? `${name}'s pixel face` : undefined} />
    </span>
  );
}
