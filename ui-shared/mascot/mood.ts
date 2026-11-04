/**
 * Which mascot a laptop should be showing.
 *
 * This is the mirror of `mood_for()` in `keeper/hermit_keeper/group.py`, and
 * `mood.test.ts` checks the two tables agree. Two copies exist because the
 * keeper needs it to answer `/v1/group` for *other* laptops, and the critter
 * needs it locally so it can keep drawing something sensible while the keeper
 * is unreachable — which is exactly when it matters most.
 *
 * **Every laptop in the group shows a mascot, not just the host.** A laptop
 * that is awake while Hermit is elsewhere shows `waiting`; one whose keeper we
 * cannot reach shows `offline`. A blank screen on four of five machines was
 * the thing that made the companion feel broken.
 *
 * The one invariant: **only the soul holder is ever `visiting`.** Local
 * activity decides whether a laptop is eligible to host; the shared Switch
 * lease decides who actually does. Keeping those apart is what stops two
 * screens claiming Hermit at once.
 */
import type { Mood } from '../components/PocketHermit';

export type { Mood };

/** Keeper state machine states, as the API reports them. */
export type KeeperState =
  | 'ASLEEP'
  | 'AWAKE_WAITING'
  | 'CLAIMING'
  | 'HOLDING'
  | 'DEPARTING'
  | 'BEDTIME_LOCK';

export interface MoodInput {
  /** This laptop's keeper state, or null if we do not know it. */
  state: KeeperState | string | null;
  /** Is a human at this laptop? Local, from its own keyboard. */
  present: boolean | null;
  /** Who Switch says holds the soul. Shared; one answer for the group. */
  soulHolder: string | null;
  /** This laptop's host_id. */
  host: string;
  /** Can we currently reach this laptop's keeper? */
  connected?: boolean;
}

export function moodFor({
  state,
  present,
  soulHolder,
  host,
  connected = true,
}: MoodInput): Mood {
  // Not knowing is its own answer. Never dress it up as "resting".
  if (!connected || state === null) return 'offline';

  switch (state) {
    case 'HOLDING':
      // If Switch disagrees with our own state, believe Switch. Disagreeing
      // here is precisely the two-Hermits bug.
      return soulHolder === null || soulHolder === host ? 'visiting' : 'waiting';
    case 'CLAIMING':
      return 'arriving';
    case 'DEPARTING':
      return 'away';
    case 'BEDTIME_LOCK':
      return 'sleeping';
    case 'ASLEEP':
      return present === false ? 'sleeping' : 'waiting';
    case 'AWAKE_WAITING':
      return 'waiting';
    default:
      return 'offline';
  }
}

/** A short line under the mascot, in Hermit's voice where it fits. */
export function moodLine(mood: Mood, soulHolder: string | null, host: string): string {
  const who = soulHolder ? titleCase(soulHolder) : null;
  switch (mood) {
    case 'visiting':
      return 'I’m here with you.';
    case 'arriving':
      return 'Just arrived — I brought you something.';
    case 'away':
      return 'Off to whoever’s awake next.';
    case 'sleeping':
      return 'Resting. You should too.';
    case 'waiting':
      return who && who.toLowerCase() !== host.toLowerCase()
        ? `I’m with ${who} right now.`
        : 'Nobody’s around — I’m waiting.';
    case 'offline':
      return 'Can’t reach this laptop.';
  }
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
