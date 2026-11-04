import { describe, expect, it } from 'vitest';

import { MOOD_LABEL, MOODS, type Mood } from './PocketHermit';

describe('PocketHermit', () => {
  it('covers exactly the six moods the keeper API can return', () => {
    const expected: Mood[] = [
      'visiting',
      'arriving',
      'away',
      'sleeping',
      'waiting',
      'offline',
    ];
    expect([...MOODS].sort()).toEqual([...expected].sort());
  });

  it('describes every state for screen readers', () => {
    for (const mood of MOODS) {
      expect(MOOD_LABEL[mood].length).toBeGreaterThan(8);
    }
  });

  it('is explicit that offline means unknown, not resting', () => {
    expect(MOOD_LABEL.offline.toLowerCase()).toMatch(/can.t reach/);
    expect(MOOD_LABEL.offline.toLowerCase()).not.toContain('sleep');
  });

  it('only promises Hermit is here for the visiting mood', () => {
    const here = MOODS.filter((m) => MOOD_LABEL[m].toLowerCase().includes('here with you'));
    expect(here).toEqual(['visiting']);
  });
});
