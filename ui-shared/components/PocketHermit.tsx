/**
 * The mascot. Owner: Akshay (art), Afreen (wiring).
 *
 * Four states, matching `map/public/pocket-hermit/*` and the `mood` the keeper
 * API returns, so this component can take `status.mood` straight from
 * `/v1/status` with nothing in between to drift.
 */

export type Mood = 'arriving' | 'visiting' | 'away' | 'sleeping';

/** What each state means, for alt text and tooltips. */
export const MOOD_LABEL: Record<Mood, string> = {
  arriving: 'Hermit is arriving, carrying a letter',
  visiting: 'Hermit is here',
  away: 'Hermit is somewhere else',
  sleeping: 'Hermit has gone to bed',
};

export interface PocketHermitProps {
  mood: Mood;
  /** Rendered size in px. The art is square. */
  size?: number;
  /** Where the images live. Override if not served from the site root. */
  basePath?: string;
  className?: string;
}

export function PocketHermit({
  mood,
  size = 128,
  basePath = '/pocket-hermit',
  className,
}: PocketHermitProps) {
  return (
    <picture className={className}>
      <source srcSet={`${basePath}/${mood}.webp`} type="image/webp" />
      <img
        src={`${basePath}/${mood}.png`}
        alt={MOOD_LABEL[mood]}
        width={size}
        height={size}
        style={{ width: size, height: size, objectFit: 'contain' }}
        draggable={false}
      />
    </picture>
  );
}
