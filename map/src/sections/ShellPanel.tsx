/** The shared shell, its legend, and per-piece tooltips. Owner: C. plan.md §7.4. */
import {
  BRAIN_LABEL,
  DEPARTURE_LABEL,
  formatDwell,
  formatTemp,
  HOUR_BAND_LABEL,
  hourBand,
  patternGrid,
  PixelBox,
  PixelCanvas,
  ShellView,
  weatherInfo,
  type BrainProvider,
  type HourBand,
} from '@hermit/ui';
import { useMemo } from 'react';

import { nameOf, type Derived } from '../lib/derive';

interface Props {
  derived: Derived;
  active: number | null;
  onActive: (i: number | null) => void;
  onPick: (i: number) => void;
  narrow: boolean;
}

const BANDS: HourBand[] = ['night', 'dawn', 'day', 'dusk'];
const BRAINS: BrainProvider[] = ['claude-code', 'codex', 'opencode'];

export function ShellPanel({ derived, active, onActive, onPick, narrow }: Props) {
  const { pieces, rawPieces } = derived;
  const describe = (i: number): string => {
    const p = rawPieces[i];
    if (!p) return '';
    const stop = derived.stopByPiece.get(p.id);
    const band = HOUR_BAND_LABEL[hourBand(pieces[i]?.local_hour ?? 12)].toLowerCase();
    return `Piece ${i + 1} of ${pieces.length}: ${nameOf(derived, p.host)} in ${p.city}, arrived at ${band}, ${BRAIN_LABEL[p.brain_provider]}, stayed ${formatDwell(p.dwell_s)}, left ${DEPARTURE_LABEL[p.departure].toLowerCase()}${stop?.favor_received?.text ? `. Favor: ${stop.favor_received.text}` : ''}`;
  };

  const legend = useMemo(
    () => ({
      bands: BANDS.map((b) => ({ b, grid: patternGrid(b, 'claude-code') })),
      brains: BRAINS.map((br) => ({ br, grid: patternGrid('day', br) })),
    }),
    [],
  );

  return (
    <PixelBox as="section" tab="Shell" className="panel panel--shell" aria-labelledby="shell-h">
      <h2 id="shell-h" className="hm-sr">
        The shell
      </h2>
      <div className="shell__stage">
        <ShellView
          pieces={pieces}
          size={48}
          scale={narrow ? 5 : 6}
          active={active}
          onActive={onActive}
          onPick={onPick}
          describe={describe}
          label="The shell friends built"
          tooltip={(i) => {
            const p = rawPieces[i]!;
            const w = weatherInfo(p.weather_code);
            const stop = derived.stopByPiece.get(p.id);
            return (
              <>
                <strong>
                  #{i + 1} · {nameOf(derived, p.host)}
                </strong>
                <div>
                  {p.city} · {HOUR_BAND_LABEL[hourBand(pieces[i]?.local_hour ?? 12)]} ·{' '}
                  {formatTemp(p.temp_c)} {w.label.toLowerCase()}
                </div>
                <div>
                  {BRAIN_LABEL[p.brain_provider]} · {formatDwell(p.dwell_s)} ·{' '}
                  {DEPARTURE_LABEL[p.departure]}
                </div>
                {stop?.favor_received?.text && (
                  <div className="tip__quote">“{stop.favor_received.text}”</div>
                )}
              </>
            );
          }}
          empty={<p className="empty">No shell yet. The first favor done adds the first piece.</p>}
        />
      </div>
      <p className="shell__count">
        <span>{pieces.length} PIECES</span>
        <span aria-hidden>·</span>
        <span>
          {derived.brains.length} BRAIN{derived.brains.length === 1 ? '' : 'S'}
        </span>
        <span aria-hidden>·</span>
        <span>{derived.hostIds.length} FRIENDS</span>
      </p>
      <p className="shell__hint">
        Hover or arrow-key through the pieces. Click one to find its stop.
      </p>

      <dl className="legend">
        <div>
          <dt>COLOUR</dt>
          <dd>
            {legend.bands.map(({ b, grid }) => (
              <span key={b} className="legend__item">
                <PixelCanvas grid={grid} scale={2} />
                {HOUR_BAND_LABEL[b]}
              </span>
            ))}
          </dd>
          <dd className="legend__note">hour Hermit arrived · lighter when hot, darker when cold</dd>
        </div>
        <div>
          <dt>PATTERN</dt>
          <dd>
            {legend.brains.map(({ br, grid }) => (
              <span key={br} className="legend__item">
                <PixelCanvas grid={grid} scale={2} />
                {BRAIN_LABEL[br].split(' ')[0]}
              </span>
            ))}
          </dd>
        </div>
        <div>
          <dt>EDGE</dt>
          <dd>
            <span className="legend__item">
              <span className="legend__edge legend__edge--solid" />
              GRACEFUL
            </span>
            <span className="legend__item">
              <span className="legend__edge legend__edge--dotted" />
              BEDTIME
            </span>
            <span className="legend__item">
              <span className="legend__edge legend__edge--cracked" />
              ABRUPT
            </span>
          </dd>
        </div>
      </dl>
    </PixelBox>
  );
}
