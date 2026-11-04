/**
 * The creature on the desktop. Owner: C. plan.md §6.3.
 *
 *   SOUL_CLAIMED (me)      walk in from the edge → dust → idle (surprised if abrupt)
 *   idle                   idle loop, blinks, eyes follow the cursor
 *   new den line           talk while the dialog types, stays 7s
 *   FAVOR_ASSIGNED (me)    "!" bobbing above the shell
 *   SHELL_PIECE_ADDED      happy + sparkle; the shell on its back grows
 *   after 00:30            sleepy + zzz, dream-coloured dialog
 *   DEPARTURE / RELEASED   wave → walk off the other edge → window hides
 *   reduced motion         fades only, static frames, instant text
 */
import {
  DialogBox,
  DUST,
  HermitSprite,
  PixelIcon,
  SPARKLE,
  SpriteAnimator,
  sound,
  useReducedMotion,
  ZZZ,
  type AnimationName,
} from '@hermit/ui';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';

import { bridge, inElectron } from '../shared/bridge';
import { toPieceInputs } from '../shared/pieces';
import { isSleepyHour } from '../shared/reduce';
import { useKeeper } from '../shared/store';

const WALK_PX = 220;
const SPRITE = 128;

type Look = readonly [number, number];

export function CritterWindow() {
  const k = useKeeper();
  const reduced = useReducedMotion();
  const pieces = useMemo(() => toPieceInputs(k.shell), [k.shell]);
  const [x, setX] = useState(0);
  const [act, setAct] = useState<{ anim: AnimationName; flip: boolean }>({
    anim: 'idle',
    flip: false,
  });
  const [effect, setEffect] = useState<'dust' | 'sparkle' | null>(null);
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
      setAct({ anim: 'walk', flip: true });
      setX(WALK_PX);
      for (let i = 1; i <= 16; i++) later(i * 100, () => setX(Math.round(WALK_PX * (1 - i / 16))));
      later(1650, () => {
        setAct({ anim: 'idle', flip: false });
        setEffect('dust');
      });
      if (k.abrupt) later(2150, () => setAct({ anim: 'surprised', flip: false }));
      later(k.abrupt ? 3000 : 2200, () => {
        setEffect(null);
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
      setAct({ anim: 'wave', flip: false });
      later(1400, () => setAct({ anim: 'walk', flip: true }));
      for (let i = 1; i <= 18; i++)
        later(1400 + i * 100, () => setX(-Math.round((WALK_PX * i) / 18)));
      later(3300, () => {
        setX(0);
        setAct({ anim: 'idle', flip: false });
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
    setAct({ anim: 'happy', flip: false });
    setEffect('sparkle');
    const t = window.setTimeout(() => {
      setEffect(null);
      setAct({ anim: 'idle', flip: false });
    }, 1300);
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
          ? 'Hermit is with someone else right now.'
          : 'Waiting for the keeper on 127.0.0.1:47800…'}
      </div>
    );
  }

  const here = k.phase === 'here';
  const base: AnimationName = here && sleepy ? 'sleepy' : here && typing ? 'talk' : 'idle';
  const anim: AnimationName = act.anim === 'idle' ? base : act.anim;
  const spriteLook: Look = act.flip ? [-look[0], look[1]] : look;

  return (
    <div className={`stage${faded ? ' is-faded' : ''}`}>
      {line && (
        <div className="bubble" {...hover}>
          <DialogBox
            text={line}
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
        aria-label="Hermit. Click to open Hermit's menu."
        {...hover}
      >
        {k.quest && here && (
          <span className="quest-mark" aria-label="Hermit is carrying a quest for you">
            <PixelIcon name="quest" scale={4} />
          </span>
        )}
        <HermitSprite
          animation={anim}
          pieces={pieces}
          scale={SPRITE / 32}
          flip={act.flip}
          look={anim === 'walk' ? undefined : spriteLook}
          label="Hermit"
        />
        {effect === 'dust' && (
          <SpriteAnimator className="fx fx--dust" frames={DUST} fps={10} scale={4} loop={false} />
        )}
        {effect === 'sparkle' && (
          <SpriteAnimator
            className="fx fx--sparkle"
            frames={SPARKLE}
            fps={10}
            scale={4}
            loop={false}
          />
        )}
        {here && sleepy && <SpriteAnimator className="fx fx--zzz" frames={ZZZ} fps={3} scale={3} />}
      </div>
    </div>
  );
}
