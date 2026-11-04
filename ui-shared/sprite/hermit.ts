/**
 * Hermit, drawn in code. Owner: C. plan.md §3.6 (sprite spec).
 *
 * 32x32 frames, Sweetie 16 only, 1px ink outline. A small crab-like creature
 * with two eyes on stalks and one claw bigger than the other. Its shell is NOT
 * part of the art: each frame composites the live `renderShellGrid` output on
 * the shell anchor, so the creature visibly grows the shell its friends built.
 *
 * Drawing in code instead of shipping an Aseprite sheet keeps every frame
 * deterministic, diffable and recolourable, and means the shell layer is real.
 */
import { borrowedShell, type ShellGrid } from '../shell/renderShellGrid';
import { blankGrid, EMPTY, P, type PixelGrid } from '../palette';

export const FRAME = 32;
/** Where the 24x24 shell grid is drawn inside a frame. */
export const SHELL_ANCHOR = { x: 1, y: 4 } as const;

export type Claw = 'rest' | 'open' | 'up' | 'high';

export interface Pose {
  bob?: number;
  jump?: number;
  /** 0 open, 1 half-lidded, 2 shut */
  blink?: 0 | 1 | 2;
  /** extra stalk height; negative droops */
  stalk?: number;
  look?: readonly [number, number];
  big?: Claw;
  small?: 'rest' | 'up';
  legs?: number;
  mouth?: 0 | 1 | 2;
}

export type AnimationName =
  'idle' | 'blink' | 'walk' | 'talk' | 'happy' | 'sleepy' | 'wave' | 'surprised';

export const ANIMATIONS: Record<AnimationName, { fps: number; poses: Pose[] }> = {
  idle: { fps: 4, poses: [{}, {}, { bob: 1 }, { bob: 1, big: 'open' }] },
  blink: { fps: 8, poses: [{ blink: 2 }, { blink: 1 }] },
  walk: {
    fps: 10,
    poses: [0, 1, 2, 3, 4, 5].map((legs) => ({
      legs,
      bob: legs % 2,
      big: legs % 3 === 0 ? 'open' : 'rest',
    })),
  },
  talk: {
    fps: 8,
    poses: [{ mouth: 1 }, { mouth: 2, big: 'open' }, { mouth: 1 }, { mouth: 0, big: 'open' }],
  },
  happy: {
    fps: 10,
    poses: [0, -1, -2, -2, -1, 0].map((jump) => ({
      jump,
      big: 'up' as const,
      small: 'up' as const,
      mouth: 2 as const,
    })),
  },
  sleepy: {
    fps: 3,
    poses: [
      { blink: 1, stalk: -2 },
      { blink: 1, stalk: -2 },
      { blink: 2, stalk: -2, bob: 1 },
      { blink: 2, stalk: -2, bob: 1 },
    ],
  },
  wave: {
    fps: 6,
    poses: [{ big: 'up' }, { big: 'high', mouth: 1 }, { big: 'up' }, { big: 'high', mouth: 1 }],
  },
  surprised: {
    fps: 8,
    poses: [
      { stalk: 2, jump: -1, mouth: 2 },
      { stalk: 3, jump: -2, mouth: 2, big: 'open' },
      { stalk: 2, jump: -1, mouth: 2 },
    ],
  },
};

class Layer {
  readonly g: PixelGrid = blankGrid(FRAME, FRAME);
  set(x: number, y: number, c: number): void {
    x = Math.round(x);
    y = Math.round(y);
    if (x < 0 || y < 0 || x >= FRAME || y >= FRAME) return;
    this.g.cells[y * FRAME + x] = c;
  }
  get(x: number, y: number): number {
    if (x < 0 || y < 0 || x >= FRAME || y >= FRAME) return EMPTY;
    return this.g.cells[y * FRAME + x] ?? EMPTY;
  }
  ellipse(
    cx: number,
    cy: number,
    rx: number,
    ry: number,
    c: number | ((x: number, y: number) => number),
  ): void {
    for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++) {
      for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++) {
        const nx = (x - cx) / (rx + 0.35);
        const ny = (y - cy) / (ry + 0.35);
        if (nx * nx + ny * ny <= 1) this.set(x, y, typeof c === 'number' ? c : c(x, y));
      }
    }
  }
  line(x0: number, y0: number, x1: number, y1: number, c: number): void {
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
      this.set(x0, y0, c);
      if (x0 === x1 && y0 === y1) break;
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
  /** 1px ink outline around everything drawn so far. */
  outline(color: number = P.ink): void {
    const src = [...this.g.cells];
    for (let y = 0; y < FRAME; y++) {
      for (let x = 0; x < FRAME; x++) {
        if (src[y * FRAME + x] !== EMPTY) continue;
        const near = [
          [x - 1, y],
          [x + 1, y],
          [x, y - 1],
          [x, y + 1],
        ].some(([nx, ny]) => {
          if (nx! < 0 || ny! < 0 || nx! >= FRAME || ny! >= FRAME) return false;
          const v = src[ny! * FRAME + nx!];
          return v !== EMPTY && v !== color;
        });
        if (near) this.g.cells[y * FRAME + x] = color;
      }
    }
  }
}

