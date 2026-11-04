/** LED-style one-line status: "NOW: WITH AKSHAY · KORAMANGALA · 42M". Owner: C. */
import type { ReactNode } from 'react';

export function Ticker({ children, live }: { children: ReactNode; live?: boolean }) {
  return (
    <div className={`hm-ticker${live ? ' hm-ticker--live' : ''}`} role="status">
      <span className="hm-ticker__led" aria-hidden />
      <span className="hm-ticker__text">{children}</span>
    </div>
  );
}
