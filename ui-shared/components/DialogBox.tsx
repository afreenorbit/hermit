/**
 * RPG speech box: name tab, typewriter reveal at 30 chars/s, click or key to
 * skip, blinking ▼ when done. Instant under reduced motion. Owner: C.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { useReducedMotion } from './hooks';

export interface DialogBoxProps {
  text: string;
  name?: string;
  /** Extra content beside the name tab, e.g. a BrainBadge. */
  badge?: ReactNode;
  speed?: number;
  tone?: 'paper' | 'night' | 'dream';
  compact?: boolean;
  onDone?: () => void;
  className?: string;
}

export function DialogBox({
  text,
  name = 'HERMIT',
  badge,
  speed = 30,
  tone = 'paper',
  compact,
  onDone,
  className,
}: DialogBoxProps) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(reduced ? text.length : 0);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    if (reduced) {
      setShown(text.length);
      return;
    }
    setShown(0);
    const id = window.setInterval(() => {
      setShown((n) => {
        if (n >= text.length) {
          window.clearInterval(id);
          return n;
        }
        return n + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(id);
  }, [text, speed, reduced]);

  const done = shown >= text.length;
  useEffect(() => {
    if (done) doneRef.current?.();
  }, [done]);

  const skip = (): void => setShown(text.length);

  return (
    <div
      className={`hm-dialog hm-dialog--${tone}${compact ? ' hm-dialog--compact' : ''} ${className ?? ''}`}
      onClick={skip}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          skip();
        }
      }}
      tabIndex={0}
      role="group"
      aria-label={`${name} says`}
    >
      <div className="hm-dialog__head">
        <span className="hm-dialog__name">{name}</span>
        {badge}
      </div>
      {/* Screen readers get the full line at once, not a letter at a time. */}
      <p className="hm-dialog__text" aria-hidden>
        {text.slice(0, shown)}
        <span className="hm-dialog__ghost">{text.slice(shown)}</span>
      </p>
      <span className="hm-sr">{text}</span>
      {done && (
        <span className="hm-dialog__more" aria-hidden>
          ▼
        </span>
      )}
    </div>
  );
}
