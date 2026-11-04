/** Fetch + validate journey.json. Owner: C. Swap the cast for a zod schema in Phase 1.2. */
import { useEffect, useState } from 'react';

export interface Journey {
  v: 1;
  generated_at: string;
  hermit: { current_host: string | null; current_city: string | null; since: string | null };
  hosts: Array<{ host_id: string; display_name: string; city: string; lat: number; lon: number }>;
  stops: Array<Record<string, unknown>>;
  shell: Array<Record<string, unknown>>;
  stats: { handoffs: number; favors_done: number; favors_left: number };
}

export function useJourney() {
  const [journey, setJourney] = useState<Journey | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      for (const url of ['/data/journey.json', '/data/journey.sample.json']) {
        try {
          const res = await fetch(url);
          if (!res.ok) continue;
          const data = (await res.json()) as Journey;
          if (!cancelled) setJourney(data);
          return;
        } catch {
          /* try the next one */
        }
      }
      if (!cancelled) setError('no journey data found');
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { journey, error };
}
