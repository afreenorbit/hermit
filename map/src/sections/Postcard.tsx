/**
 * "Make a postcard": a 1200×630 PNG of Tilli, the shell and the top stats,
 * for the README header and the #HowISwitch post. Owner: C. plan.md §7.6.
 *
 * Drawn straight onto one canvas instead of screenshotting the DOM: the shell
 * keeps whole pixels, and Tilli is the same SVG the page animates.
 */
import {
  formatDay,
  formatHandoffMs,
  PixelButton,
  renderShellGrid,
  sound,
  tilliSvg,
  toCanvas,
} from '@hermit/ui';
import type { JourneyT } from '@hermit/ui/contracts';
import { useState } from 'react';

import type { Derived } from '../lib/derive';

const CREAM = '#f8f1e5';
const PAPER = '#fffaf1';
const INK = '#5b3d27';
const TEXT = '#483424';
const MUTED = '#74604a';
const BUTTER = '#f8d98a';
const SAGE_SOFT = '#e7ecd3';
const PEACH_SOFT = '#fbe3d7';
const SKY_SOFT = '#e2f0f4';

function sticker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  face: string,
): void {
  ctx.fillStyle = '#e2d0ad';
  ctx.beginPath();
  ctx.roundRect(x, y + 7, w, h, r);
  ctx.fill();
  ctx.fillStyle = face;
  ctx.strokeStyle = INK;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
  ctx.stroke();
}

function loadSvg(markup: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
  });
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
  try {
    await Promise.all([
      document.fonts.load('600 64px "Fredoka"'),
      document.fonts.load('600 24px "Nunito"'),
    ]);
  } catch {
    /* system fonts are fine */
  }
  const fredoka = (size: number, weight = 600): string =>
    `${weight} ${size}px "Fredoka", ui-rounded, system-ui, sans-serif`;
  const nunito = (size: number, weight = 600): string =>
    `${weight} ${size}px "Nunito", system-ui, sans-serif`;

  // paper card with a soft dotted ground
  ctx.fillStyle = CREAM;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#ecdfc6';
  for (let y = 18; y < H; y += 28) for (let x = 18; x < W; x += 28) ctx.fillRect(x, y, 3, 3);
  ctx.strokeStyle = INK;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.roundRect(22, 22, W - 44, H - 44, 34);
  ctx.stroke();

  // the shell in a little frame
  sticker(ctx, 64, 300, 240, 240, 26, PAPER);
  ctx.save();
  ctx.translate(88, 324);
  ctx.imageSmoothingEnabled = false;
  toCanvas(renderShellGrid(d.pieces, { size: 48 }), ctx, 4);
  ctx.restore();
  ctx.fillStyle = MUTED;
  ctx.font = fredoka(18, 500);
  ctx.fillText('the shell we built', 112, 572);

  // Tilli, celebrating, big
  ctx.fillStyle = '#fdf0c9';
  ctx.beginPath();
  ctx.ellipse(420, 360, 200, 200, 0, 0, Math.PI * 2);
  ctx.fill();
  try {
    const tilli = await loadSvg(tilliSvg({ mood: 'celebrate', title: '' }));
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(tilli, 238, 150, 400, 400);
  } catch {
    /* the card still works without the mascot */
  }

  // words
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = TEXT;
  ctx.font = fredoka(72, 600);
  ctx.fillText('Hermit', 64, 132);
  ctx.font = fredoka(30, 500);
  ctx.fillStyle = MUTED;
  ctx.fillText('with Tilli, a creature with no home', 66, 178);
  ctx.font = nunito(26, 700);
  ctx.fillStyle = TEXT;
  const friends = d.hostIds.length;
  ctx.fillText(
    `Visited ${friends} friend${friends === 1 ? '' : 's'} in ${d.places} place${d.places === 1 ? '' : 's'}`,
    66,
    232,
  );
  if (d.range) {
    ctx.font = nunito(20, 600);
    ctx.fillStyle = MUTED;
    ctx.fillText(`${formatDay(d.range.from)} → ${formatDay(d.range.to)}`, 66, 264);
  }

  // three stat stickers
  const stats: Array<[string, string, string]> = [
    ['Favors done', String(journey.stats.favors_done ?? d.favorsDone), PEACH_SOFT],
    ['Shell pieces', String(d.pieces.length), SAGE_SOFT],
    ['Median handoff', formatHandoffMs(journey.stats.median_handoff_ms).toLowerCase(), SKY_SOFT],
  ];
  stats.forEach(([label, value, face], i) => {
    const y = 120 + i * 140;
    sticker(ctx, 860, y, 276, 112, 22, face);
    ctx.font = fredoka(20, 500);
    ctx.fillStyle = MUTED;
    ctx.fillText(label, 886, y + 38);
    ctx.font = fredoka(46, 600);
    ctx.fillStyle = TEXT;
    ctx.fillText(value, 886, y + 90);
  });

  ctx.font = nunito(18, 600);
  ctx.fillStyle = MUTED;
  ctx.fillText('built on Switch · Flip the Switch 2026', 862, 578);

  if (sample) {
    ctx.fillStyle = BUTTER;
    ctx.strokeStyle = INK;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(862, 50, 190, 44, 22);
    ctx.fill();
    ctx.stroke();
    ctx.font = fredoka(20, 600);
    ctx.fillStyle = TEXT;
    ctx.fillText('Sample data', 898, 80);
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
      {busy ? 'Drawing…' : 'Make a postcard'}
    </PixelButton>
  );
}
