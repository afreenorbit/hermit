import { describe, expect, it } from 'vitest';

import { soulAction, soulStatus, type SoulActionInput } from './soulAction';

const base: SoulActionInput = {
  connected: true,
  state: 'AWAKE_WAITING',
  soulHolder: null,
  host: 'afreen',
};

describe('soulAction', () => {
  it('offers to take Hermit only when nobody has it', () => {
    expect(soulAction(base).kind).toBe('take');
    expect(soulAction({ ...base, soulHolder: 'akshay' }).kind).toBe('none');
  });

  it('offers to send Hermit on only when you have it', () => {
    const action = soulAction({ ...base, soulHolder: 'afreen', state: 'HOLDING' });
    expect(action.kind).toBe('send');
    expect(action.tone).toBe('danger');
  });

  it('cannot be pressed again while a request is in flight', () => {
    const taking = soulAction({ ...base, busy: true });
    expect(taking.disabled).toBe(true);
    expect(taking.label).toMatch(/Taking/);

    const sending = soulAction({ ...base, soulHolder: 'afreen', state: 'HOLDING', busy: true });
    expect(sending.disabled).toBe(true);
    expect(sending.label).toMatch(/goodbye/);
  });

  it('stays locked through the states that resolve on their own', () => {
    // Pressing during these only fires a second request for the same thing.
    for (const state of ['CLAIMING', 'DEPARTING']) {
      const action = soulAction({ ...base, state });
      expect(action.disabled).toBe(true);
      expect(action.kind).toBe('none');
    }
  });

  it('always explains why it is not pressable', () => {
    const blocked = [
      soulAction({ ...base, connected: false }),
      soulAction({ ...base, state: 'CLAIMING' }),
      soulAction({ ...base, state: 'DEPARTING' }),
      soulAction({ ...base, state: 'BEDTIME_LOCK' }),
      soulAction({ ...base, soulHolder: 'akshay' }),
    ];
    for (const action of blocked) {
      expect(action.disabled).toBe(true);
      expect(action.hint).toBeTruthy();
    }
  });

  it('names who has Hermit rather than just greying out', () => {
    expect(soulAction({ ...base, soulHolder: 'akshay' }).label).toContain('Akshay');
  });

  it('refuses to offer anything while the keeper is unreachable', () => {
    const action = soulAction({ ...base, connected: false });
    expect(action.kind).toBe('none');
    expect(action.label).toMatch(/offline/i);
  });

  it('will not let you take Hermit past your own bedtime', () => {
    const action = soulAction({ ...base, state: 'BEDTIME_LOCK' });
    expect(action.kind).toBe('none');
    expect(action.disabled).toBe(true);
  });
});

describe('soulStatus', () => {
  it('says where Hermit is in one line', () => {
    expect(soulStatus(true, 'afreen', 'afreen')).toMatch(/on this laptop/i);
    expect(soulStatus(true, 'akshay', 'afreen')).toContain('Akshay');
    expect(soulStatus(true, null, 'afreen')).toMatch(/nobody/i);
    expect(soulStatus(false, null, 'afreen')).toMatch(/cannot reach/i);
  });
});
