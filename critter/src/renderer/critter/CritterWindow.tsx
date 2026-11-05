/**
 * Hermit on the desktop — on every laptop in the group, not only the host.
 *
 *   SOUL_CLAIMED (me)      waddle in from the edge → wave with a letter (curious if abrupt)
 *   idle                   visiting: breathes, blinks, eyes follow the cursor
 *   new den line           chatter while the bubble types, stays 7s
 *   FAVOR_ASSIGNED (me)    a little letter badge bobbing beside Hermit
 *   SHELL_PIECE_ADDED      celebrate with sparkles; the shell badge grows
 *   after 00:30            tucked into the shell asleep, zzz, lilac bubble
 *   DEPARTURE / RELEASED   wave → turn around → walk off the other edge → hide
 *   reduced motion         fades only, still poses, instant text
 */
import {
  DialogBox,
  type Mood,
  moodFor,
  moodLine,
  PixelCanvas,
  PocketHermit,
  renderShellGrid,
  sound,
  useReducedMotion,
} from '@hermit/ui';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';

import { bridge } from '../shared/bridge';
import { toPieceInputs } from '../shared/pieces';
import { isSleepyHour } from '../shared/reduce';
import { useKeeper } from '../shared/store';

const WALK_PX = 220;
const SPRITE = 150;

