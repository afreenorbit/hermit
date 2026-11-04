import { describe, expect, it } from 'vitest';

import { pixelAvatar } from './pixelAvatar';

describe('pixelAvatar', () => {
  it('is deterministic per host', () => {
    expect(pixelAvatar('afreen')).toEqual(pixelAvatar('afreen'));
  });

  it('is left-right symmetric', () => {
    for (const id of ['afreen', 'abhishek', 'akshay', 'zz-9']) {
      const g = pixelAvatar(id, { background: true });
      for (let y = 0; y < 8; y++) {
        for (let x = 0; x < 4; x++) expect(g.cells[y * 8 + x]).toBe(g.cells[y * 8 + 7 - x]);
      }
    }
  });

  it('gives our three hosts three different faces', () => {
    const faces = ['afreen', 'abhishek', 'akshay'].map((id) =>
      JSON.stringify(pixelAvatar(id).cells),
    );
    expect(new Set(faces).size).toBe(3);
  });
});
