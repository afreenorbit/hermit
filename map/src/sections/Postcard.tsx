/**
 * "MAKE A POSTCARD": a 1200×630 PNG of the shell, Hermit and the top stats,
 * for the README header and the #HowISwitch post. Owner: C. plan.md §7.6.
 *
 * Drawn straight onto one canvas instead of screenshotting the DOM — every
 * pixel lands on an integer grid, so the PNG is as crisp as the page.
 */
import {
  composeFrame,
  formatDay,
  formatHandoffMs,
  PixelButton,
  renderShellGrid,
  sound,
  SWEETIE16,
  toCanvas,
  ANIMATIONS,
} from '@hermit/ui';
import type { JourneyT } from '@hermit/ui/contracts';
import { useState } from 'react';

import type { Derived } from '../lib/derive';

const C = (i: number): string => SWEETIE16[i] ?? '#000';
const INK = C(0);
const EMBER = C(3);
const SUN = C(4);
const LIME = C(5);
const PAPER = C(12);
const MIST = C(13);
const DUSK = C(14);
const NIGHT = C(15);

function box(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  face: string,
  edge: string,
): void {
  ctx.fillStyle = edge;
  ctx.fillRect(x, y - 4, w, h + 8);
  ctx.fillRect(x - 4, y, w + 8, h);
  ctx.fillStyle = face;
  ctx.fillRect(x, y, w, h);
}

export async function drawPostcard(
  journey: JourneyT,
  d: Derived,
  sample: boolean,
): Promise<HTMLCanvasElement> {
  const W = 1200;
  const H = 630;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  try {
    await Promise.all([
      document.fonts.load('48px "Press Start 2P"'),
      document.fonts.load('600 24px "Pixelify Sans"'),
    ]);
  } catch {
    /* fall back to monospace */
  }

  // ground: ink with a night pixel dot grid, stepped frame
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = NIGHT;
  for (let y = 12; y < H; y += 24) for (let x = 12; x < W; x += 24) ctx.fillRect(x, y, 4, 4);
  ctx.fillStyle = SUN;
  ctx.fillRect(24, 24, W - 48, 4);
  ctx.fillRect(24, H - 28, W - 48, 4);
  ctx.fillRect(24, 28, 4, H - 56);
  ctx.fillRect(W - 28, 28, 4, H - 56);

  // the shell, big, with Hermit wearing it
  const shell = renderShellGrid(d.pieces, { size: 48 });
  box(ctx, 72, 88, 456, 456, NIGHT, INK);
  ctx.save();
  ctx.translate(84, 100);
  toCanvas(shell, ctx, 9);
  ctx.restore();
  const small = renderShellGrid(d.pieces, { size: 24 });
  const hermit = composeFrame(
    ANIMATIONS.happy.poses[0]!,
    small.cells.some((c) => c >= 0) ? small : null,
  );
  ctx.save();
  ctx.translate(400, 372);
  toCanvas(hermit, ctx, 6);
  ctx.restore();

  // title
  const pf = (size: number, weight = 600): string =>
    `${weight} ${size}px "Pixelify Sans", ui-sans-serif, sans-serif`;
  ctx.textBaseline = 'alphabetic';
  ctx.font = '56px "Press Start 2P", monospace';
  ctx.fillStyle = INK;
  ctx.fillText('HERMIT', 612, 168);
  ctx.fillStyle = SUN;
  ctx.fillText('HERMIT', 608, 164);

  ctx.font = pf(30);
  ctx.fillStyle = PAPER;
  const friends = d.hostIds.length;
  ctx.fillText(
    `visited ${friends} friend${friends === 1 ? '' : 's'} in ${d.places} place${d.places === 1 ? '' : 's'}`,
    608,
    224,
  );
  ctx.font = pf(22, 500);
  ctx.fillStyle = MIST;
  if (d.range) ctx.fillText(`${formatDay(d.range.from)} → ${formatDay(d.range.to)}`, 608, 260);

  // three stats
  const stats: Array<[string, string, string]> = [
    ['FAVORS DONE', String(journey.stats.favors_done ?? d.favorsDone), EMBER],
    ['SHELL PIECES', String(d.pieces.length), SUN],
    ['MEDIAN HANDOFF', formatHandoffMs(journey.stats.median_handoff_ms), LIME],
  ];
  stats.forEach(([label, value, color], i) => {
    const x = 612 + i * 180;
    box(ctx, x, 304, 160, 128, NIGHT, INK);
    ctx.font = pf(16);
    ctx.fillStyle = MIST;
    ctx.fillText(label, x + 14, 336);
    ctx.font = '30px "Press Start 2P", monospace';
    ctx.fillStyle = INK;
    ctx.fillText(value, x + 17, 403);
    ctx.fillStyle = color;
    ctx.fillText(value, x + 14, 400);
  });

  ctx.font = pf(22, 500);
  ctx.fillStyle = PAPER;
  ctx.fillText('A creature with no home. It lives on one', 608, 492);
  ctx.fillText('friend’s laptop at a time.', 608, 522);
  ctx.font = pf(18, 500);
  ctx.fillStyle = DUSK;
  ctx.fillText('built on Switch · Flip the Switch 2026', 608, 572);

  if (sample) {
    box(ctx, 940, 54, 200, 44, SUN, INK);
    ctx.font = pf(22, 700);
    ctx.fillStyle = INK;
    ctx.fillText('SAMPLE DATA', 966, 84);
  }
  return canvas;
}

export function PostcardButton({
  journey,
  derived,
  sample,
}: {
  journey: JourneyT;
  derived: Derived;
  sample: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const make = async (): Promise<void> => {
    setBusy(true);
    try {
      const canvas = await drawPostcard(journey, derived, sample);
      const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/png'));
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hermit-postcard-${journey.generated_at.slice(0, 10)}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
      sound.play('shell');
    } finally {
      setBusy(false);
    }
  };
  return (
    <PixelButton
      variant="quest"
      size="lg"
      icon="camera"
      onClick={() => void make()}
      disabled={busy}
    >
      {busy ? 'DRAWING…' : 'MAKE A POSTCARD'}
    </PixelButton>
  );
}
