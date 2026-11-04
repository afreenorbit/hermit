/**
 * "Hermit's menu" — a tiny handheld game menu. Owner: C. plan.md §6.4.
 * Shell + brain, then QUEST / LOG / FRIENDS tabs, then OPEN CHAT and I'M BUSY.
 */
import {
  BrainBadge,
  DialogBox,
  formatDay,
  formatDwell,
  formatSpan,
  HermitSprite,
  PixelAvatar,
  PixelButton,
  PixelTabs,
  QuestCard,
  ShellView,
  sound,
  Ticker,
  type BrainProvider,
} from '@hermit/ui';
import { useEffect, useMemo, useState } from 'react';

import { bridge } from '../shared/bridge';
import { titleCase, toPieceInputs } from '../shared/pieces';
import { useKeeper } from '../shared/store';

export function PanelWindow() {
  const k = useKeeper();
  const [departing, setDeparting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const depart = async (): Promise<void> => {
    if (departing) return;
    setDeparting(true);
    setActionError(null);
    try {
      await k.depart();
    } catch {
      setActionError('Couldn’t send your goodbye. Please try again.');
    } finally {
      setDeparting(false);
    }
  };
  const { start } = k;
  useEffect(() => start(), [start]);

  const [soundOn, setSoundOn] = useState(sound.isEnabled());
  useEffect(() => sound.subscribe(setSoundOn), []);
  useEffect(() => bridge.on('sound', (v) => setSoundOn(!!v)), []);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') bridge.panel(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const pieces = useMemo(() => toPieceInputs(k.shell), [k.shell]);
  const mine = k.hostId != null && k.soulHolder === k.hostId;
  const myBrain: BrainProvider =
    [...k.shell].reverse().find((p) => p.host === k.hostId)?.brain_provider ?? 'other';
  const ticker = !k.connected
    ? 'KEEPER OFFLINE · RETRYING'
    : mine
      ? `WITH YOU${k.since ? ` · ${formatSpan(k.since, now)}` : ''}`
      : k.soulHolder
        ? `WITH ${k.soulHolder.toUpperCase()}`
        : 'ASLEEP · NOBODY AROUND';

  const favor = k.favorPending as { text?: string; left_by?: string; status?: string } | null;
  const reward = useMemo(
    () =>
      favor && k.hostId
        ? {
            id: 'preview',
            brain_provider: myBrain,
            temp_c: k.shell[k.shell.length - 1]?.temp_c ?? null,
            dwell_s: k.since ? Math.max(600, (now - Date.parse(k.since)) / 1000) : 1800,
            departure: 'graceful' as const,
            seed: 7,
            local_hour: new Date().getHours(),
          }
        : null,
    [favor, k.hostId, myBrain, k.shell, k.since, now],
  );

  const friends = useMemo(() => {
    const by = new Map<
      string,
      { pieces: number; last: string; brain: BrainProvider; dwell: number }
    >();
    for (const p of k.shell) {
      const f = by.get(p.host) ?? {
        pieces: 0,
        last: p.created_at,
        brain: p.brain_provider,
        dwell: 0,
      };
      f.pieces += 1;
      f.dwell += p.dwell_s;
      if (p.created_at > f.last) f.last = p.created_at;
      f.brain = p.brain_provider;
      by.set(p.host, f);
    }
    return [...by.entries()].sort((a, b) => b[1].last.localeCompare(a[1].last));
  }, [k.shell]);

  return (
    <div className="menu">
      <header className="menu__bar">
        <span className="menu__title">HERMIT’S MENU</span>
        <div className="menu__tools">
          <PixelButton
            variant="ghost"
            size="sm"
            icon={soundOn ? 'sound' : 'mute'}
            label={soundOn ? 'Mute sound' : 'Turn sound on'}
            aria-pressed={soundOn}
            onClick={() => sound.setEnabled(!soundOn)}
          />
          <PixelButton
            variant="ghost"
            size="sm"
            icon="close"
            label="Close menu"
            onClick={() => bridge.panel(false)}
          />
        </div>
      </header>

      <Ticker live={mine}>{ticker}</Ticker>

      <section className="menu__hero" aria-label="Hermit's shell">
        <div className="menu__shell">
          {pieces.length ? (
            <ShellView pieces={pieces} size={48} scale={3} label="Hermit's shell" />
          ) : (
            <HermitSprite animation="idle" scale={3} />
          )}
        </div>
        <dl className="menu__facts">
          <div>
            <dt>BRAIN</dt>
            <dd>
              <BrainBadge provider={myBrain} />
            </dd>
          </div>
          <div>
            <dt>PIECES</dt>
            <dd className="menu__big">{pieces.length}</dd>
          </div>
          <div>
            <dt>HOST</dt>
            <dd>{k.hostId ? titleCase(k.hostId) : '—'}</dd>
          </div>
        </dl>
      </section>

      <PixelTabs
        label="Hermit's menu"
        tabs={[
          {
            id: 'quest',
            label: 'QUEST',
            badge: favor ? <span className="menu__dot" aria-label="one quest" /> : undefined,
            content: favor?.text ? (
              <QuestCard
                text={favor.text}
                from={favor.left_by ? titleCase(favor.left_by) : 'Hermit'}
                status={(favor.status as 'open' | 'assigned' | 'done' | 'expired') ?? 'assigned'}
                reward={reward}
              />
            ) : (
              <p className="menu__empty">No quest right now. Hermit is just happy to be here.</p>
            ),
          },
          {
            id: 'log',
            label: 'LOG',
            content: k.lines.length ? (
              <ol className="menu__log">
                {[...k.lines].reverse().map((l) => (
                  <li key={l.ts + l.text}>
                    <DialogBox
                      text={l.text}
                      compact
                      speed={1000}
                      badge={<BrainBadge provider={myBrain} short />}
                    />
                  </li>
                ))}
              </ol>
            ) : (
              <p className="menu__empty">Hermit hasn’t said anything here yet.</p>
            ),
          },
          {
            id: 'friends',
            label: 'FRIENDS',
            content: friends.length ? (
              <ul className="menu__friends">
                {friends.map(([id, f]) => (
                  <li key={id}>
                    <PixelAvatar hostId={id} scale={3} name={titleCase(id)} />
                    <span className="menu__friend">
                      <strong>
                        {titleCase(id)}
                        {id === k.hostId ? ' (you)' : ''}
                      </strong>
                      <span>
                        {f.pieces} piece{f.pieces === 1 ? '' : 's'} · {formatDwell(f.dwell)} hosted
                        · last {formatDay(f.last)}
                      </span>
                    </span>
                    <BrainBadge provider={f.brain} short />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="menu__empty">Nobody has finished a favor yet.</p>
            ),
          },
        ]}
      />

      {actionError && (
        <p className="menu__error" role="alert">
          {actionError}
        </p>
      )}
      <footer className="menu__actions">
        <PixelButton
          variant="ghost"
          icon="chat"
          disabled={!bridge.chatUrl}
          title={
            bridge.chatUrl
              ? 'Open the den in Discord'
              : 'Set HERMIT_CHAT_URL to your Discord channel'
          }
          onClick={() => bridge.chatUrl && bridge.openExternal(bridge.chatUrl)}
        >
          OPEN CHAT
        </PixelButton>
        <PixelButton
          variant="danger"
          icon="play"
          disabled={!mine || departing || !k.connected}
          onClick={() => void depart()}
        >
          {departing ? 'SAYING GOODBYE…' : 'I’M BUSY — GO'}
        </PixelButton>
      </footer>
    </div>
  );
}
