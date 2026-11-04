import { describe, expect, it } from 'vitest';

import { kindOf, requestedScenario, scenarioById } from './useJourney';

describe('requestedScenario', () => {
  it('reads ?journey= and its aliases', () => {
    expect(requestedScenario('?journey=three_cities')).toBe('three_cities');
    expect(requestedScenario('?journey=sim')).toBe('three_cities');
    expect(requestedScenario('?journey=world')).toBe('world');
    expect(requestedScenario('?journey=Bengaluru')).toBe('bengaluru');
  });

  it('still honours the old ?data= links', () => {
    expect(requestedScenario('?data=wide')).toBe('world');
    expect(requestedScenario('?data=sample')).toBe('bengaluru');
  });

  it('ignores anything else', () => {
    expect(requestedScenario('')).toBeNull();
    expect(requestedScenario('?journey=../../etc/passwd')).toBeNull();
  });

  it('defaults to Bengaluru: the real export first, then the sample', () => {
    expect(scenarioById(null).files).toEqual(['live', 'sample']);
  });
});

describe('kindOf', () => {
  it('believes the data when it says where it came from', () => {
    expect(kindOf({ source: { kind: 'simulation' } }, 'live')).toBe('simulation');
    expect(kindOf({ source: { kind: 'simulation' } }, 'three_cities')).toBe('simulation');
  });

  it('never calls a committed sample real', () => {
    expect(kindOf({}, 'sample')).toBe('sample');
    expect(kindOf({}, 'wide')).toBe('sample');
    expect(kindOf({ source: null }, 'three_cities')).toBe('sample');
  });

  it('treats an unlabelled export as real', () => {
    expect(kindOf({}, 'live')).toBe('real');
  });
});
