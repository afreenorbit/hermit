/**
 * The journey map. Owner: C, Phase 7.
 *
 * Reads `public/data/journey.json` (falls back to the committed sample) and
 * shows: where Hermit has been, what friends did for each other, and the shell.
 */
import { useState } from 'react';
import { useJourney } from './hooks/useJourney';

export function App() {
  const { journey, error } = useJourney();
  const [pose, setPose] = useState('visiting');

  return (
    <main className="min-h-screen bg-mist p-8 text-ink" style={{ fontFamily: 'var(--font-body)' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 20 }}>HERMIT</h1>
      <p className="mt-4 max-w-prose">
        A creature with no home, living on one friend&apos;s laptop at a time.
      </p>

      <section className="mt-6" aria-label="Pocket Hermit preview">
        <h2>Pocket Hermit</h2>
        <picture key={pose}>
          <source media="(prefers-reduced-motion: reduce)" srcSet={`/pocket-hermit/${pose}.png`} />
          <img width="220" height="220" className="h-[220px] w-[220px] rounded-2xl object-contain"
            src={`/pocket-hermit/${pose}.webp`} alt={`Pocket Hermit, ${pose}`} />
        </picture>
        <p>Preview a movement</p>
        <div className="flex flex-wrap gap-2">
          {['arriving', 'visiting', 'sleeping', 'away'].map((state) => (
            <button key={state} type="button" aria-pressed={pose === state}
              className="rounded border px-3 py-1 capitalize aria-pressed:font-bold"
              onClick={() => setPose(state)}>{state}</button>
          ))}
        </div>
      </section>
      {error && <p className="mt-6 text-berry">could not load the journey: {error}</p>}

      {journey && (
        <p className="mt-6">
          {journey.stops.length} stops · {journey.stats.favors_done} favors done · currently with{' '}
          {journey.hermit.current_host ?? 'nobody'}
        </p>
      )}

      {/* TODO(C): Header, WorldPanel, ShellPanel, ImpactPanel, QuestLog, PostcardButton */}
    </main>
  );
}
