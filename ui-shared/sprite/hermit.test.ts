import { describe, expect, it } from 'vitest';

import { EMPTY, P } from '../palette';
import { renderShellGrid } from '../shell/renderShellGrid';
import { ANIMATIONS, animationFrames, FRAME, type AnimationName } from './hermit';
import { DUST, SPARKLE, ZZZ } from './glyphs';

describe('hermit sprite', () => {
  it('matches the frame counts in the sprite spec', () => {
    const spec: Record<AnimationName, number> = {
      idle: 4,
      blink: 2,
      walk: 6,
      talk: 4,
      happy: 6,
      sleepy: 4,
      wave: 4,
      surprised: 3,
    };
    for (const [name, n] of Object.entries(spec)) {
      expect(ANIMATIONS[name as AnimationName].poses).toHaveLength(n);
    }
    expect([DUST.length, ZZZ.length, SPARKLE.length]).toEqual([5, 3, 6]);
  });

  it('draws 32x32 frames with an ink outline, using only the palette', () => {
    for (const name of Object.keys(ANIMATIONS) as AnimationName[]) {
      for (const f of animationFrames(name)) {
        expect(f.w).toBe(FRAME);
        expect(f.cells).toHaveLength(FRAME * FRAME);
        expect(f.cells).toContain(P.ink);
        expect(f.cells.every((c) => c === EMPTY || (c >= 0 && c < 16))).toBe(true);
      }
    }
  });

  it('wears the live shell instead of the borrowed one', () => {
    const shell = renderShellGrid(
      [
        {
          id: 'pc_a',
          brain_provider: 'codex',
          dwell_s: 7200,
          departure: 'graceful',
          seed: 3,
          local_hour: 2,
        },
      ],
      { size: 24 },
    );
    const borrowed = animationFrames('idle')[0]!;
    const worn = animationFrames('idle', shell)[0]!;
    expect(worn.cells).not.toEqual(borrowed.cells);
    expect(worn.cells).toContain(P.dream); // night piece
  });
});
