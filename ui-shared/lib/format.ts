/** Times, temperatures, durations, departure labels. Owner: C. */

export function formatDwell(seconds: number): string {
  if (seconds < 60) return `${seconds}S`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}M`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}H` : `${hours}H ${rest}M`;
}

export const DEPARTURE_LABEL = {
  graceful: 'GRACEFUL',
  bedtime: 'BEDTIME',
  abrupt: 'ABRUPT',
  manual: 'MANUAL',
} as const;
