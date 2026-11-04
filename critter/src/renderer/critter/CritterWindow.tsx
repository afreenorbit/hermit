/**
 * Tilli on the desktop. Owner: C. plan.md §6.3, moves from the mascot demo.
 *
 *   SOUL_CLAIMED (me)      waddle in from the edge → wave with a letter (curious if abrupt)
 *   idle                   visiting: breathes, blinks, eyes follow the cursor
 *   new den line           chatter while the bubble types, stays 7s
 *   FAVOR_ASSIGNED (me)    a little letter badge bobbing by Tilli
 *   SHELL_PIECE_ADDED      celebrate with sparkles; the shell badge grows
 *   after 00:30            tucked into the shell asleep, zzz, lilac bubble
 *   DEPARTURE / RELEASED   wave → turn around → walk off the other edge → hide
 *   reduced motion         fades only, still poses, instant text
 */
import {
  DialogBox,
  PixelCanvas,
  renderShellGrid,
  sound,
  Tilli,
  useReducedMotion,
  type TilliMood,
} from '@hermit/ui';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';

import { bridge, inElectron } from '../shared/bridge';
import { toPieceInputs } from '../shared/pieces';
import { isSleepyHour } from '../shared/reduce';
import { useKeeper } from '../shared/store';

const WALK_PX = 220;
const SPRITE = 150;

type Look = readonly [number, number];

export function CritterWindow() {
  const k = useKeeper();
  const reduced = useReducedMotion();
  const pieces = useMemo(() => toPieceInputs(k.shell), [k.shell]);
  const shellGrid = useMemo(() => renderShellGrid(pieces, { size: 24 }), [pieces]);
  const [x, setX] = useState(0);
  const [act, setAct] = useState<{ mood: TilliMood | null; flip: boolean }>({
    mood: null,
    flip: false,
  });
  const [effect, setEffect] = useState<'dust' | null>(null);
  const [line, setLine] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);
  const [look, setLook] = useState<Look>([1, 0]);
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

  // show the window whenever there is something to show
  useEffect(() => {
    bridge.setVisible(k.phase !== 'hidden');
    if (k.phase === 'hidden') bridge.setMouseOver(false);
  }, [k.phase]);

  // eyes follow the cursor (screen position from main, or the page in a browser)
  useEffect(() => {
    const aim = (px: number, py: number): void => {
      const r = spriteRef.current?.getBoundingClientRect();
      if (!r) return;
      const dx = px - (r.left + r.width * 0.65);
      const dy = py - (r.top + r.height * 0.35);
      setLook([Math.abs(dx) < 30 ? 0 : Math.sign(dx), Math.abs(dy) < 30 ? 0 : Math.sign(dy)]);
    };
    const off = bridge.on('cursor', (v) => {
      const p = v as { x: number; y: number };
      aim(p.x, p.y);
    });
    const onMove = (e: MouseEvent): void => aim(e.clientX, e.clientY);
    if (!inElectron) window.addEventListener('mousemove', onMove);
    return () => {
      off();
      window.removeEventListener('mousemove', onMove);
    };
  }, []);

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
      setAct({ mood: 'walk', flip: true });
      setX(WALK_PX);
      for (let i = 1; i <= 16; i++) later(i * 100, () => setX(Math.round(WALK_PX * (1 - i / 16))));
      later(1650, () => {
        setAct({ mood: k.abrupt ? 'curious' : 'arriving', flip: false });
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
      setAct({ mood: 'wave', flip: false });
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
    setAct({ mood: 'celebrate', flip: false });
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
  const hover = {
    onPointerEnter: () => bridge.setMouseOver(true),
    onPointerLeave: () => {
      if (!down.current) bridge.setMouseOver(false);
    },
  };
  const onDown = (e: PointerEvent): void => {
    down.current = { x: e.screenX, y: e.screenY };
    bridge.dragStart();
  };
  const onUp = (e: PointerEvent): void => {
    const d = down.current;
    down.current = null;
    bridge.dragEnd();
    if (d && Math.abs(e.screenX - d.x) + Math.abs(e.screenY - d.y) < 4) bridge.panel(true);
  };

  if (k.phase === 'hidden') {
    return inElectron ? null : (
      <div className="web-hint">
        {k.connected
          ? 'Tilli is visiting someone else right now.'
          : 'Waiting for the keeper on 127.0.0.1:47800…'}
      </div>
    );
  }

  const here = k.phase === 'here';
  const base: TilliMood = here && sleepy ? 'sleeping' : here && typing ? 'talking' : 'happy';
  const mood: TilliMood = act.mood ?? base;
  const eyes: Look = act.flip ? [-look[0], look[1]] : look;

  return (
    <div className={`stage${faded ? ' is-faded' : ''}`}>
      {line && (
        <div className="bubble" {...hover}>
          <DialogBox
            text={line}
            name="TILLI"
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
        onPointerDown={onDown}
        onPointerUp={onUp}
        role="button"
        aria-label="Tilli. Click to open Tilli's menu."
        {...hover}
      >
        {k.quest && here && (
          <span className="quest-mark" aria-label="Tilli is carrying a favor for you">
            <span aria-hidden>✉</span>
            <b aria-hidden>!</b>
          </span>
        )}
        {pieces.length > 0 && here && !sleepy && (
          <span className="shell-badge" title={`${pieces.length} shell pieces`}>
            <PixelCanvas grid={shellGrid} scale={2} label={`Shell: ${pieces.length} pieces`} />
          </span>
        )}
        <Tilli
          mood={mood}
          size={SPRITE}
          flip={act.flip}
          look={mood === 'walk' || mood === 'away' ? undefined : eyes}
          letter={mood === 'arriving' || (k.quest && here && mood === 'happy')}
          label="Tilli"
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
