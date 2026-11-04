/**
 * Fetch + zod-validate a journey. Owner: C. plan.md §7.0.
 *
 * Which journey: `?journey=<id>` picks one of SCENARIOS (`?data=` is the old
 * spelling and still works). With no choice, the real export
 * (`data/journey.json`, git-ignored) is tried first, falling back to the
 * committed Bengaluru sample — so a hosted build without an export still shows
 * something, clearly labelled.
 *
 * Honest labelling: `kind` comes from the data's own `source.kind` when it has
 * one, and otherwise from which file it was: the committed samples are always
 * `sample`, the export is `real`. A simulation never passes as real.
 */
import { Journey, type JourneySourceKindT, type JourneyT } from '@hermit/ui/contracts';
import { useCallback, useEffect, useState } from 'react';

export type ScenarioId = 'bengaluru' | 'three_cities' | 'world';
/** Which file a journey actually came from. */
export type JourneySource = 'live' | 'sample' | 'three_cities' | 'wide';
export type JourneyKind = JourneySourceKindT;

export interface Scenario {
  id: ScenarioId;
  label: string;
  title: string;
  /** Files to try, in order. */
  files: JourneySource[];
}

export const SCENARIOS: readonly Scenario[] = [
  {
    id: 'bengaluru',
    label: 'Bengaluru',
    title: 'Three areas of one city — our real group',
    files: ['live', 'sample'],
  },
  {
    id: 'three_cities',
    label: '3 cities · sim',
    title: 'Bengaluru → Berlin → Toronto, from the simulator (three_cities_day)',
    files: ['three_cities'],
  },
  {
    id: 'world',
    label: 'World · sample',
    title: 'A hand-made three-continent sample, to show the world view',
    files: ['wide'],
  },
];

export const FILES: Record<JourneySource, string> = {
  live: 'data/journey.json',
  sample: 'data/journey.sample.json',
  three_cities: 'data/journey.three_cities.json',
  wide: 'data/journey.wide.sample.json',
};

const ALIASES: Record<string, ScenarioId> = {
  bengaluru: 'bengaluru',
  city: 'bengaluru',
  sample: 'bengaluru',
  live: 'bengaluru',
  three_cities: 'three_cities',
  'three-cities': 'three_cities',
  three_cities_day: 'three_cities',
  sim: 'three_cities',
  world: 'world',
  wide: 'world',
};

/** `?journey=three_cities` (or the older `?data=wide`), else null. */
export function requestedScenario(
  search = typeof location === 'undefined' ? '' : location.search,
): ScenarioId | null {
  const q = new URLSearchParams(search);
  const v = (q.get('journey') ?? q.get('data') ?? '').toLowerCase();
  return ALIASES[v] ?? null;
}

export function scenarioById(id: ScenarioId | null): Scenario {
  return SCENARIOS.find((s) => s.id === id) ?? SCENARIOS[0]!;
}

/** What the page should call this journey. */
export function kindOf(journey: Pick<JourneyT, 'source'>, file: JourneySource): JourneyKind {
  const declared = journey.source?.kind;
  if (declared) return declared;
  return file === 'live' ? 'real' : 'sample';
}

export interface JourneyState {
  journey: JourneyT | null;
  /** The file it came from. */
  source: JourneySource | null;
  kind: JourneyKind | null;
  error: string | null;
  loading: boolean;
  retry: () => void;
}

export function useJourney(want: ScenarioId | null = requestedScenario()): JourneyState {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<Omit<JourneyState, 'retry'>>({
    journey: null,
    source: null,
    kind: null,
    error: null,
    loading: true,
  });
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const order = scenarioById(want).files;
    setState((s) => ({ ...s, loading: true, error: null }));
    const load = async (): Promise<void> => {
      let lastError = 'no journey data found';
      for (const source of order) {
        try {
          const res = await fetch(`${import.meta.env.BASE_URL}${FILES[source]}`, {
            cache: 'no-store',
            signal: controller.signal,
          });
          if (!res.ok) {
            lastError = `${FILES[source]}: HTTP ${res.status}`;
            continue;
          }
          // A static host answers a missing file with its index.html; that is
          // "not there", not "broken".
          if (!(res.headers.get('content-type') ?? 'application/json').includes('json')) {
            lastError = `${FILES[source]} is not there`;
            continue;
          }
          const parsed = Journey.safeParse(await res.json());
          if (!parsed.success) {
            const issue = parsed.error.issues[0];
            lastError = `${FILES[source]} does not match the schema: ${issue?.path.join('.') ?? ''} ${issue?.message ?? ''}`;
            continue;
          }
          if (!cancelled)
            setState({
              journey: parsed.data,
              source,
              kind: kindOf(parsed.data, source),
              error: null,
              loading: false,
            });
          return;
        } catch (err) {
          if (controller.signal.aborted) return;
          lastError =
            err instanceof SyntaxError
              ? `${FILES[source]} is not valid JSON`
              : `could not fetch ${FILES[source]} — are you offline?`;
        }
      }
      if (!cancelled)
        setState({ journey: null, source: null, kind: null, error: lastError, loading: false });
    };
    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [want, attempt]);

  return { ...state, retry };
}
