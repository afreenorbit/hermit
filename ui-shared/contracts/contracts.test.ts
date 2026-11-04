import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { Event, Journey } from './index';

const data = (name: string) =>
  JSON.parse(readFileSync(resolve(__dirname, '../../map/public/data', name), 'utf8')) as unknown;

describe('contracts', () => {
  it.each(['journey.sample.json', 'journey.wide.sample.json'])('%s parses as a Journey', (name) => {
    const r = Journey.safeParse(data(name));
    expect(r.success, r.success ? '' : JSON.stringify(r.error.issues.slice(0, 3))).toBe(true);
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
