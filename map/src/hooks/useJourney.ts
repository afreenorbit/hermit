/**
 * Fetch + zod-validate journey.json. Owner: C. plan.md §7.0.
 *
 * Order: `?data=wide` → the wide sample; otherwise the real export
 * (`data/journey.json`), falling back to the committed Bengaluru sample with a
 * SAMPLE DATA ribbon so nobody mistakes it for a pilot.
 */
import { Journey, type JourneyT } from '@hermit/ui/contracts';
import { useEffect, useState } from 'react';

export type JourneySource = 'live' | 'sample' | 'wide';

export interface JourneyState {
  journey: JourneyT | null;
  source: JourneySource | null;
  error: string | null;
}

const FILES: Record<JourneySource, string> = {
  live: 'data/journey.json',
  sample: 'data/journey.sample.json',
  wide: 'data/journey.wide.sample.json',
};

export function requestedSource(
  search = typeof location === 'undefined' ? '' : location.search,
): JourneySource | null {
  const v = new URLSearchParams(search).get('data');
  return v === 'wide' || v === 'sample' || v === 'live' ? v : null;
}

export function useJourney(want: JourneySource | null = requestedSource()): JourneyState {
  const [state, setState] = useState<JourneyState>({ journey: null, source: null, error: null });

  useEffect(() => {
    let cancelled = false;
    const order: JourneySource[] = want && want !== 'live' ? [want] : ['live', 'sample'];
    const load = async (): Promise<void> => {
      let lastError = 'no journey data found';
      for (const source of order) {
        try {
          const res = await fetch(`${import.meta.env.BASE_URL}${FILES[source]}`, {
            cache: 'no-store',
          });
          if (!res.ok) continue;
          const parsed = Journey.safeParse(await res.json());
          if (!parsed.success) {
            const issue = parsed.error.issues[0];
            lastError = `${FILES[source]} does not match the schema: ${issue?.path.join('.') ?? ''} ${issue?.message ?? ''}`;
            continue;
          }
          if (!cancelled) setState({ journey: parsed.data, source, error: null });
          return;
        } catch {
          /* not there or not JSON — try the next one */
        }
      }
      if (!cancelled) setState({ journey: null, source: null, error: lastError });
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [want]);

  return state;
}
