/**
 * "Hermit's menu" — a cozy pocket companion. Owner: C. plan.md §6.4.
 * Hermit + status, then Quest / Log / Shell / Friends tabs, then Open chat and
 * I'm busy. Hermit's pose mirrors what is happening: visiting, asleep, away.
 */
import { BrainBadge, DialogBox, formatDay, formatDwell, formatSpan, PixelAvatar, PixelButton, PixelTabs, PocketHermit, QuestCard, soulAction, soulStatus, ShellView, sound, Ticker, type BrainProvider, type Mood, moodFor, moodLine } from '@hermit/ui';
import { useEffect, useMemo, useState } from 'react';

import { bridge } from '../shared/bridge';
import { titleCase, toPieceInputs } from '../shared/pieces';
import { isSleepyHour } from '../shared/reduce';
import { useKeeper } from '../shared/store';

export function PanelWindow() {
  const k = useKeeper();
  // One request at a time, whichever it is. Separate flags let you fire a
  // claim while a departure was still settling.
  const [busy, setBusy] = useState(false);

  const [actionError, setActionError] = useState<string | null>(null);
  const [favorText, setFavorText] = useState('');
  const [favorBusy, setFavorBusy] = useState(false);
  const [favorFeedback, setFavorFeedback] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [noteBusy, setNoteBusy] = useState(false);
  const [noteFeedback, setNoteFeedback] = useState<string | null>(null);
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

  // What the one button does right now, derived from live state rather than
  // from what was last clicked.
  const action = soulAction({
    connected: k.connected,
    state: k.state,
    soulHolder: k.soulHolder,
    host: k.hostId,
    busy,
  });

  const run = async (): Promise<void> => {
    if (busy || action.kind === 'none') return;
    setBusy(true);
    setActionError(null);
    try {
      if (action.kind === 'send') await k.depart();
      else await k.claim();
    } catch {
      setActionError(
        action.kind === 'send'
          ? 'Couldn’t send your goodbye. Please try again.'
          : 'Couldn’t ask for Hermit. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  };
  const myBrain: BrainProvider =
    [...k.shell].reverse().find((p) => p.host === k.hostId)?.brain_provider ?? 'other';
  const ticker = !k.connected
    ? 'Keeper offline · retrying'
    : mine
      ? `With you${k.since ? ` · ${formatSpan(k.since, now).toLowerCase()}` : ''}`
      : k.soulHolder
        ? `Visiting ${titleCase(k.soulHolder)}`
        : 'Asleep · nobody around';
  const sleepy = isSleepyHour(new Date(now));
  const heroMood: Mood = moodFor({
    state: k.state,
    present: k.present,
    soulHolder: k.soulHolder,
    host: k.hostId ?? '',
    connected: k.connected,
  });
  const heroLine = !k.connected
    ? 'I can’t find my keeper… is it running?'
    : !mine
      ? k.soulHolder
        ? `I’m off visiting ${titleCase(k.soulHolder)}. Back soon!`
        : 'Everyone’s asleep, so I am too.'
      : sleepy
        ? 'It’s late — I’ll nap until you’re done.'
        : k.favorPending
          ? 'I brought you a little favor!'
          : 'Cozy here. Thanks for having me.';

  const favor = k.favorPending as { id?: string; text?: string; left_by?: string; status?: string } | null;
  const runFavor = async (kind: 'leave' | 'complete'): Promise<void> => {
    if (favorBusy) return;
    setFavorBusy(true);
    setFavorFeedback(null);
    try {
      if (kind === 'leave') {
        await k.leaveFavor(favorText.trim());
        setFavorText('');
        setFavorFeedback('Hermit is carrying your favor to the next friend.');
      } else if (favor?.id) {
        await k.completeFavor(favor.id);
        setFavorFeedback('Favor complete! A piece was added to the shared shell.');
      }
    } catch (error) {
      setFavorFeedback(error instanceof Error ? error.message : 'Please try again.');
    } finally {
      setFavorBusy(false);
    }
  };
  const runNote = async (): Promise<void> => {
    if (noteBusy) return;
    setNoteBusy(true);
    setNoteFeedback(null);
    try {
      const to = await k.sendNote(noteText.trim());
      setNoteText('');
      setNoteFeedback(`Sent to ${titleCase(to)} through Switch.`);
    } catch (error) {
      setNoteFeedback(error instanceof Error ? error.message : 'Please try again.');
    } finally {
      setNoteBusy(false);
    }
  };
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
        <span className="menu__title">Hermit’s menu</span>
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

      <section className="menu__hero" aria-label="Hermit right now">
        <div className={`menu__portrait menu__portrait--${heroMood}`}>
          <PocketHermit mood={heroMood} size={118} label={moodLine(heroMood, k.soulHolder, k.hostId ?? '')} />
        </div>
        <div className="menu__status">
          <p className="menu__line">{heroLine}</p>
          <Ticker live={mine}>{ticker}</Ticker>
        </div>
      </section>

      <dl className="menu__facts">
        <div>
          <dt>Brain</dt>
          <dd>
            <BrainBadge provider={myBrain} short />
          </dd>
        </div>
        <div>
          <dt>Shell</dt>
          <dd className="menu__big">{pieces.length}</dd>
        </div>
        <div>
          <dt>Host</dt>
          <dd>{k.hostId ? titleCase(k.hostId) : '—'}</dd>
        </div>
      </dl>

      <PixelTabs
        label="Hermit's menu"
        tabs={[
          {
            id: 'quest',
            label: 'Quest',
            badge: favor ? <span className="menu__dot" aria-label="one quest" /> : undefined,
            content: (
              <div className="menu__quest">
                {favor?.text ? (
                  <>
                    <QuestCard
                      text={favor.text}
                      from={favor.left_by ? titleCase(favor.left_by) : 'Hermit'}
                      status={(favor.status as 'open' | 'assigned' | 'done' | 'expired') ?? 'assigned'}
                      reward={reward}
                    />
                    <PixelButton disabled={favorBusy || !mine || !favor.id} onClick={() => void runFavor('complete')}>
                      I did it · grow the shell
                    </PixelButton>
                  </>
                ) : (
                  <p className="menu__empty">No favor right now. Leave a small task for the next friend Hermit visits.</p>
                )}
                {mine && !favor && (
                  <form onSubmit={(event) => { event.preventDefault(); void runFavor('leave'); }}>
                    <label htmlFor="favor-text">A little favor for the next friend</label>
                    <textarea id="favor-text" maxLength={280} minLength={3} value={favorText}
                      onChange={(event) => setFavorText(event.target.value)}
                      placeholder="Share one song that helped you focus today" />
                    <PixelButton type="submit" disabled={favorBusy || favorText.trim().length < 3}>
                      Leave a favor
                    </PixelButton>
                  </form>
                )}
                {favorFeedback && <p className="menu__feedback" role="status">{favorFeedback}</p>}
              </div>
            ),
          },
          {
            id: 'log',
            label: 'Log',
            content: k.lines.length ? (
              <ol className="menu__log">
                {[...k.lines].reverse().map((l) => (
                  <li key={l.ts + l.text}>
                    <DialogBox
                      text={l.text}
                      name="HERMIT"
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
            id: 'shell',
            label: 'Shell',
            content: pieces.length ? (
              <div className="menu__shell">
                <ShellView pieces={pieces} size={48} scale={3} label="The shell so far" />
                <p>
                  {pieces.length} piece{pieces.length === 1 ? '' : 's'} so far — one for every favor
                  a friend finished.
                </p>
              </div>
            ) : (
              <p className="menu__empty">No shell pieces yet. The first favor done adds one.</p>
            ),
          },
          {
            id: 'friends',
            label: 'Friends',
            content: (
              <div className="menu__quest">
                {!mine && k.soulHolder && k.connected && (
                  <form onSubmit={(event) => { event.preventDefault(); void runNote(); }}>
                    <label htmlFor="friend-note">Send a little note to {titleCase(k.soulHolder)}</label>
                    <textarea id="friend-note" maxLength={280} minLength={3} value={noteText}
                      onChange={(event) => setNoteText(event.target.value)}
                      placeholder="Hey, how is your day going?" />
                    <PixelButton type="submit" disabled={noteBusy || noteText.trim().length < 3}>Send through Switch</PixelButton>
                  </form>
                )}
                {noteFeedback && <p className="menu__feedback" role="status">{noteFeedback}</p>}
                {friends.length ? (
                  <ul className="menu__friends">
                    {friends.map(([id, f]) => (
                      <li key={id}>
                        <PixelAvatar hostId={id} scale={3} name={titleCase(id)} />
                        <span className="menu__friend">
                          <strong>{titleCase(id)}{id === k.hostId ? ' (you)' : ''}</strong>
                          <span>{f.pieces} piece{f.pieces === 1 ? '' : 's'} · {formatDwell(f.dwell)} hosted · last {formatDay(f.last)}</span>
                        </span>
                        <BrainBadge provider={f.brain} short />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="menu__empty">The shared shell will remember each friend who completes a favor.</p>
                )}
              </div>
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
          Open chat
        </PixelButton>
        <PixelButton
          variant={action.tone}
          icon="play"
          disabled={action.disabled}
          title={action.hint ?? undefined}
          aria-disabled={action.disabled}
          onClick={() => void run()}
        >
          {action.label}
        </PixelButton>
      </footer>
      <p className="panel__hint" aria-live="polite">
        {actionError ?? action.hint ?? soulStatus(k.connected, k.soulHolder, k.hostId)}
      </p>
    </div>
  );
}
