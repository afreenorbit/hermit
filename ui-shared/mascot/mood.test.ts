import { describe, expect, it } from 'vitest';

import { MOODS } from '../components/PocketHermit';
import { moodFor, moodLine, type MoodInput } from './mood';

const base: MoodInput = {
  state: 'AWAKE_WAITING',
  present: true,
  soulHolder: null,
  host: 'afreen',
};

describe('moodFor', () => {
  it('shows visiting only to the laptop that actually holds the soul', () => {
    expect(moodFor({ ...base, state: 'HOLDING', soulHolder: 'afreen' })).toBe('visiting');
    expect(moodFor({ ...base, state: 'HOLDING', soulHolder: 'akshay' })).toBe('waiting');
  });

  it('never shows two laptops as visiting at once', () => {
    const holder = 'akshay';
    const screens = ['afreen', 'abhishek', 'akshay'].map((host) =>
      moodFor({ state: 'HOLDING', present: true, soulHolder: holder, host }),
    );
    expect(screens.filter((m) => m === 'visiting')).toHaveLength(1);
  });

  it('gives every awake non-host laptop a waiting presence, not a blank screen', () => {
    expect(moodFor({ ...base, state: 'AWAKE_WAITING', soulHolder: 'akshay' })).toBe('waiting');
    expect(moodFor({ ...base, state: 'ASLEEP', present: true, soulHolder: 'akshay' })).toBe(
      'waiting',
    );
  });

  it('shows arriving only after a claim succeeds, never while reaching', () => {
    // Every awake laptop reaches at the same moment when a soul frees.
    expect(moodFor({ ...base, state: 'CLAIMING' })).toBe('waiting');
    expect(
      moodFor({ ...base, state: 'HOLDING', soulHolder: 'afreen', holdingForS: 2 }),
    ).toBe('arriving');
    expect(
      moodFor({ ...base, state: 'HOLDING', soulHolder: 'afreen', holdingForS: 60 }),
    ).toBe('visiting');
  });

  it('never shows two laptops arriving at once during a scramble', () => {
    const screens = ['afreen', 'abhishek', 'akshay'].map((host) =>
      moodFor({ state: 'CLAIMING', present: true, soulHolder: null, host }),
    );
    expect(screens.filter((m) => m === 'arriving')).toHaveLength(0);
  });

  it('maps the remaining handoff states the brief calls for', () => {
    expect(moodFor({ ...base, state: 'DEPARTING' })).toBe('away');
    expect(moodFor({ ...base, state: 'BEDTIME_LOCK' })).toBe('sleeping');
    expect(moodFor({ ...base, state: 'ASLEEP', present: false })).toBe('sleeping');
  });

  it('admits when it cannot tell instead of guessing', () => {
    expect(moodFor({ ...base, connected: false })).toBe('offline');
    expect(moodFor({ ...base, state: null })).toBe('offline');
    expect(moodFor({ ...base, state: 'SOMETHING_NEW' })).toBe('offline');
  });

  it('returns a mood the artwork actually has', () => {
    const states = [
      'ASLEEP',
      'AWAKE_WAITING',
      'CLAIMING',
      'HOLDING',
      'DEPARTING',
      'BEDTIME_LOCK',
    ];
    for (const state of states) {
      for (const present of [true, false, null]) {
        for (const soulHolder of [null, 'afreen', 'akshay']) {
          const mood = moodFor({ state, present, soulHolder, host: 'afreen' });
          expect(MOODS).toContain(mood);
        }
      }
    }
  });
});

describe('moodLine', () => {
  it('names who has Hermit when someone else does', () => {
    expect(moodLine('waiting', 'akshay', 'afreen')).toContain('Akshay');
  });

  it('does not claim a host when nobody has it', () => {
    expect(moodLine('waiting', null, 'afreen')).toContain('Nobody');
  });

  it('has a line for every mood', () => {
    for (const mood of MOODS) {
      expect(moodLine(mood, 'akshay', 'afreen').length).toBeGreaterThan(5);
    }
  });
});
