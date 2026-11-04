/**
 * The journey map. Owner: C, Phase 7.
 *
 * Where Hermit has been, what friends did for each other, and the shell they
 * built. Reads `data/journey.json` (falls back to the committed sample).
 */
import { HermitSprite, PixelBox, sound, useMediaQuery, useReducedMotion } from '@hermit/ui';
import { useEffect, useMemo, useRef, useState } from 'react';

import { requestedSource, useJourney, type JourneySource } from './hooks/useJourney';
import { useTheme } from './hooks/useTheme';
import { derive } from './lib/derive';
import { Header } from './sections/Header';
import { ImpactPanel } from './sections/ImpactPanel';
import { PostcardButton } from './sections/Postcard';
import { QuestLog } from './sections/QuestLog';
import { ShellPanel } from './sections/ShellPanel';
import { WorldPanel } from './world/WorldPanel';

export function App() {
  const [want, setWant] = useState<JourneySource | null>(requestedSource);
  const { journey, source, error } = useJourney(want);
  const { dark, toggle } = useTheme();
  const reduced = useReducedMotion();
  const narrow = useMediaQuery('(max-width: 767px)');
  const derived = useMemo(() => (journey ? derive(journey) : null), [journey]);

  const [friend, setFriend] = useState<string | null>(null);
  const [activePiece, setActivePiece] = useState<number | null>(null);
  const [flashStop, setFlashStop] = useState<string | null>(null);
  const flashTimer = useRef<number>(0);

  useEffect(() => {
    setFriend(null);
    setActivePiece(null);
  }, [journey]);

  useEffect(() => {
    if (journey)
      document.title = `Hermit — ${journey.stops.length} stops, ${journey.stats.favors_done ?? 0} favors`;
  }, [journey]);

  const chooseSource = (s: JourneySource): void => {
    setWant(s);
    const url = new URL(location.href);
    url.searchParams.set('data', s);
    history.replaceState(null, '', url);
  };

  const pick = (i: number): void => {
    const id = derived?.rawPieces[i]?.id;
    const stop = id ? derived?.stopByPiece.get(id) : undefined;
    if (!stop) return;
    if (friend && friend !== stop.host) setFriend(null);
    setFlashStop(stop.stop_id);
    sound.play('quest');
    window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setFlashStop(null), 1600);
    requestAnimationFrame(() =>
      document
        .getElementById(`stop-${stop.stop_id}`)
        ?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' }),
    );
  };

  const pieceId = activePiece != null ? (derived?.rawPieces[activePiece]?.id ?? null) : null;

  return (
    <div className="page">
      <a className="skip" href="#log">
        Skip to the quest log
      </a>
      <Header
        derived={derived}
        pieces={derived?.pieces ?? []}
        source={source}
        dark={dark}
        onTheme={toggle}
        onSource={chooseSource}
      />

      <section className="welcome" aria-labelledby="welcome-title">
        <div className="welcome__copy">
          <span className="welcome__eyebrow">A little creature. A shared adventure.</span>
          <h1 id="welcome-title">
            Small favors.
            <br />A shell full of stories.
          </h1>
          <p>
            Meet Tilli, your wandering companion. One friend at a time, one little kindness after
            another — every stop becomes part of the journey.
          </p>
          <a className="welcome__link" href="#log">
            Explore the journey <span aria-hidden="true">↗</span>
          </a>
          <span className="welcome__note">Made of moments together.</span>
        </div>
        <figure className="welcome__portrait">
          <div className="welcome__art">
            <img
              src={`${import.meta.env.BASE_URL}assets/tilli.jpeg`}
              alt="Tilli, a cheerful yellow creature with leaf ears, nestled in a sage shell with a heart and flower charm"
              width="1241"
              height="1268"
              fetchPriority="high"
            />
          </div>
          <figcaption>Your next little adventure starts with hello.</figcaption>
        </figure>
      </section>

      {error && (
        <PixelBox variant="quest" className="notice" role="alert">
          <HermitSprite animation="surprised" scale={2} />
          <p>
            Hermit couldn’t find its journey. <code>{error}</code>
          </p>
        </PixelBox>
      )}

      {!journey && !error && (
        <div className="loading" role="status">
          <HermitSprite animation="walk" scale={3} />
          <span>Following Hermit’s footprints…</span>
        </div>
      )}

      {journey && derived && (
        <main className="layout">
          <PixelBox as="section" tab="Journey" className="panel panel--world" aria-label="Map">
            <div className="intro">
              <p>
                <strong>Hermit has no home.</strong> It lives on one friend’s laptop at a time,
                borrowing their AI as a brain, and moves on when they go idle. Each friend leaves a
                favor for the next; each favor done adds a piece to the shell.
              </p>
            </div>
            <WorldPanel
              derived={derived}
              stops={journey.stops}
              dark={dark}
              reduced={reduced}
              currentHost={journey.hermit.current_host}
              selectedHost={friend}
              onSelectHost={setFriend}
            />
          </PixelBox>

          <ShellPanel
            derived={derived}
            active={activePiece}
            onActive={setActivePiece}
            onPick={pick}
            narrow={narrow}
          />
          <ImpactPanel journey={journey} derived={derived} />

          <div id="log" className="log-wrap">
            <QuestLog
              derived={derived}
              generatedAt={journey.generated_at}
              friend={friend}
              onFriend={setFriend}
              activePiece={pieceId}
              flashStop={flashStop}
            />
          </div>

          <footer className="foot">
            <PostcardButton journey={journey} derived={derived} sample={source !== 'live'} />
            <p className="foot__privacy">
              <strong>Privacy:</strong> area-level places only, typed by each friend into their own
              config. No addresses, no tracking, and nothing from anyone’s window folder ever
              reaches this page.
            </p>
            <p className="foot__meta">
              Exported {new Date(journey.generated_at).toLocaleString()} ·{' '}
              {journey.stats.handoffs ?? 0} handoffs · built on Switch
            </p>
          </footer>
        </main>
      )}
    </div>
  );
}
