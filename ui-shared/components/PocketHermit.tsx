/**
 * Pocket Hermit — the mascot, everywhere.
 *
 * The art is Afreen's: animated WebP (40–60 frames, looping) with a matching
 * PNG still for each pose, in `ui-shared/assets/pocket-hermit/`. They are
 * imported rather than read from a `public/` folder so the map and the
 * Electron critter share one set of source files and each bundler emits its
 * own copy — no duplicated art in the repo.
 *
 * Six moods, which are exactly the `mood` values the keeper API returns, so a
 * caller can pass `status.mood` straight through with no lookup table in
 * between to drift:
 *
 *   visiting  Hermit is on this laptop                 (only ever one laptop)
 *   arriving  just claimed the soul, carrying a letter
 *   away      leaving, or just left
 *   sleeping  this host is idle, or past their bedtime
 *   waiting   this laptop is awake; Hermit is elsewhere
 *   offline   we cannot reach this keeper — not a guess, an admission
 *
 * There is art for four poses and six moods, so `waiting` and `offline` reuse
 * the tucked-in `away` drawing and are told apart by styling: waiting is calm
 * and slightly faded, offline is greyed out. Reusing a pose is honest here —
 * in all three the creature is not with you.
 */
import type { CSSProperties } from 'react';

import arrivingStill from '../assets/pocket-hermit/arriving.png';
import arrivingMotion from '../assets/pocket-hermit/arriving.webp';
import awayStill from '../assets/pocket-hermit/away.png';
import awayMotion from '../assets/pocket-hermit/away.webp';
import sleepingStill from '../assets/pocket-hermit/sleeping.png';
import sleepingMotion from '../assets/pocket-hermit/sleeping.webp';
import visitingStill from '../assets/pocket-hermit/visiting.png';
import visitingMotion from '../assets/pocket-hermit/visiting.webp';
import { useReducedMotion } from './hooks';

export type Mood = 'visiting' | 'arriving' | 'away' | 'sleeping' | 'waiting' | 'offline';

export const MOODS: readonly Mood[] = [
  'visiting',
  'arriving',
  'away',
  'sleeping',
  'waiting',
  'offline',
];

/** Which drawing each mood uses. */
const POSE: Record<Mood, { motion: string; still: string }> = {
  visiting: { motion: visitingMotion, still: visitingStill },
  arriving: { motion: arrivingMotion, still: arrivingStill },
  away: { motion: awayMotion, still: awayStill },
  sleeping: { motion: sleepingMotion, still: sleepingStill },
  waiting: { motion: awayMotion, still: awayStill },
  offline: { motion: awayStill, still: awayStill },
};

/** The image URL for a mood — for canvases (the postcard) that cannot use <img>. */
export function pocketHermitSrc(mood: Mood, still = true): string {
  const pose = POSE[mood] ?? POSE.offline;
  return still ? pose.still : pose.motion;
}

/** Said out loud by screen readers, and used as the default caption. */
export const MOOD_LABEL: Record<Mood, string> = {
  visiting: 'Hermit is here with you',
  arriving: 'Hermit is arriving, carrying a letter',
  away: 'Hermit is leaving',
  sleeping: 'Hermit has settled down to sleep',
  waiting: 'Hermit is with someone else right now',
  offline: "Can't reach this laptop",
};

export interface PocketHermitProps {
  mood: Mood;
  /** Rendered width in CSS px. The art is roughly square. */
  size?: number;
  /** Force the still frame (thumbnails). Reduced motion does this anyway. */
  still?: boolean;
  /** Override the alt text; pass '' for a decorative image. */
  label?: string;
  className?: string;
  style?: CSSProperties;
}

export function PocketHermit({
  mood,
  size = 128,
  still,
  label,
  className,
  style,
}: PocketHermitProps) {
  const reduced = useReducedMotion();
  const pose = POSE[mood] ?? POSE.offline;
  // An animated WebP ignores prefers-reduced-motion on its own, so swapping to
  // the PNG still is the only way to actually honour the setting.
  const src = still || reduced ? pose.still : pose.motion;

  return (
    <img
      className={`pocket-hermit pocket-hermit--${mood} ${className ?? ''}`}
      src={src}
      alt={label ?? MOOD_LABEL[mood]}
      width={size}
      height={size}
      draggable={false}
      style={{ width: size, height: size, objectFit: 'contain', ...style }}
    />
  );
}
