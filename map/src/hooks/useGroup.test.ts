import { describe, expect, it } from 'vitest';

import { requestedKeeper, secondsSince } from './useGroup';

/** `requestedKeeper` reads window.location, so each case sets it up. */
function withSearch<T>(search: string, fn: () => T): T {
  const original = globalThis.location;
  Object.defineProperty(globalThis, 'location', {
    value: { search, href: `http://localhost/${search}` },
    writable: true,
    configurable: true,
  });
  try {
    return fn();
  } finally {
    Object.defineProperty(globalThis, 'location', {
      value: original,
      writable: true,
      configurable: true,
    });
  }
}

describe('requestedKeeper', () => {
  it('accepts a loopback keeper', () => {
    expect(withSearch('?live=http://127.0.0.1:47801', requestedKeeper)).toBe(
      'http://127.0.0.1:47801',
    );
    expect(withSearch('?live=http://localhost:47802', requestedKeeper)).toBe(
      'http://localhost:47802',
    );
  });

  it('refuses a keeper on somebody else’s machine', () => {
    // A shared link carrying ?live=<their host> would make everyone who opens
    // the page quietly probe that address.
    expect(withSearch('?live=http://192.168.1.50:47801', requestedKeeper)).toBeNull();
    expect(withSearch('?live=http://example.com', requestedKeeper)).toBeNull();
  });

  it('ignores junk instead of throwing', () => {
    expect(withSearch('?live=not-a-url', requestedKeeper)).toBeNull();
    expect(withSearch('', requestedKeeper)).toBeNull();
  });
});

describe('secondsSince', () => {
  const now = Date.parse('2026-11-05T12:00:00Z');

  it('measures how long ago a host checked in', () => {
    expect(secondsSince('2026-11-05T11:59:30Z', now)).toBe(30);
    expect(secondsSince('2026-11-05T11:55:00Z', now)).toBe(300);
  });

  it('never reports negative time for a slightly fast clock', () => {
    expect(secondsSince('2026-11-05T12:00:05Z', now)).toBe(0);
  });

  it('returns null for a host that never checked in', () => {
    expect(secondsSince(null, now)).toBeNull();
    expect(secondsSince('nonsense', now)).toBeNull();
  });
});