export function CritterWindow() {
  const k = useKeeper();
  const reduced = useReducedMotion();
  const pieces = useMemo(() => toPieceInputs(k.shell), [k.shell]);
  const shellGrid = useMemo(() => renderShellGrid(pieces, { size: 24 }), [pieces]);
  const [x, setX] = useState(0);
  const [act, setAct] = useState<{ mood: Mood | null; flip: boolean }>({
    mood: null,
    flip: false,
  });
  const [effect, setEffect] = useState<'dust' | null>(null);
  const [line, setLine] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);
  const [sleepy, setSleepy] = useState(isSleepyHour());
  const [faded, setFaded] = useState(false);
  const spriteRef = useRef<HTMLDivElement>(null);

  const { start, arrived, left } = k;
  useEffect(() => start(), [start]);

  // sound preference is shared with the tray menu
  useEffect(() => {
    bridge.soundState(sound.isEnabled());
    const offToggle = bridge.on('sound-toggle', () => sound.setEnabled(!sound.isEnabled()));
    const offSub = sound.subscribe((on) => bridge.soundState(on));
    return () => {
      offToggle();
      offSub();
    };
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => setSleepy(isSleepyHour()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  // Every laptop shows its local state, including waiting, sleeping and offline.
  useEffect(() => {
    bridge.setVisible(true);
  }, [k.phase]);

  // --- arrival ---------------------------------------------------------------
  useEffect(() => {
    if (k.phase !== 'arriving') return;
    const timers: number[] = [];
    const later = (ms: number, fn: () => void): void => void timers.push(window.setTimeout(fn, ms));
    if (reduced) {
      setX(0);
      setFaded(true);
      later(30, () => setFaded(false));
      later(450, arrived);
    } else {
      setAct({ mood: 'away', flip: true });
      setX(WALK_PX);
      for (let i = 1; i <= 16; i++) later(i * 100, () => setX(Math.round(WALK_PX * (1 - i / 16))));
      later(1650, () => {
        setAct({ mood: 'arriving', flip: false });
        setEffect('dust');
      });
      later(k.abrupt ? 3400 : 3200, () => {
        setEffect(null);
        setAct({ mood: null, flip: false });
        arrived();
      });
    }
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [k.phase, k.abrupt, reduced, arrived]);

  // --- departure -------------------------------------------------------------
  useEffect(() => {
    if (k.phase !== 'leaving') return;
    const timers: number[] = [];
    const later = (ms: number, fn: () => void): void => void timers.push(window.setTimeout(fn, ms));
    setLine(null);
    if (reduced) {
      setFaded(true);
      later(450, () => {
        setFaded(false);
        left();
      });
    } else {
      setAct({ mood: 'away', flip: false });
      later(1400, () => setAct({ mood: 'away', flip: true }));
      for (let i = 1; i <= 18; i++)
        later(1400 + i * 100, () => setX(-Math.round((WALK_PX * i) / 18)));
      later(3300, () => {
        setX(0);
        setAct({ mood: null, flip: false });
        left();
      });
    }
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [k.phase, reduced, left]);

  // --- shell piece -------------------------------------------------------------
  const seenCelebrate = useRef(k.celebrate);
  useEffect(() => {
    if (k.celebrate === seenCelebrate.current) return;
    seenCelebrate.current = k.celebrate;
    if (k.phase !== 'here') return;
    setAct({ mood: 'visiting', flip: false });
    const t = window.setTimeout(() => setAct({ mood: null, flip: false }), 1800);
    return () => window.clearTimeout(t);
  }, [k.celebrate, k.phase]);

  // --- talking -----------------------------------------------------------------
  useEffect(() => {
    if (k.phase !== 'here' && k.phase !== 'arriving') return;
    if (!k.lastLine) return;
    const text = k.lastLine.length > 140 ? `${k.lastLine.slice(0, 139)}…` : k.lastLine;
    setLine(text);
    setTyping(true);
  }, [k.lastLine, k.phase]);

  useEffect(() => {
    if (!line || typing) return;
    const t = window.setTimeout(() => setLine(null), 7000);
    return () => window.clearTimeout(t);
  }, [line, typing]);

  // --- pointer: click-through off over the sprite, drag, click for the menu ----
  const down = useRef<{ x: number; y: number } | null>(null);
  // Capture is a dead-man's switch in the main process: it expires unless we
  // keep saying the pointer is still here. onPointerMove is the heartbeat, so
  // a missed `leave` costs at most a second of grip instead of locking the
  // desktop.
  const hover = {
    onPointerEnter: () => bridge.setMouseOver(true),
    onPointerMove: () => bridge.setMouseOver(true),
    onPointerLeave: () => {
      if (!down.current) bridge.setMouseOver(false);
    },
  };
  // Belt and braces: a transparent always-on-top window can miss the leave
  // event on the sprite, and then it keeps swallowing clicks for the whole
  // desktop. Releasing on window-leave means the worst case is one stuck
  // frame, not an unusable screen. (pointerleave-window)
  useEffect(() => {
    const release = (): void => {
      if (!down.current) bridge.setMouseOver(false);
    };
    window.addEventListener('pointerleave', release);
    window.addEventListener('blur', release);
    return () => {
      window.removeEventListener('pointerleave', release);
      window.removeEventListener('blur', release);
    };
  }, []);

  // A click opens the menu; only a real drag moves the window. Starting the
  // drag on pointerdown meant every click set the window chasing the cursor,
  // and a missed pointerup left it under the pointer eating every click.
  const dragging = useRef(false);
  const DRAG_THRESHOLD_PX = 4;
  const endPress = (openMenu: boolean): void => {
    const wasDragging = dragging.current;
    down.current = null;
    dragging.current = false;
    if (wasDragging) bridge.dragEnd();
    if (openMenu && !wasDragging) bridge.panel(true);
  };
  const onDown = (e: PointerEvent<HTMLDivElement>): void => {
    if (e.button !== 0) return;
    down.current = { x: e.screenX, y: e.screenY };
    dragging.current = false;
    // Keep the press's pointerup coming to us even if the window moves.
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>): void => {
    // Also the grip heartbeat (see `hover`): this handler replaces hover's own
    // onPointerMove on the sprite, so it must keep re-asserting the grip.
    bridge.setMouseOver(true);
    const d = down.current;
    if (!d || dragging.current) return;
    if (Math.abs(e.screenX - d.x) + Math.abs(e.screenY - d.y) >= DRAG_THRESHOLD_PX) {
      dragging.current = true;
      bridge.dragStart();
    }
  };
  const onUp = (e: PointerEvent<HTMLDivElement>): void => {
    if (!down.current) return;
    if (e.currentTarget.hasPointerCapture(e.pointerId))
      e.currentTarget.releasePointerCapture(e.pointerId);
    endPress(true);
    // Still over the creature after the press: keep it clickable.
    bridge.setMouseOver(true);
  };
  const onCancel = (): void => {
    if (down.current) endPress(false);
  };
  // Window-level safety net for a press that ends somewhere we never hear.
  useEffect(() => {
    const stop = (): void => {
      if (down.current) endPress(false);
    };
    window.addEventListener('blur', stop);
    window.addEventListener('pointerup', stop);
    return () => {
      window.removeEventListener('blur', stop);
      window.removeEventListener('pointerup', stop);
    };
    // endPress only touches refs and the bridge, so mounting once is enough.
  }, []);

  // Every laptop keeps a presence, not just the host: a blank screen on the
  // other machines was what made the companion feel broken. A non-hosting
  // laptop shows `waiting` (Hermit is with someone else), `sleeping` (this
  // host is idle or past bedtime) or `offline` (we cannot reach the keeper).
  const here = k.phase === 'here';
  const derived = moodFor({
    state: k.state,
    present: k.present,
    soulHolder: k.soulHolder,
    host: k.hostId ?? '',
    connected: k.connected,
  });
  // The animation phases own the brief in-between moments; otherwise the
  // keeper's own state decides.
  const phased: Mood | null =
    k.phase === 'arriving' ? 'arriving' : k.phase === 'leaving' ? 'away' : null;
  const base: Mood = here && sleepy ? 'sleeping' : (phased ?? derived);
  // The keeper is the authority on whether Hermit is on THIS laptop. An
  // animation beat may colour the moment, but it must never contradict that:
  // the walk-in used to leave `away` on screen while the banner said "with
  // you", which read as the mascot being broken.
  const holdsIt = !!k.soulHolder && k.soulHolder === k.hostId;
  const acted: Mood | null =
    act.mood && !(holdsIt && (act.mood === 'away' || act.mood === 'offline')) ? act.mood : null;
  const mood: Mood = acted ?? (holdsIt && base === 'away' ? 'visiting' : base);
  const hostName = (k.hostId ?? 'this laptop').replace(/^./, (c) => c.toUpperCase());
  const holderName = k.soulHolder?.replace(/^./, (c) => c.toUpperCase());
  const locationTitle = !k.connected
    ? 'Keeper offline'
    : k.phase === 'arriving'
      ? `Arriving at ${hostName}`
      : k.phase === 'leaving'
        ? `Leaving ${hostName}`
        : holderName
          ? `Hermit is with ${holderName}`
          : 'Hermit is between laptops';
  const locationDetail = !k.connected
    ? 'Waiting to reconnect'
    : k.phase === 'leaving'
      ? 'Next stop is not chosen yet'
      : k.soulHolder === k.hostId
        ? 'On your laptop now'
        : holderName
          ? `On ${holderName}’s laptop`
          : 'Waiting for someone to claim it';

  return (
    <div className={`stage${faded ? ' is-faded' : ''}`}>
      <div className="location-label" aria-live="polite">
        <strong>{locationTitle}</strong>
        <span>{locationDetail}</span>
      </div>
      {line && (
        <div className="bubble" aria-live="polite">
          <DialogBox
            text={line}
            name="HERMIT"
            compact
            tone={sleepy ? 'dream' : 'paper'}
            onDone={() => setTyping(false)}
          />
        </div>
      )}

      <div
        ref={spriteRef}
        className="creature"
        style={{ transform: `translateX(${x}px)`, width: SPRITE, height: SPRITE }}
        {...hover}
        // after the spread: onMove is the heartbeat AND the drag detector
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onCancel}
        onLostPointerCapture={onCancel}
        role="button"
        aria-label={`${moodLine(mood, k.soulHolder, k.hostId ?? '')} Click for the menu.`}
      >
        {k.quest && here && (
          <span className="quest-mark" aria-label="Hermit is carrying a favor for you">
            <span aria-hidden>✉</span>
            <b aria-hidden>!</b>
          </span>
        )}
        {pieces.length > 0 && here && !sleepy && (
          <span className="shell-badge" title={`${pieces.length} shell pieces`}>
            <PixelCanvas grid={shellGrid} scale={2} label={`Shell: ${pieces.length} pieces`} />
          </span>
        )}
        <PocketHermit
          mood={mood}
          size={SPRITE}
          label={moodLine(mood, k.soulHolder, k.hostId ?? '')}
        />
        {effect === 'dust' && (
          <span className="fx fx--dust" aria-hidden>
            <i />
            <i />
            <i />
          </span>
        )}
      </div>
    </div>
  );
}
