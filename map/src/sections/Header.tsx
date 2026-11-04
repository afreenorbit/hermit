/** Logo, live ticker, data switch, sound and theme toggles. Owner: C. */
import {
  formatDwell,
  HermitSprite,
  PixelButton,
  PixelToggleGroup,
  sound,
  Ticker,
  type ShellPieceInput,
} from '@hermit/ui';
import { useEffect, useState } from 'react';

import type { Derived } from '../lib/derive';
import type { JourneySource } from '../hooks/useJourney';

interface Props {
  derived: Derived | null;
  pieces: ShellPieceInput[];
  source: JourneySource | null;
  dark: boolean;
  onTheme: () => void;
  onSource: (s: JourneySource) => void;
}

export function Header({ derived, pieces, source, dark, onTheme, onSource }: Props) {
  const [on, setOn] = useState(sound.isEnabled());
  useEffect(() => sound.subscribe(setOn), []);

  const cur = derived?.current;
  const ticker = cur?.host
    ? `NOW: WITH ${cur.host.display_name.toUpperCase()} · ${cur.host.city.toUpperCase()}${cur.dwellS != null ? ` · ${formatDwell(cur.dwellS)}` : ''}`
    : 'NOW: ASLEEP · NOBODY IS AROUND';
  const sample = source === 'sample' || source === 'wide';

  return (
    <header className="masthead">
      {sample && (
        <div className="ribbon" role="note">
          <strong>SAMPLE DATA</strong>
          <span>
            {source === 'wide'
              ? 'A simulated three-timezone journey — not a real run.'
              : 'A made-up journey in the shape of our Bengaluru pilot.'}
          </span>
        </div>
      )}
      <div className="masthead__row">
        <a className="logo" href="./" aria-label="Hermit — home">
          <HermitSprite pieces={pieces} scale={2} label="" animation="idle" />
          <span className="logo__text">
            <span className="logo__word">HERMIT</span>
            <span className="logo__sub">a creature with no home</span>
          </span>
        </a>
        <div className="masthead__ticker">
          <Ticker live={!!cur?.host && source === 'live'}>{ticker}</Ticker>
        </div>
        <div className="masthead__tools">
          {sample && (
            <PixelToggleGroup
              label="Sample journey"
              value={source ?? 'sample'}
              onValueChange={(v) => onSource(v as JourneySource)}
              items={[
                {
                  value: 'sample',
                  label: 'CITY',
                  title: 'Three areas of Bengaluru (our pilot shape)',
                },
                { value: 'wide', label: 'WORLD', title: 'Three timezones (simulation)' },
              ]}
            />
          )}
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
    </header>
  );
}
