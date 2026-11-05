/**
 * What the one big button should say and whether it can be pressed.
 *
 * There is exactly one action at a time — take Hermit, or send it on — and
 * which one depends on live state, not on what you last clicked. Deriving it
 * here, from the keeper's own state, fixes three things that made the button
 * feel broken:
 *
 *   - it could be pressed again while the first press was still happening,
 *     queueing departures and claims nobody asked for;
 *   - it went back to "Take Hermit" the instant the request returned, so you
 *     could press it three times before the soul actually moved;
 *   - it never said what was going on in between.
 *
 * The rule: the button is live only when pressing it would change something.
 * The rest of the time it still shows the current situation in words, because
 * a greyed-out button with no explanation is its own kind of broken.
 */
export type SoulActionKind = 'take' | 'send' | 'none';

export interface SoulActionInput {
  /** Can we reach this laptop's keeper? */
  connected: boolean;
  /** This laptop's keeper state. */
  state: string | null;
  /** Who Switch says holds the soul. */
  soulHolder: string | null;
  /** This laptop's host_id. */
  host: string | null;
  /** A request of ours is in flight. */
  busy?: boolean;
}

export interface SoulAction {
  kind: SoulActionKind;
  label: string;
  /** Why it cannot be pressed, for a tooltip or helper line. Null when live. */
  hint: string | null;
  disabled: boolean;
  /** 'danger' for sending Hermit away, 'primary' for taking it. */
  tone: 'primary' | 'danger' | 'ghost';
}

export function soulAction({
  connected,
  state,
  soulHolder,
  host,
  busy = false,
}: SoulActionInput): SoulAction {
  if (!connected) {
    return {
      kind: 'none',
      label: 'Keeper offline',
      hint: 'Start the keeper on this laptop to take or send Hermit.',
      disabled: true,
      tone: 'ghost',
    };
  }

  const mine = !!host && soulHolder === host;

  // Mid-move. Both of these resolve on their own in a few seconds, and
  // pressing anything during them only causes a second request.
  if (state === 'CLAIMING') {
    return {
      kind: 'none',
      label: 'Taking Hermit…',
      hint: 'Asking Switch for the soul.',
      disabled: true,
      tone: 'primary',
    };
  }
  if (state === 'DEPARTING') {
    return {
      kind: 'none',
      label: 'Saying goodbye…',
      hint: 'Leaving a favor for whoever is next.',
      disabled: true,
      tone: 'danger',
    };
  }
  if (state === 'BEDTIME_LOCK') {
    return {
      kind: 'none',
      label: 'Past your bedtime',
      hint: 'Hermit will not come back until morning. That is the point.',
      disabled: true,
      tone: 'ghost',
    };
  }

  if (mine) {
    return {
      kind: 'send',
      label: busy ? 'Saying goodbye…' : 'I’m busy — go',
      hint: busy ? 'Sending Hermit on.' : null,
      disabled: busy,
      tone: 'danger',
    };
  }

  if (soulHolder) {
    return {
      kind: 'none',
      label: `Hermit is with ${titleCase(soulHolder)}`,
      hint: 'You can take it once they hand it on.',
      disabled: true,
      tone: 'ghost',
    };
  }

  return {
    kind: 'take',
    label: busy ? 'Taking Hermit…' : 'Take Hermit',
    hint: busy ? 'Asking Switch for the soul.' : null,
    disabled: busy,
    tone: 'primary',
  };
}

/** A one-line description of where Hermit is, for under the button. */
export function soulStatus(
  connected: boolean,
  soulHolder: string | null,
  host: string | null,
): string {
  if (!connected) return 'Cannot reach this laptop.';
  if (soulHolder && host && soulHolder === host) return 'Hermit is on this laptop.';
  if (soulHolder) return `Hermit is with ${titleCase(soulHolder)}.`;
  return 'Nobody has Hermit right now.';
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
