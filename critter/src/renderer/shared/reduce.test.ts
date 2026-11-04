import type { EventT, KeeperStatusT } from '@hermit/ui/contracts';
import { describe, expect, it } from 'vitest';

import {
  applyEvent,
  applyStatus,
  finishArriving,
  finishLeaving,
  initial,
  isSleepyHour,
} from './reduce';

let n = 0;
const ev = (type: EventT['type'], data: Record<string, unknown> = {}, host = 'akshay'): EventT => ({
  v: 1,
  id: `evt_${String(n++).padStart(26, '0')}`,
  type,
  host,
  ts: '2026-11-05T10:00:00Z',
  data,
});

const status = (over: Partial<KeeperStatusT> = {}): KeeperStatusT => ({
  host: 'akshay',
  state: 'WAITING',
  present: true,
  soul_holder: 'afreen',
  mood: 'away',
  ...over,
});

const connected = applyStatus(initial, status());

describe('critter reducer (plan.md 6.3)', () => {
  it('stays hidden while someone else has the soul', () => {
    expect(connected.phase).toBe('waiting');
    expect(applyEvent(connected, ev('SOUL_CLAIMED', { holder: 'abhishek' })).phase).toBe('waiting');
  });

  it('walks in when this host claims the soul, then settles', () => {
    const s = applyEvent(
      connected,
      ev('SOUL_CLAIMED', { holder: 'akshay', previous_holder: 'afreen' }),
    );
    expect(s.phase).toBe('arriving');
    expect(s.abrupt).toBe(false);
    expect(finishArriving(s).phase).toBe('here');
  });

  it('arrives surprised after a lid slam (lease expiry)', () => {
    const freed = applyEvent(
      connected,
      ev('SOUL_FREE', { previous_holder: 'afreen', freed_by: 'lease_expiry' }, 'afreen'),
    );
    const s = applyEvent(freed, ev('SOUL_CLAIMED', { holder: 'akshay' }));
    expect(s.abrupt).toBe(true);
  });

  it('shows a quest marker only for favors assigned here', () => {
    const here = finishArriving(applyEvent(connected, ev('SOUL_CLAIMED', { holder: 'akshay' })));
    expect(applyEvent(here, ev('FAVOR_ASSIGNED', { assignee: 'afreen' })).quest).toBe(false);
    const q = applyEvent(here, ev('FAVOR_ASSIGNED', { assignee: 'akshay', favor_id: 'fav_x' }));
    expect(q.quest).toBe(true);
    expect(applyEvent(q, ev('FAVOR_COMPLETED', { favor_id: 'fav_x' })).quest).toBe(false);
  });

  it('celebrates each new shell piece once', () => {
    const piece = {
      v: 1,
      id: 'pc_01JC5Z8W9X0Y1Z2A3B4C5D6E7F',
      host: 'akshay',
      city: 'Koramangala',
      brain_provider: 'codex',
      dwell_s: 600,
      departure: 'graceful',
      created_at: '2026-11-05T10:00:00Z',
      seed: 1,
    };
    const a = applyEvent(connected, ev('SHELL_PIECE_ADDED', { piece }));
    expect(a.shell).toHaveLength(1);
    expect(a.celebrate).toBe(1);
    const b = applyEvent(a, ev('SHELL_PIECE_ADDED', { piece }));
    expect(b.celebrate).toBe(1);
  });

  it('waves goodbye on departure and hides when the walk-off ends', () => {
    const here = finishArriving(applyEvent(connected, ev('SOUL_CLAIMED', { holder: 'akshay' })));
    const leaving = applyEvent(here, ev('DEPARTURE_STARTED', { reason: 'idle' }));
    expect(leaving.phase).toBe('leaving');
    expect(applyEvent(leaving, ev('SOUL_RELEASED', { departure: 'graceful' })).phase).toBe(
      'leaving',
    );
    expect(finishLeaving(leaving).phase).toBe('waiting');
  });

  it('jumps straight to "here" when it connects mid-visit (no walk-in)', () => {
    const s = applyStatus(
      initial,
      status({ soul_holder: 'akshay', state: 'HOLDING', last_line: 'hi' }),
    );
    expect(s.phase).toBe('here');
    expect(s.lines.map((l) => l.text)).toEqual(['hi']);
  });

  it('keeps the last five den lines', () => {
    let s = applyStatus(initial, status({ soul_holder: 'akshay' }));
    for (let i = 0; i < 8; i++)
      s = applyStatus(s, status({ soul_holder: 'akshay', last_line: `line ${i}` }));
    expect(s.lines.map((l) => l.text)).toEqual(['line 3', 'line 4', 'line 5', 'line 6', 'line 7']);
  });

  it('is sleepy from 00:30 until morning', () => {
    expect(isSleepyHour(new Date(2026, 10, 5, 0, 29))).toBe(false);
    expect(isSleepyHour(new Date(2026, 10, 5, 0, 30))).toBe(true);
    expect(isSleepyHour(new Date(2026, 10, 5, 5, 59))).toBe(true);
    expect(isSleepyHour(new Date(2026, 10, 5, 6, 0))).toBe(false);
  });
});
