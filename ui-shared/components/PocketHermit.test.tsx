import { describe, expect, it } from 'vitest';

import { MOOD_LABEL, type Mood } from './PocketHermit';

const MOODS: Mood[] = ['arriving', 'visiting', 'away', 'sleeping'];

describe('PocketHermit', () => {
  it('covers exactly the four moods the keeper API can return', () => {
    expect(Object.keys(MOOD_LABEL).sort()).toEqual([...MOODS].sort());
  });

  it('describes every state for screen readers', () => {
    for (const mood of MOODS) {
      expect(MOOD_LABEL[mood].length).toBeGreaterThan(8);
    }
  });
});
