/** Times, temperatures, durations, weather and departure labels. Owner: C. */

export type BrainProvider = 'claude-code' | 'codex' | 'opencode' | 'other';
export type Departure = 'graceful' | 'bedtime' | 'abrupt' | 'manual';
export type StopDeparture = Departure | 'present';

export function formatDwell(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}S`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}M`;
  const hours = Math.floor(minutes / 60);
  if (hours >= 48) return `${Math.floor(hours / 24)}D`;
  const rest = minutes % 60;
  return rest === 0 ? `${hours}H` : `${hours}H ${rest}M`;
}

/** Milliseconds between two ISO timestamps, as a dwell label. */
export function formatSpan(fromIso: string, toIso: string | number): string {
  const to = typeof toIso === 'number' ? toIso : Date.parse(toIso);
  return formatDwell(Math.max(0, (to - Date.parse(fromIso)) / 1000));
}

export function formatHandoffMs(ms: number | null | undefined): string {
  if (ms == null) return '—';
  return ms < 10_000 ? `${(ms / 1000).toFixed(1)}S` : `${Math.round(ms / 1000)}S`;
}

export function formatTemp(tempC: number | null | undefined): string {
  return tempC == null ? '—' : `${Math.round(tempC)}°C`;
}

/** "10:12" in the given zone (default: the viewer's own). */
export function formatClock(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    ...(timeZone ? { timeZone } : {}),
  }).format(new Date(iso));
}

/** "NOV 5" in the viewer's zone. */
export function formatDay(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(timeZone ? { timeZone } : {}),
  })
    .format(new Date(iso))
    .toUpperCase();
}

/**
 * Local hour of an instant (0–24, fractional) at a place.
 *
 * The journey contract carries coordinates but no timezone, so without one we
 * approximate the offset from longitude (nearest half hour). That is plenty for
 * colouring a shell by night / dawn / day / dusk.
 */
export function localHour(
  iso: string,
  place: { timezone?: string | null; lon?: number | null } = {},
): number {
  const d = new Date(iso);
  if (place.timezone) {
    try {
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: place.timezone,
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      }).formatToParts(d);
      const h = Number(parts.find((p) => p.type === 'hour')?.value ?? 0);
      const m = Number(parts.find((p) => p.type === 'minute')?.value ?? 0);
      return h + m / 60;
    } catch {
      /* unknown zone: fall through to the longitude guess */
    }
  }
  const offset = place.lon != null ? Math.round(place.lon / 7.5) / 2 : 0;
  const h = d.getUTCHours() + d.getUTCMinutes() / 60 + offset;
  return ((h % 24) + 24) % 24;
}

export type HourBand = 'night' | 'dawn' | 'day' | 'dusk';

export function hourBand(hour: number): HourBand {
  const h = ((hour % 24) + 24) % 24;
  if (h >= 5 && h < 9) return 'dawn';
  if (h >= 9 && h < 17) return 'day';
  if (h >= 17 && h < 21) return 'dusk';
  return 'night';
}

export const HOUR_BAND_LABEL: Record<HourBand, string> = {
  night: 'NIGHT',
  dawn: 'DAWN',
  day: 'DAY',
  dusk: 'DUSK',
};

export const DEPARTURE_LABEL = {
  graceful: 'GRACEFUL',
  bedtime: 'BEDTIME',
  abrupt: 'ABRUPT',
  manual: 'MANUAL',
  present: 'HERE NOW',
} as const satisfies Record<StopDeparture, string>;

export const BRAIN_LABEL = {
  'claude-code': 'CLAUDE CODE',
  codex: 'CODEX',
  opencode: 'OPENCODE',
  other: 'OTHER',
} as const satisfies Record<BrainProvider, string>;

export type WeatherIcon =
  'sun' | 'partly' | 'cloud' | 'fog' | 'rain' | 'snow' | 'storm' | 'unknown';

/** Open-Meteo WMO weather code → short label + icon. */
export function weatherInfo(code: number | null | undefined): { label: string; icon: WeatherIcon } {
  if (code == null) return { label: 'UNKNOWN', icon: 'unknown' };
  if (code === 0) return { label: 'CLEAR', icon: 'sun' };
  if (code <= 2) return { label: 'PARTLY CLOUDY', icon: 'partly' };
  if (code === 3) return { label: 'OVERCAST', icon: 'cloud' };
  if (code === 45 || code === 48) return { label: 'FOG', icon: 'fog' };
  if (code >= 51 && code <= 67) return { label: code < 60 ? 'DRIZZLE' : 'RAIN', icon: 'rain' };
  if (code >= 71 && code <= 77) return { label: 'SNOW', icon: 'snow' };
  if (code >= 80 && code <= 82) return { label: 'SHOWERS', icon: 'rain' };
  if (code === 85 || code === 86) return { label: 'SNOW SHOWERS', icon: 'snow' };
  if (code >= 95) return { label: 'STORM', icon: 'storm' };
  return { label: 'UNKNOWN', icon: 'unknown' };
}
