/** One card per stop, newest first, with filters. Owner: C. plan.md §7.5. */
import { BrainBadge, DepartureChip, formatClock, formatDay, formatSpan, formatTemp, PixelAvatar, PixelBox, PixelCanvas, PixelIcon, PixelToggleGroup, PocketHermit, QuestCard, renderShellGrid, type BrainProvider, weatherInfo } from '@hermit/ui';
import type { StopT } from '@hermit/ui/contracts';
import { useEffect, useMemo, useRef, useState } from 'react';

import { nameOf, type Derived } from '../lib/derive';

const BRAIN_SHORT: Record<BrainProvider, string> = {
  'claude-code': 'Claude',
  codex: 'Codex',
  opencode: 'OpenCode',
  other: 'Other',
};

interface Props {
  derived: Derived;
  generatedAt: string;
  friend: string | null;
  onFriend: (f: string | null) => void;
  activePiece: string | null;
  flashStop: string | null;
}

export function QuestLog({
  derived,
  generatedAt,
  friend,
  onFriend,
  activePiece,
  flashStop,
}: Props) {
  const [brain, setBrain] = useState<string>('all');
  const [doneOnly, setDoneOnly] = useState(false);
  const firstPaint = useRef(true);
  useEffect(() => {
    const t = window.setTimeout(() => (firstPaint.current = false), 1200);
    return () => window.clearTimeout(t);
  }, []);

  const stops = useMemo(
    () =>
      derived.stopsNewestFirst.filter((s) => {
        if (friend && s.host !== friend) return false;
        if (brain !== 'all' && derived.hosts.get(s.host)?.brain_provider !== brain) return false;
        if (doneOnly && !derived.receivedDone(s)) return false;
        return true;
      }),
    [derived, friend, brain, doneOnly],
  );

  const brains = useMemo(
    () => [...new Set([...derived.hosts.values()].map((h) => h.brain_provider))] as BrainProvider[],
    [derived],
  );

  return (
    <PixelBox as="section" tab="Quest log" className="panel panel--log" aria-labelledby="log-h">
      <h2 id="log-h" className="hm-sr">
        Quest log — every stop Hermit made
      </h2>
      <div className="filters">
        <div className="filters__group">
          <span className="filters__label">Friend</span>
          <PixelToggleGroup
            label="Filter by friend"
            value={friend ?? 'all'}
            onValueChange={(v) => onFriend(v === 'all' ? null : v)}
            items={[
              { value: 'all', label: 'All' },
              ...derived.hostIds.map((id) => ({
                value: id,
                label: (
                  <>
                    <PixelAvatar hostId={id} scale={2} framed={false} />
                    {nameOf(derived, id)}
                  </>
                ),
              })),
            ]}
          />
        </div>
        <div className="filters__group">
          <span className="filters__label">Brain</span>
          <PixelToggleGroup
            label="Filter by brain"
            value={brain}
            onValueChange={setBrain}
            items={[
              { value: 'all', label: 'All' },
              ...brains.map((b) => ({ value: b, label: BRAIN_SHORT[b] })),
            ]}
          />
        </div>
        <div className="filters__group">
          <PixelToggleGroup
            label="Completed favors only"
            value={doneOnly ? 'done' : 'any'}
            onValueChange={(v) => setDoneOnly(v === 'done')}
            items={[
              { value: 'any', label: 'Every stop' },
              {
                value: 'done',
                label: (
                  <>
                    <PixelIcon name="check" /> Favor done
                  </>
                ),
              },
            ]}
          />
        </div>
        <span className="filters__count" aria-live="polite">
          {stops.length} of {derived.stopsNewestFirst.length} stops
        </span>
      </div>

      {derived.stopsNewestFirst.length === 0 ? (
        <div className="empty empty--big">
          <PocketHermit mood="sleeping" size={150} label="" />
          <p>Hermit hasn’t left its first laptop yet.</p>
        </div>
      ) : stops.length === 0 ? (
        <div className="empty">
          <p>No stops match these filters.</p>
        </div>
      ) : (
        <ol className="log" data-testid="quest-log">
          {stops.map((s, i) => (
            <StopCard
              key={s.stop_id}
              stop={s}
              derived={derived}
              generatedAt={generatedAt}
              lit={!!activePiece && derived.pieceOfStop.get(s.stop_id) === activePiece}
              flash={flashStop === s.stop_id}
              delay={firstPaint.current ? i * 60 : 0}
            />
          ))}
        </ol>
      )}
    </PixelBox>
  );
}

function StopCard({
  stop,
  derived,
  generatedAt,
  lit,
  flash,
  delay,
}: {
  stop: StopT;
  derived: Derived;
  generatedAt: string;
  lit: boolean;
  flash: boolean;
  delay: number;
}) {
  const host = derived.hosts.get(stop.host);
  const pid = derived.pieceOfStop.get(stop.stop_id);
  const idx = pid ? derived.pieceIndex.get(pid) : undefined;
  const piece = idx != null ? derived.pieces[idx] : undefined;
  const mini = useMemo(() => (piece ? renderShellGrid([piece], { size: 24 }) : null), [piece]);
  const w = weatherInfo(stop.weather?.code);
  const recv = stop.favor_received;
  const left = stop.favor_left;

  return (
    <li
      id={`stop-${stop.stop_id}`}
      className={`stop${lit ? ' is-lit' : ''}${flash ? ' is-flash' : ''}`}
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      <header className="stop__head">
        <span className="stop__seq">#{stop.seq}</span>
        <PixelAvatar hostId={stop.host} scale={3} name={host?.display_name} />
        <span className="stop__who">
          <strong>{nameOf(derived, stop.host)}</strong>
          <span>{host?.city}</span>
        </span>
        {mini && (
          <span className="stop__piece" title="The shell piece from this stop">
            <PixelCanvas grid={mini} scale={2} label="Shell piece from this stop" />
          </span>
        )}
      </header>

      <div className="stop__chips">
        {host && <BrainBadge provider={host.brain_provider} short />}
        <DepartureChip departure={stop.departure} />
      </div>

      <dl className="stop__meta">
        <div>
          <dt>Arrived</dt>
          <dd>
            <time dateTime={stop.arrived_at}>
              {formatDay(stop.arrived_at)} · {formatClock(stop.arrived_at)}
            </time>
          </dd>
        </div>
        <div>
          <dt>Stayed</dt>
          <dd>{formatSpan(stop.arrived_at, stop.left_at ?? generatedAt)}</dd>
        </div>
        <div>
          <dt>Weather</dt>
          <dd className="stop__weather">
            <PixelIcon name={w.icon} label={w.label.toLowerCase()} />
            {formatTemp(stop.weather?.temp_c)}
          </dd>
        </div>
      </dl>

      {recv?.text ? (
        <QuestCard
          compact
          text={recv.text}
          from={nameOf(derived, recv.left_by)}
          status={derived.receivedDone(stop) ? 'done' : (recv.status ?? 'assigned')}
        />
      ) : (
        <p className="stop__none">
          {stop.seq === 1
            ? 'First stop — nothing to carry yet.'
            : 'Arrived empty-clawed. No favor to deliver.'}
        </p>
      )}

      {left?.text ? (
        <p className="stop__left">
          <span>Left for the next friend</span> “{left.text}”
        </p>
      ) : stop.departure === 'abrupt' ? (
        <p className="stop__left stop__left--abrupt">
          <span>Left in a hurry</span> no time to leave a favor
        </p>
      ) : null}
    </li>
  );
}
