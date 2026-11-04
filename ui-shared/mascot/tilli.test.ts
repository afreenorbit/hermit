import { describe, expect, it } from 'vitest';

import { TILLI_MOODS, tilliSvg } from './tilli';

describe('tilliSvg', () => {
  it.each(TILLI_MOODS)('draws a complete Tilli for "%s"', (mood) => {
    const svg = tilliSvg({ mood });
    expect(svg.startsWith('<svg')).toBe(true);
    expect(svg).toContain('viewBox="0 0 220 220"');
    expect(svg).toContain('class="t-shell"');
    expect(svg).toContain('class="t-head"');
    expect(svg.match(/<svg/g)).toHaveLength(1);
  });

  it('turns its back when walking away — no face, no paws', () => {
    const away = tilliSvg({ mood: 'away' });
    expect(away).not.toContain('t-face');
    expect(away).not.toContain('t-paws');
    expect(away).toContain('t-note');
  });

  it('marks moods the way the character sheet does', () => {
    expect(tilliSvg({ mood: 'sleeping' })).toContain('t-zzz');
    expect(tilliSvg({ mood: 'curious' })).toContain('t-question');
    expect(tilliSvg({ mood: 'celebrate' })).toContain('t-sparkles');
    expect(tilliSvg({ mood: 'happy', marks: false })).not.toContain('t-mark');
  });

  it('carries a letter when arriving, or when asked to', () => {
    expect(tilliSvg({ mood: 'arriving' })).toContain('t-letter');
    expect(tilliSvg({ mood: 'happy' })).not.toContain('t-letter');
    expect(tilliSvg({ mood: 'happy', letter: true })).toContain('t-letter');
  });

  it('keeps ids unique so several Tillis can share a page', () => {
    const id = (s: string) => /id="(t[a-z0-9]+)-shell"/.exec(s)?.[1];
    expect(id(tilliSvg())).not.toBe(id(tilliSvg()));
  });

  it('can hide itself from screen readers', () => {
    expect(tilliSvg({ title: '' })).toContain('aria-hidden="true"');
    expect(tilliSvg({ title: 'Tilli' })).toContain('aria-label="Tilli"');
  });
});