function drawEye(l: Layer, cx: number, cy: number, pose: Pose): void {
  const blink = pose.blink ?? 0;
  if (blink === 2) {
    l.line(cx - 1, cy, cx + 1, cy, P.ink);
    l.set(cx, cy - 1, P.ember);
    return;
  }
  for (let y = -1; y <= 1; y++) for (let x = -1; x <= 1; x++) l.set(cx + x, cy + y, P.paper);
  const [lx, ly] = pose.look ?? [1, 0];
  const px = cx + Math.max(-1, Math.min(1, lx));
  const py = cy + Math.max(blink === 1 ? 0 : -1, Math.min(1, ly));
  l.set(px, py, P.ink);
  if (blink === 1) l.line(cx - 1, cy - 1, cx + 1, cy - 1, P.ember);
}

function drawClaw(l: Layer, cx: number, cy: number, r: number, open: boolean): void {
  l.ellipse(cx, cy, r, r + 0.5, (x, y) => (y > cy + 0.5 ? P.berry : x < cx ? P.ember : P.sun));
  l.set(cx - 1, cy - 1, P.sun);
  if (open) {
    l.line(cx + 1, cy, cx + r + 1, cy, EMPTY);
    l.set(cx, cy, EMPTY);
  } else {
    l.set(cx + r, cy, EMPTY);
  }
}

/** Draw the creature (no shell) for one pose. */
export function drawBody(pose: Pose): PixelGrid {
  const l = new Layer();
  const bob = (pose.bob ?? 0) + (pose.jump ?? 0);
  const jump = pose.jump ?? 0;
  const stalk = pose.stalk ?? 0;
  const legPhase = pose.legs ?? 0;

  // legs first so the body overlaps them
  [16, 19, 22].forEach((bx, i) => {
    const swing = Math.round(Math.sin((legPhase / 6) * Math.PI * 2 + i * 2.1));
    const footY = 30 + Math.min(0, jump);
    l.line(bx, 26 + bob, bx - 1 + swing, footY - 1, P.berry);
    l.set(bx - 2 + swing, footY, P.berry);
  });

  // small claw, low and in front
  const small = pose.small === 'up' ? { x: 27, y: 25 } : { x: 27, y: 28 };
  l.line(24, 26 + bob, small.x - 1, small.y + bob, P.ember);
  drawClaw(l, small.x, small.y + bob, 1, false);

  // torso
  const tx = 20;
  const ty = 23 + bob;
  l.ellipse(tx, ty, 6, 4, (x, y) => {
    if (y >= ty + 2) return P.berry;
    if (y <= ty - 2 && x <= tx - 1 && x >= tx - 4) return P.sun;
    return P.ember;
  });

  // mouth
  const mouth = pose.mouth ?? 0;
  l.set(25, ty + 1, P.ink);
  if (mouth >= 1) l.set(24, ty + 1, P.ink);
  if (mouth === 2) {
    l.set(24, ty + 2, P.berry);
    l.set(25, ty + 2, P.ink);
  }

  // eye stalks + eyes
  const eL = { x: 18, y: 15 - stalk + bob };
  const eR = { x: 23, y: 14 - stalk + bob };
  l.line(18, ty - 3, eL.x, eL.y + 1, P.ember);
  l.line(22, ty - 3, eR.x, eR.y + 1, P.ember);
  drawEye(l, eL.x, eL.y, pose);
  drawEye(l, eR.x, eR.y, pose);

  // big claw — the important one
  const big = pose.big ?? 'rest';
  const at = big === 'up' ? { x: 28, y: 16 } : big === 'high' ? { x: 28, y: 12 } : { x: 28, y: 20 };
  l.line(25, ty, at.x - 1, at.y + bob + 2, P.ember);
  drawClaw(l, at.x, at.y + bob, 2, big !== 'rest');

  l.outline(P.ink);
  return l.g;
}

/** Composite shell + body into one frame. `shell` defaults to the borrowed shell. */
export function composeFrame(pose: Pose, shell?: ShellGrid | null, flip = false): PixelGrid {
  const out = blankGrid(FRAME, FRAME);
  const sh = shell && shell.cells.some((c) => c !== EMPTY) ? shell : borrowedShell(24);
  const jump = pose.jump ?? 0;
  for (let y = 0; y < sh.h; y++) {
    for (let x = 0; x < sh.w; x++) {
      const v = sh.cells[y * sh.w + x] ?? EMPTY;
      if (v === EMPTY) continue;
      const fx = SHELL_ANCHOR.x + x;
      const fy = SHELL_ANCHOR.y + y + jump;
      if (fx < 0 || fy < 0 || fx >= FRAME || fy >= FRAME) continue;
      out.cells[fy * FRAME + fx] = v;
    }
  }
  const body = drawBody(pose);
  for (let i = 0; i < body.cells.length; i++) {
    const v = body.cells[i] ?? EMPTY;
    if (v !== EMPTY) out.cells[i] = v;
  }
  if (flip) {
    for (let y = 0; y < FRAME; y++) {
      const row = out.cells.slice(y * FRAME, (y + 1) * FRAME).reverse();
      for (let x = 0; x < FRAME; x++) out.cells[y * FRAME + x] = row[x] ?? EMPTY;
    }
  }
  return out;
}

export function animationFrames(
  name: AnimationName,
  shell?: ShellGrid | null,
  flip = false,
): PixelGrid[] {
  return ANIMATIONS[name].poses.map((p) => composeFrame(p, shell, flip));
}
