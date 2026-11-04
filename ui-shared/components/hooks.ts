/** Small hooks every pixel component leans on. Owner: C. */
import { useEffect, useState } from 'react';

function query(q: string): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia?.(q).matches;
}

export function useMediaQuery(q: string): boolean {
  const [match, setMatch] = useState(() => query(q));
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia(q);
    const on = (): void => setMatch(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [q]);
  return match;
}

export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

export function useDevicePixelRatio(): number {
  const [dpr, setDpr] = useState(() =>
    typeof window === 'undefined' ? 1 : window.devicePixelRatio || 1,
  );
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia(`(resolution: ${dpr}dppx)`);
    const on = (): void => setDpr(window.devicePixelRatio || 1);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [dpr]);
  return dpr;
}

/**
 * Integer device pixels per art pixel, closest to `cssScale` CSS px.
 * Keeps sprites crisp at 100/125/150/200% display scaling: we never ask the
 * browser for a fractional device scale.
 */
export function crispScale(cssScale: number, dpr: number): { device: number; css: number } {
  const device = Math.max(1, Math.round(cssScale * dpr));
  return { device, css: device / dpr };
}

/** Advance a frame counter at `fps` while `running`. */
export function useFrame(fps: number, running = true): number {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (!running || fps <= 0) return;
    const id = window.setInterval(() => setFrame((f) => f + 1), 1000 / fps);
    return () => window.clearInterval(id);
  }, [fps, running]);
  return frame;
}
