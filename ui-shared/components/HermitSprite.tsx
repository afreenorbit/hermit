/**
 * Plays a named Hermit animation with the live shell on its back. Owner: C.
 * Also exports `SpriteAnimator` for the small effect sheets (dust, zzz, sparkle).
 *
 * Frames advance in whole steps at the animation's fps — never tweened. Under
 * reduced motion the first frame is held.
 */
import { useLayoutEffect, useMemo, useRef, type CSSProperties } from 'react';

import type { PixelGrid } from '../palette';
import { renderShellGrid, type ShellPieceInput } from '../shell/renderShellGrid';
import { toCanvas } from '../shell/adapters';
import { ANIMATIONS, composeFrame, FRAME, type AnimationName, type Pose } from '../sprite/hermit';
import { crispScale, useDevicePixelRatio, useFrame, useReducedMotion } from './hooks';

export interface SpriteAnimatorProps {
  frames: readonly PixelGrid[];
  fps: number;
  scale?: number;
  loop?: boolean;
  playing?: boolean;
  className?: string;
  style?: CSSProperties;
  label?: string;
}

export function SpriteAnimator({
  frames,
  fps,
  scale = 4,
  loop = true,
  playing = true,
  className,
  style,
  label,
}: SpriteAnimatorProps) {
  const reduced = useReducedMotion();
  const tick = useFrame(fps, playing && !reduced && frames.length > 1);
  const idx = reduced ? 0 : loop ? tick % frames.length : Math.min(tick, frames.length - 1);
  const grid = frames[idx] ?? frames[0];
  const ref = useRef<HTMLCanvasElement>(null);
  const dpr = useDevicePixelRatio();
  const { device, css } = crispScale(scale, dpr);
  const w = grid?.w ?? 0;
  const h = grid?.h ?? 0;

  useLayoutEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !grid) return;
    if (canvas.width !== w * device) canvas.width = w * device;
    if (canvas.height !== h * device) canvas.height = h * device;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    toCanvas(grid, ctx, device);
  }, [grid, device, w, h]);

  return (
    <canvas
      ref={ref}
      data-pixel
      className={className}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ width: w * css, height: h * css, imageRendering: 'pixelated', ...style }}
    />
  );
}

export interface HermitSpriteProps {
  animation?: AnimationName;
  /** Shell pieces to wear; empty means the borrowed shell. */
  pieces?: readonly ShellPieceInput[];
  scale?: number;
  flip?: boolean;
  /** Eye direction, -1..1 each. Overrides the pose's default glance. */
  look?: readonly [number, number];
  /** Blink on top of idle every few seconds. */
  blinks?: boolean;
  className?: string;
  style?: CSSProperties;
  label?: string;
}

export function HermitSprite({
  animation = 'idle',
  pieces,
  scale = 4,
  flip,
  look,
  blinks = true,
  className,
  style,
  label = 'Hermit',
}: HermitSpriteProps) {
  const shell = useMemo(
    () => (pieces && pieces.length ? renderShellGrid(pieces, { size: 24 }) : null),
    [pieces],
  );
  const lookKey = look ? `${look[0]},${look[1]}` : '';
  const anim = ANIMATIONS[animation];
  const reduced = useReducedMotion();
  const tick = useFrame(anim.fps, !reduced);

  // Blink: every ~5s, swap two frames of the idle loop for the blink frames.
  const blinkPhase = animation === 'idle' && blinks && !reduced ? tick % 22 : -1;
  const withLook = (p: Pose): Pose => (look ? { ...p, look } : p);
  // `lookKey` stands in for `look` so a new array literal doesn't rebuild frames.
  const frames = useMemo(
    () => anim.poses.map((p) => composeFrame(withLook(p), shell, flip)),
    [anim, shell, flip, lookKey],
  );
  const blinkFrames = useMemo(
    () => ANIMATIONS.blink.poses.map((p) => composeFrame(withLook(p), shell, flip)),
    [shell, flip, lookKey],
  );

  const grid =
    blinkPhase === 20 || blinkPhase === 21
      ? blinkFrames[blinkPhase - 20]
      : frames[reduced ? 0 : tick % frames.length];

  const ref = useRef<HTMLCanvasElement>(null);
  const dpr = useDevicePixelRatio();
  const { device, css } = crispScale(scale, dpr);

  useLayoutEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !grid) return;
    if (canvas.width !== FRAME * device) canvas.width = FRAME * device;
    if (canvas.height !== FRAME * device) canvas.height = FRAME * device;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    toCanvas(grid, ctx, device);
  }, [grid, device]);

  return (
    <canvas
      ref={ref}
      data-pixel
      className={className}
      role="img"
      aria-label={label}
      style={{ width: FRAME * css, height: FRAME * css, imageRendering: 'pixelated', ...style }}
    />
  );
}
