/** Keeper shell pieces → renderer input. This laptop's clock is the host's local time. Owner: C. */
import type { ShellPieceInput } from '@hermit/ui';
import type { ShellPieceT } from '@hermit/ui/contracts';

export function toPieceInputs(shell: readonly ShellPieceT[]): ShellPieceInput[] {
  return shell.map((p) => {
    const d = new Date(p.created_at);
    return {
      id: p.id,
      brain_provider: p.brain_provider,
      temp_c: p.temp_c ?? null,
      dwell_s: p.dwell_s,
      departure: p.departure,
      seed: p.seed,
      created_at: p.created_at,
      // created_at is when the piece was made; arrival was dwell_s earlier
      local_hour: (((d.getHours() + d.getMinutes() / 60 - p.dwell_s / 3600) % 24) + 24) % 24,
    };
  });
}

export const titleCase = (id: string): string => id.charAt(0).toUpperCase() + id.slice(1);
