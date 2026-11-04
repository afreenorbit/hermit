/** Logo, live ticker, data switch, sound and theme toggles. Owner: C. */
import { formatDwell, PixelButton, PixelToggleGroup, sound, Ticker, Tilli } from '@hermit/ui';
import { useEffect, useState } from 'react';

import type { Derived } from '../lib/derive';
import type { JourneySource } from '../hooks/useJourney';

interface Props {
  derived: Derived | null;
  source: JourneySource | null;
  dark: boolean;
  onTheme: () => void;
  onSource: (s: JourneySource) => void;
}

export function Header({ derived, source, dark, onTheme, onSource }: Props) {
  const [on, setOn] = useState(sound.isEnabled());
  useEffect(() => sound.subscribe(setOn), []);

  const cur = derived?.current;
  const ticker = cur?.host
    ? `Now with ${cur.host.display_name} · ${cur.host.city}${cur.dwellS != null ? ` · ${formatDwell(cur.dwellS).toLowerCase()}` : ''}`
    : 'Asleep · nobody is around';
  const sample = source === 'sample' || source === 'wide';

  return (
    <header className="masthead">
      {sample && (
        <div className="ribbon" role="note">
          <strong>Sample data</strong>
          <span>
            {source === 'wide'
              ? 'A simulated three-timezone journey — not a real run.'
              : 'A made-up journey in the shape of our Bengaluru pilot.'}
          </span>
        </div>
      )}
      <div className="masthead__row">
        <a className="logo" href="./" aria-label="Hermit — home">
          <span className="logo__mark">
            <Tilli mood="happy" size={58} marks={false} label="" />
          </span>
          <span className="logo__text">
            <span className="logo__word">Hermit</span>
            <span className="logo__sub">with Tilli, a creature with no home</span>
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
                  label: 'City',
                  title: 'Three areas of Bengaluru (our pilot shape)',
                },
                { value: 'wide', label: 'World', title: 'Three timezones (simulation)' },
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
