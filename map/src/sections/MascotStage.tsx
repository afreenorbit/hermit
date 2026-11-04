/**
 * The welcome stage: Hermit acting out each movement — arriving
 * with a letter, visiting, wondering, sleeping, walking away, celebrating.
 * Cycles on its own until someone picks a movement. Owner: C.
 */
import { formatDwell, type Mood, PocketHermit, useReducedMotion } from '@hermit/ui';
import { useEffect, useState } from 'react';

import type { Derived } from '../lib/derive';

interface Movement {
  id: string;
  label: string;
  mood: Mood;
  line: string;
  scene: string;
}

const MOVEMENTS: Movement[] = [
  {
    id: 'arriving',
    label: 'Arriving',
    mood: 'arriving',
    line: 'Hello! I brought a little note from your friend.',
    scene: 'scene--dawn',
  },
  {
    id: 'visiting',
    label: 'Visiting',
    mood: 'visiting',
    line: 'Cozy laptop. I think I’ll stay a while.',
    scene: 'scene--day',
  },
  {
    id: 'curious',
    label: 'Curious',
    mood: 'waiting',
    line: 'Ooh — what will you leave for the next friend?',
    scene: 'scene--day',
  },
  {
    id: 'celebrate',
    label: 'Favor done',
    mood: 'visiting',
    line: 'A new piece for my shell! Thank you!',
    scene: 'scene--dusk',
  },
  {
    id: 'sleeping',
    label: 'Sleeping',
    mood: 'sleeping',
    line: 'It’s past bedtime… you should rest too.',
    scene: 'scene--night',
  },
  {
    id: 'away',
    label: 'Away',
    mood: 'away',
    line: 'Off to whoever’s awake next. See you soon!',
    scene: 'scene--dusk',
  },
];

export function MascotStage({ derived }: { derived: Derived | null }) {
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(1);
  const [auto, setAuto] = useState(true);
  const m = MOVEMENTS[index]!;

  useEffect(() => {
    if (!auto || reduced) return;
    const t = window.setTimeout(() => setIndex((i) => (i + 1) % MOVEMENTS.length), 4200);
    return () => window.clearTimeout(t);
  }, [auto, index, reduced]);

  const host = derived?.current.host;

  return (
    <section className="stage" aria-labelledby="welcome-title">
      <div className="stage__copy">
        <span className="stage__eyebrow">A little creature · A shared adventure</span>
        <h1 id="welcome-title">
          Small favors.
          <br />
          <span>A shell full of stories.</span>
        </h1>
        <p className="stage__lede">
          Meet <strong>Hermit</strong>, Hermit’s wandering companion. Hermit lives on one friend’s
          laptop at a time, borrows their AI as a voice, and moves on when they go quiet — carrying
          a little favor to whoever is awake next.
        </p>
        <div className="stage__cta">
          <a className="hm-btn hm-btn--lg" href="#journey">
            See the journey
          </a>
          <a className="hm-btn hm-btn--lg hm-btn--ghost" href="#log">
            Read the quest log
          </a>
        </div>
        {host && (
          <p className="stage__now">
            <span className="stage__dot" aria-hidden />
            Right now Hermit is with <strong>{host.display_name}</strong> in {host.city}
            {derived?.current.dwellS != null
              ? ` · ${formatDwell(derived.current.dwellS).toLowerCase()}`
              : ''}
          </p>
        )}
      </div>

      <figure className={`stage__scene ${m.scene}`}>
        <div className="scene__sky" aria-hidden>
          <span className="scene__orb" />
          <span className="scene__cloud scene__cloud--a" />
          <span className="scene__cloud scene__cloud--b" />
        </div>
        <div className="scene__ground" aria-hidden />
        <p className="scene__bubble" key={m.id} aria-live="polite">
          {m.line}
        </p>
        <div className="scene__tilli" key={`t-${m.id}`}>
          <PocketHermit mood={m.mood} size={260} label={`Hermit — ${m.label.toLowerCase()}`} />
        </div>
        <figcaption>
          <span className="scene__label">Preview a movement</span>
          <div className="scene__moves" role="radiogroup" aria-label="Hermit's movements">
            {MOVEMENTS.map((mv, i) => (
              <button
                key={mv.id}
                type="button"
                role="radio"
                aria-checked={i === index}
                className={`scene__move${i === index ? ' is-on' : ''}`}
                onClick={() => {
                  setIndex(i);
                  setAuto(false);
                }}
              >
                <PocketHermit mood={mv.mood} size={34} still label="" />
                {mv.label}
              </button>
            ))}
          </div>
        </figcaption>
      </figure>

      <ol className="steps" aria-label="How Hermit works">
        <li>
          <PocketHermit mood="arriving" size={84} still label="" />
          <div>
            <strong>Hermit arrives</strong>
            <span>on whichever friend is at their laptop, and speaks in their AI’s voice.</span>
          </div>
        </li>
        <li>
          <PocketHermit mood="waiting" size={84} still label="" />
          <div>
            <strong>Leave a favor</strong>
            <span>before Hermit moves on — a song, a photo, a kind word for the next friend.</span>
          </div>
        </li>
        <li>
          <PocketHermit mood="visiting" size={84} still label="" />
          <div>
            <strong>The shell grows</strong>
            <span>every favor done adds a piece, coloured by when and where it happened.</span>
          </div>
        </li>
      </ol>
    </section>
  );
}
