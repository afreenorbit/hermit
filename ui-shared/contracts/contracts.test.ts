import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { Event, Journey, KeeperStatus } from './index';

const data = (name: string) =>
  JSON.parse(readFileSync(resolve(__dirname, '../../map/public/data', name), 'utf8')) as unknown;

describe('contracts', () => {
  it.each(['journey.sample.json', 'journey.wide.sample.json', 'journey.three_cities.json'])(
    '%s parses as a Journey',
    (name) => {
      const r = Journey.safeParse(data(name));
      expect(r.success, r.success ? '' : JSON.stringify(r.error.issues.slice(0, 3))).toBe(true);
    },
  );

  it('labels a simulator journey through the optional source field', () => {
    const r = Journey.safeParse(data('journey.three_cities.json'));
    expect(r.success && r.data.source?.kind).toBe('simulation');
    const bad = Journey.safeParse({
      ...(data('journey.sample.json') as object),
      source: { kind: 'guess' },
    });
    expect(bad.success).toBe(false);
  });

  it('accepts a real keeper /v1/status (the OpenAPI states and moods)', () => {
    for (const [state, mood] of [
      ['AWAKE_WAITING', 'waiting'],
      ['HOLDING', 'visiting'],
      ['BEDTIME_LOCK', 'sleeping'],
      ['ASLEEP', 'offline'],
    ]) {
      const r = KeeperStatus.safeParse({
        host: 'afreen',
        state,
        present: true,
        soul_holder: 'abhishek',
        since: '2026-11-05T10:12:03+00:00',
        mood,
        favor_pending: null,
        last_line: null,
      });
      expect(r.success, `${state}/${mood}`).toBe(true);
    }
  });

  it('rejects ids without the right prefix', () => {
    const r = Event.safeParse({
      v: 1,
      id: 'evt_nope',
      type: 'SOUL_CLAIMED',
      host: 'afreen',
      ts: '2026-11-05T10:12:03Z',
      data: {},
    });
    expect(r.success).toBe(false);
  });

  it('accepts a real event envelope', () => {
    const r = Event.safeParse({
      v: 1,
      id: 'evt_01JC5Z8W9X0Y1Z2A3B4C5D6E7F',
      type: 'SOUL_CLAIMED',
      host: 'afreen',
      ts: '2026-11-05T10:12:03Z',
      data: { holder: 'afreen', previous_holder: 'abhishek', latency_ms: 8400 },
    });
    expect(r.success).toBe(true);
  });
});
