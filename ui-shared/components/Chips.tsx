/** BrainBadge, DepartureChip, StatusChip. Owner: C. */
import {
  BRAIN_LABEL,
  DEPARTURE_LABEL,
  type BrainProvider,
  type StopDeparture,
} from '../lib/format';
import { BRAIN_ICONS, type IconName } from '../sprite/glyphs';
import { PixelGridSvg, PixelIcon } from './PixelIcon';

export function BrainBadge({ provider, short }: { provider: BrainProvider; short?: boolean }) {
  const label = BRAIN_LABEL[provider];
  return (
    <span className={`hm-chip hm-brain hm-brain--${provider}`} title={`Brain: ${label}`}>
      <PixelGridSvg grid={BRAIN_ICONS[provider]} scale={2} />
      <span>{short ? label.split(' ')[0] : label}</span>
    </span>
  );
}

const DEPARTURE_ICON: Partial<Record<StopDeparture, IconName>> = {
  bedtime: 'moon',
  abrupt: 'bolt',
  graceful: 'heart',
  manual: 'play',
};

export function DepartureChip({ departure }: { departure: StopDeparture }) {
  const icon = DEPARTURE_ICON[departure];
  return (
    <span className={`hm-chip hm-dep hm-dep--${departure}`}>
      {departure === 'present' ? (
        <span className="hm-dep__pulse" aria-hidden />
      ) : (
        icon && <PixelIcon name={icon} />
      )}
      <span>{DEPARTURE_LABEL[departure]}</span>
    </span>
  );
}

export type QuestStatus = 'open' | 'assigned' | 'done' | 'expired';

export function StatusChip({ status }: { status: QuestStatus }) {
  const icon: IconName | null = status === 'done' ? 'check' : status === 'expired' ? 'cross' : null;
  return (
    <span className={`hm-chip hm-status hm-status--${status}`}>
      {icon && <PixelIcon name={icon} />}
      <span>{status.toUpperCase()}</span>
    </span>
  );
}
