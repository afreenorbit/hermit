/**
 * The journey map. Owner: C, Phase 7.
 *
 * Reads `public/data/journey.json` (falls back to the committed sample) and
 * shows: where Hermit has been, what friends did for each other, and the shell.
 */
import { useJourney } from './hooks/useJourney';

export function App() {
  const { journey, error } = useJourney();

  return (
    <main className="min-h-screen bg-mist p-8 text-ink" style={{ fontFamily: 'var(--font-body)' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 20 }}>HERMIT</h1>
      <p className="mt-4 max-w-prose">
        A creature with no home, living on one friend&apos;s laptop at a time.
      </p>

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
