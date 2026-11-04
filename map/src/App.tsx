/**
 * The journey map. Owner: C, Phase 7.
 *
 * Where Hermit has been, what friends did for each other, and the shell they
 * built. Reads `data/journey.json` (falls back to the committed sample).
 */
import {
  PixelBox,
  PixelButton,
  PocketHermit,
  sound,
  useMediaQuery,
  useReducedMotion,
} from '@hermit/ui';
import { useEffect, useMemo, useRef, useState } from 'react';

import { requestedKeeper, useGroup } from './hooks/useGroup';
import { requestedScenario, scenarioById, useJourney, type ScenarioId } from './hooks/useJourney';
import { useTheme } from './hooks/useTheme';
import { derive } from './lib/derive';
import { Header } from './sections/Header';
import { ImpactPanel } from './sections/ImpactPanel';
import { LivePanel } from './sections/LivePanel';
import { MascotStage } from './sections/MascotStage';
import { PostcardButton } from './sections/Postcard';
import { QuestLog } from './sections/QuestLog';
import { ShellPanel } from './sections/ShellPanel';
import { WorldPanel } from './world/WorldPanel';

/** The live panel only makes sense where a keeper could answer: this machine. */
function onLoopback(): boolean {
  if (typeof location === 'undefined') return false;
  return ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
}

export function App() {
  const [want, setWant] = useState<ScenarioId | null>(requestedScenario);
  const { journey, source, kind, error, loading, retry } = useJourney(want);
  const scenario = scenarioById(want);
  // Live group status is a separate feed from the exported journey, on purpose.
  const keeper = requestedKeeper();
  const live = useGroup(keeper);
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
      document.title = `${kind === 'simulation' ? '[SIMULATION] ' : ''}Hermit — ${journey.stops.length} stops, ${derived?.favorsDone ?? 0} favors`;
  }, [journey, kind, derived]);

  const chooseScenario = (s: ScenarioId): void => {
    setWant(s);
    const url = new URL(location.href);
    url.searchParams.delete('data');
    url.searchParams.set('journey', s);
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
      {kind === 'simulation' && (
        <div className="sim-stamp" aria-hidden>
          SIMULATION
        </div>
      )}
      <Header
        derived={derived}
        journey={journey}
        kind={kind}
        source={source}
        scenario={scenario.id}
        dark={dark}
        onTheme={toggle}
        onScenario={chooseScenario}
      />

      <MascotStage derived={derived} />

      {(live.keeper || onLoopback()) && (
        <LivePanel group={live.group} error={live.error} keeper={live.keeper} />
      )}

      {error && !journey && (
        <PixelBox variant="quest" className="notice" role="alert">
          <PocketHermit mood="offline" size={96} label="" />
          <div className="notice__text">
            <p>
              <strong>Hermit couldn’t find this journey.</strong> <code>{error}</code>
            </p>
            <div className="notice__actions">
              <PixelButton size="sm" icon="fit" onClick={retry}>
                Try again
              </PixelButton>
              {scenario.id !== 'bengaluru' && (
                <PixelButton size="sm" variant="ghost" onClick={() => chooseScenario('bengaluru')}>
                  Show the Bengaluru journey
                </PixelButton>
              )}
            </div>
          </div>
        </PixelBox>
      )}

      {!journey && !error && loading && (
        <div className="loading" role="status">
          <PocketHermit mood="away" size={140} label="" />
          <span>Following Hermit’s footprints…</span>
        </div>
      )}

      {journey && derived && (
        <main className="layout">
          <PixelBox
            as="section"
            tab="Journey"
            id="journey"
            className="panel panel--world"
            aria-label="Map"
          >
            <div className="intro">
              <p>
                <strong>Where Hermit has wandered.</strong> Each house is a friend; the dotted trail
                is every hop between laptops, coloured by how Hermit left. Click a house to see only
                that friend’s stops.
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
              simulated={kind === 'simulation'}
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
            <PostcardButton journey={journey} derived={derived} kind={kind ?? 'sample'} />
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
