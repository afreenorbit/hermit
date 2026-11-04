/** Big pixel number that counts up the first time it is seen. Owner: C. */
import { useEffect, useRef, useState } from 'react';

import type { IconName } from '../sprite/glyphs';
import { useReducedMotion } from './hooks';
import { PixelIcon } from './PixelIcon';

export interface StatTileProps {
  label: string;
  value: number | string;
  icon?: IconName;
  /** Formats the animated number (e.g. seconds). */
  format?: (n: number) => string;
  hint?: string;
  tone?: 'ember' | 'sun' | 'leaf' | 'sea' | 'berry' | 'dream';
}

export function StatTile({ label, value, icon, format, hint, tone = 'sun' }: StatTileProps) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const target = typeof value === 'number' ? value : null;
  const [n, setN] = useState(target ?? 0);
  const started = useRef(false);

  useEffect(() => {
    if (target === null) return;
    if (reduced || typeof IntersectionObserver === 'undefined') {
      setN(target);
      return;
    }
    const el = ref.current;
    if (!el) return;
    if (started.current) {
      setN(target);
      return;
    }
    setN(0);
    let timer = 0;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting) || started.current) return;
      started.current = true;
      io.disconnect();
      // 12 whole steps over ~0.9s — ticks like a game counter, not a tween.
      // A timer (not rAF) so a background tab still lands on the real value.
      let step = 0;
      timer = window.setInterval(() => {
        step += 1;
        setN(step >= 12 ? target : Math.round((target * step) / 12));
        if (step >= 12) window.clearInterval(timer);
      }, 75);
    });
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearInterval(timer);
      if (started.current) setN(target);
    };
  }, [target, reduced]);

  const shown = target === null ? String(value) : format ? format(n) : String(n);
  const full = target === null ? String(value) : format ? format(target) : String(target);

  return (
    <div ref={ref} className={`hm-stat hm-stat--${tone}`} title={hint}>
      <div className="hm-stat__label">
        {icon && <PixelIcon name={icon} />}
        <span>{label}</span>
      </div>
      <div className="hm-stat__value" aria-hidden>
        {shown}
      </div>
      <span className="hm-sr">
        {label}: {full}
      </span>
      {hint && <div className="hm-stat__hint">{hint}</div>}
    </div>
  );
}
