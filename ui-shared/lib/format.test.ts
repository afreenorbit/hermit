import { describe, expect, it } from 'vitest';

import { formatDwell } from './format';

describe('formatDwell', () => {
  it('reads like a game stat, not a timestamp', () => {
    expect(formatDwell(42)).toBe('42S');
    expect(formatDwell(600)).toBe('10M');
    expect(formatDwell(3600)).toBe('1H');
    expect(formatDwell(5400)).toBe('1H 30M');
  });
});
