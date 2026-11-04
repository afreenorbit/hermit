/**
 * The journey map. Owner: Akshay, Phase 7.
 *
 * Reads `public/data/journey.json` (falls back to the committed sample) and
 * shows where Hermit has been, what friends did for each other, and the shell.
 *
 * This is a scaffold with the mascot wired in, not the finished page — the
 * world canvas, shell panel and quest log are Akshay's.
 */
import { PocketHermit, type Mood } from '@hermit/ui';

import { useJourney } from './hooks/useJourney';

export function App() {
  const { journey, error } = useJourney();
  const mood: Mood = journey?.hermit.current_host ? 'visiting' : 'away';
  const withWhom = journey?.hosts.find((h) => h.host_id === journey.hermit.current_host);

  return (
    <main className="min-h-screen px-6 py-10" style={{ background: 'var(--color-off-white)' }}>
      <div className="mx-auto flex max-w-3xl flex-col items-center gap-6 text-center">
        <PocketHermit mood={mood} size={160} />

        <h1 className="text-3xl font-semibold" style={{ color: 'var(--color-warm-brown)' }}>
          Hermit
        </h1>
        <p className="max-w-prose" style={{ color: 'var(--color-warm-brown)' }}>
          A small creature with no home, living on one friend&apos;s laptop at a time.
        </p>

        {error && <p style={{ color: 'var(--color-blush)' }}>could not load the journey: {error}</p>}

        {journey && (
          <>
            <p className="text-lg" style={{ color: 'var(--color-deep-sage)' }}>
              {withWhom
                ? `right now Hermit is with ${withWhom.display_name} in ${withWhom.city}`
                : 'Hermit is between friends'}
            </p>
            <dl className="flex gap-10">
              <Stat label="stops" value={journey.stops.length} />
              <Stat label="favors done" value={journey.stats.favors_done} />
              <Stat label="friends" value={journey.hosts.length} />
            </dl>
          </>
        )}

        {/* TODO(Akshay): WorldPanel, ShellPanel, ImpactPanel, QuestLog, PostcardButton */}
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-sm" style={{ color: 'var(--color-sage)' }}>
        {label}
      </dt>
      <dd className="text-3xl font-semibold" style={{ color: 'var(--color-deep-sage)' }}>
        {value}
      </dd>
    </div>
  );
}
