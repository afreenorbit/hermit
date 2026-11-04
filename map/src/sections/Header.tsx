/** Logo, live ticker, journey picker, sound and theme toggles. Owner: C. */
import {
  formatDwell,
  PixelButton,
  PixelToggleGroup,
  PocketHermit,
  sound,
  Ticker,
} from '@hermit/ui';
import type { JourneyT } from '@hermit/ui/contracts';
import { useEffect, useState } from 'react';

import type { Derived } from '../lib/derive';
import {
  SCENARIOS,
  type JourneyKind,
  type JourneySource,
  type ScenarioId,
} from '../hooks/useJourney';

interface Props {
  derived: Derived | null;
  journey: JourneyT | null;
  kind: JourneyKind | null;
  source: JourneySource | null;
  scenario: ScenarioId;
  dark: boolean;
  onTheme: () => void;
  onScenario: (s: ScenarioId) => void;
}

/** What the ribbon says about where this journey came from. */
function provenance(
  kind: JourneyKind | null,
  journey: JourneyT | null,
  source: JourneySource | null,
) {
  if (kind === 'simulation') {
    const scenario = journey?.source?.scenario;
    return {
      tag: 'Simulation',
      text: `Not a real run: the simulator played${scenario ? ` ${scenario}` : ' a scenario'} with fake clocks and fake friends, then exported the journey.`,
    };
  }
  if (kind === 'sample')
    return {
      tag: 'Sample data',
      text:
        source === 'wide'
          ? 'A hand-made three-continent journey, to show the world view — not a real run.'
          : 'A made-up journey in the shape of our Bengaluru group — not a real run.',
    };
  return null;
}

export function Header({
  derived,
  journey,
  kind,
  source,
  scenario,
  dark,
  onTheme,
  onScenario,
}: Props) {
  const [on, setOn] = useState(sound.isEnabled());
  useEffect(() => sound.subscribe(setOn), []);

  const cur = derived?.current;
  const ticker = cur?.host
    ? `Now with ${cur.host.display_name} · ${cur.host.city}${cur.dwellS != null ? ` · ${formatDwell(cur.dwellS).toLowerCase()}` : ''}`
    : 'Asleep · nobody is around';
  const note = provenance(kind, journey, source);

  return (
    <header className="masthead">
      {note && (
        <div className={`ribbon${kind === 'simulation' ? ' ribbon--sim' : ''}`} role="note">
          <strong>{note.tag}</strong>
          <span>{note.text}</span>
        </div>
      )}
      <div className="masthead__row">
        <a className="logo" href="./" aria-label="Hermit — home">
          <span className="logo__mark">
            <PocketHermit mood="visiting" size={58} label="" />
          </span>
          <span className="logo__text">
            <span className="logo__word">Hermit</span>
            <span className="logo__sub">a creature with no home</span>
          </span>
        </a>
        <div className="masthead__ticker">
          <Ticker live={!!cur?.host && kind === 'real'}>{ticker}</Ticker>
        </div>
        <div className="masthead__tools">
          <PixelButton
            variant="ghost"
            size="sm"
            icon={on ? 'sound' : 'mute'}
            label={on ? 'Mute sound' : 'Turn sound on'}
            aria-pressed={on}
            onClick={() => sound.setEnabled(!on)}
          />
          <PixelButton
            variant="ghost"
            size="sm"
            icon={dark ? 'sun' : 'moon'}
            label={dark ? 'Light theme' : 'Dark theme'}
            onClick={onTheme}
          />
        </div>
      </div>
      <nav className="picker" aria-label="Which journey">
        <span className="picker__label">Journey</span>
        <PixelToggleGroup
          label="Which journey"
          required
          value={scenario}
          onValueChange={(v) => onScenario(v as ScenarioId)}
          items={SCENARIOS.map((s) => ({ value: s.id, label: s.label, title: s.title }))}
        />
      </nav>
    </header>
  );
}
