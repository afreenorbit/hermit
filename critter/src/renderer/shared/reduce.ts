/**
 * Keeper events → what the creature should be doing. Pure, so every row of
 * plan.md §6.3 has a unit test. Owner: C.
 */
import type { EventT, KeeperStatusT, ShellPieceT } from '@hermit/ui/contracts';

export type Phase = 'hidden' | 'arriving' | 'here' | 'leaving';

export interface Line {
  text: string;
  ts: string;
}

export interface CritterState {
  connected: boolean;
  hostId: string | null;
  state: KeeperStatusT['state'] | null;
  present: boolean;
  soulHolder: string | null;
  mood: KeeperStatusT['mood'];
  since: string | null;
  favorPending: Record<string, unknown> | null;
  lastLine: string | null;
  shell: ShellPieceT[];
  events: EventT[];
  lines: Line[];
  phase: Phase;
  /** The previous host vanished (lease expiry) — arrive surprised. */
  abrupt: boolean;
  /** Bumped on every SHELL_PIECE_ADDED so the window can play `happy`. */
  celebrate: number;
  quest: boolean;
  lastFreedBy: 'release' | 'lease_expiry' | null;
}

export const initial: CritterState = {
  connected: false,
  hostId: null,
  state: null,
  present: false,
  soulHolder: null,
  mood: 'away',
  since: null,
  favorPending: null,
  lastLine: null,
  shell: [],
  events: [],
  lines: [],
  phase: 'hidden',
  abrupt: false,
  celebrate: 0,
  quest: false,
  lastFreedBy: null,
};

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);

export function applyStatus(
  s: CritterState,
  st: KeeperStatusT,
  ts = new Date().toISOString(),
): CritterState {
  const holding = st.soul_holder === st.host;
  let phase = s.phase;
  // On connect (or a missed event) jump straight to the right place, no walk.
  if (holding && phase === 'hidden') phase = 'here';
  if (!holding && (phase === 'here' || phase === 'arriving')) phase = 'leaving';
  const line = st.last_line ?? null;
  const lines =
    line && line !== s.lastLine && holding ? [...s.lines, { text: line, ts }].slice(-5) : s.lines;
  return {
    ...s,
    connected: true,
    hostId: st.host,
    state: st.state,
    present: st.present,
    soulHolder: st.soul_holder,
    mood: st.mood,
    since: st.since ?? null,
    favorPending: (st.favor_pending as Record<string, unknown> | null | undefined) ?? null,
    quest: holding && !!st.favor_pending,
    lastLine: line,
    lines,
    phase,
  };
}

export function applyEvent(s: CritterState, e: EventT): CritterState {
  const me = s.hostId;
  const d = e.data;
  const next: CritterState = { ...s, events: [...s.events, e].slice(-50) };
  switch (e.type) {
    case 'SOUL_FREE': {
      const by = str(d.freed_by);
      return {
        ...next,
        soulHolder: null,
        lastFreedBy: by === 'lease_expiry' ? 'lease_expiry' : 'release',
      };
    }
    case 'SOUL_CLAIMED': {
      const holder = str(d.holder);
      if (holder && holder === me) {
        return {
          ...next,
          soulHolder: holder,
          phase: s.phase === 'here' ? 'here' : 'arriving',
          abrupt: s.lastFreedBy === 'lease_expiry',
          lastFreedBy: null,
        };
      }
      return {
        ...next,
        soulHolder: holder,
        phase: s.phase === 'hidden' ? 'hidden' : 'leaving',
        quest: false,
        lastFreedBy: null,
      };
    }
    case 'DEPARTURE_STARTED':
    case 'SOUL_RELEASED':
      if (e.host !== me || s.phase === 'hidden') return next;
      return { ...next, phase: 'leaving', quest: false };
    case 'FAVOR_ASSIGNED':
      return str(d.assignee) === me ? { ...next, quest: true } : next;
    case 'FAVOR_COMPLETED':
      return { ...next, quest: false };
    case 'SHELL_PIECE_ADDED': {
      const piece = d.piece as ShellPieceT | undefined;
      if (!piece || s.shell.some((p) => p.id === piece.id)) return next;
      return { ...next, shell: [...s.shell, piece], celebrate: s.celebrate + 1 };
    }
    default:
      return next;
  }
}

/** Animation phases call this when the walk-off finishes. */
export function finishLeaving(s: CritterState): CritterState {
  return s.phase === 'leaving' ? { ...s, phase: 'hidden', abrupt: false } : s;
}

export function finishArriving(s: CritterState): CritterState {
  return s.phase === 'arriving' ? { ...s, phase: 'here', abrupt: false } : s;
}

/** "Local time ≥ 00:30" (and before morning) → sleepy. */
export function isSleepyHour(date = new Date()): boolean {
  const m = date.getHours() * 60 + date.getMinutes();
  return m >= 30 && m < 6 * 60;
}
