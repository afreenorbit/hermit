/**
 * Live group status, polled from a keeper's `/v1/group`.
 *
 * Deliberately separate from `useJourney`: the journey is **history**, a static
 * JSON export of where Hermit has been, and the group is **now**. Mixing them
 * on one page would imply the exported file is a live feed, which it is not.
 *
 * Any keeper can answer — each folds the same shared ledger — so the dashboard
 * points at whichever laptop you can reach. If it cannot reach one, it says so
 * rather than showing an empty group that looks like everyone went home.
 */
import { useEffect, useState } from 'react';

export interface GroupHost {
  host_id: string;
  state: string | null;
  present: boolean | null;
  mood: 'visiting' | 'arriving' | 'away' | 'sleeping' | 'waiting' | 'offline';
  last_seen: string | null;
  stale: boolean;
  holding: boolean;
}

export interface Group {
  v: 1;
  generated_at: string;
  self: string | null;
  soul_holder: string | null;
  hosts: GroupHost[];
}

/** `?live=http://127.0.0.1:47801` picks which keeper to ask. */
export function requestedKeeper(): string | null {
  if (typeof location === 'undefined') return null;
  const raw = new URLSearchParams(location.search).get('live');
  if (!raw) return null;
  // Only ever talk to a loopback keeper from this page. A `live=` pointing at
  // someone else's machine would make a shared link quietly probe their network.
  try {
    const url = new URL(raw);
    const okHost = url.hostname === '127.0.0.1' || url.hostname === 'localhost';
    return okHost ? url.origin : null;
  } catch {
    return null;
  }
}

const POLL_MS = 3000;

export interface GroupResult {
  group: Group | null;
  /** Null while fine; a message when we cannot reach the keeper. */
  error: string | null;
  /** The keeper we are asking, or null when live status is switched off. */
  keeper: string | null;
}

export function useGroup(keeper: string | null): GroupResult {
  const [group, setGroup] = useState<Group | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!keeper) {
      setGroup(null);
      setError(null);
      return;
    }
    let cancelled = false;
    let timer = 0;

    const tick = async (): Promise<void> => {
      try {
        const res = await fetch(`${keeper}/v1/group`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`keeper answered ${res.status}`);
        const data = (await res.json()) as Group;
        if (cancelled) return;
        setGroup(data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        // Keep the last good snapshot on screen and mark it unreachable, rather
        // than blanking the page on one dropped poll.
        setError(err instanceof Error ? err.message : 'keeper unreachable');
      }
      if (!cancelled) timer = window.setTimeout(tick, POLL_MS);
    };

    void tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [keeper]);

  return { group, error, keeper };
}

/** Seconds since a host last checked in, or null if it never has. */
export function secondsSince(iso: string | null, now = Date.now()): number | null {
  if (!iso) return null;
  const then = Date.parse(iso);
  return Number.isNaN(then) ? null : Math.max(0, Math.round((now - then) / 1000));
}
