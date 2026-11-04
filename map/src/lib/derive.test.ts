import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { Journey, type JourneyT } from '@hermit/ui/contracts';
import { describe, expect, it } from 'vitest';

import { derive, nameOf } from './derive';

const load = (name: string): JourneyT =>
  Journey.parse(JSON.parse(readFileSync(resolve(__dirname, '../../public/data', name), 'utf8')));

describe('derive (Bengaluru sample)', () => {
  const j = load('journey.sample.json');
  const d = derive(j);

  it('orders stops newest first and keeps every shell piece', () => {
    expect(d.stopsNewestFirst.map((s) => s.seq)).toEqual([8, 7, 6, 5, 4, 3, 2, 1]);
    expect(d.pieces).toHaveLength(j.shell.length);
    expect(d.pieceIndex.get(j.shell[0]!.id)).toBe(0);
  });

  it('counts a favor once even if two stops mention it', () => {
    // the fixture's stop 4 and stop 5 both carry stop 3's favor (done, then expired)
    const ids = j.stops
      .filter((s) => s.favor_received?.status === 'done')
      .map((s) => s.favor_received!.id);
    expect(d.favorsDone).toBe(new Set(ids).size);
  });

  it('builds favor pairs between different friends', () => {
    expect(d.pairs.every((p) => p.from !== p.to)).toBe(true);
    expect(d.pairs.reduce((a, p) => a + p.count, 0)).toBe(d.favorsDone);
    const given = Object.values(d.perHost).reduce((a, h) => a + h.given, 0);
    const received = Object.values(d.perHost).reduce((a, h) => a + h.received, 0);
    expect(given).toBe(d.favorsDone);
    expect(received).toBe(d.favorsDone);
  });

  it('finds friends reached and the longest chain', () => {
    expect(d.friendsReached).toBe(3);
    // stops 2,3,4 done; 5 expired; 6,7,8 done → longest run is 3
    expect(d.longestChain).toBe(3);
  });

  it('knows where Hermit is now and fills local hours from longitude', () => {
    expect(d.current.host?.host_id).toBe('abhishek');
    expect(d.current.dwellS).toBeGreaterThanOrEqual(0);
    for (const p of d.pieces) expect(p.local_hour).toBeGreaterThanOrEqual(0);
    // first stop arrives 00:00Z — Bengaluru (~UTC+5) is dawn, not midnight
    expect(d.pieces[0]!.local_hour).toBeCloseTo(5, 0);
  });

  it('names people, including wild favors from Hermit', () => {
    expect(nameOf(d, 'afreen')).toBe('Afreen');
    expect(nameOf(d, 'hermit')).toBe('Hermit');
    expect(nameOf(d, null)).toBe('nobody');
  });
});

describe('derive (wide sample)', () => {
  it('counts three distinct places', () => {
    const d = derive(load('journey.wide.sample.json'));
    expect(d.places).toBe(3);
    expect(d.brains.sort()).toEqual(['claude-code', 'codex', 'opencode']);
  });

  it('handles an empty journey', () => {
    const j = load('journey.sample.json');
    const d = derive({
      ...j,
      stops: [],
      shell: [],
      hermit: { current_host: null, current_city: null, since: null },
    });
    expect(d.favorsDone).toBe(0);
    expect(d.longestChain).toBe(0);
    expect(d.range).toBeNull();
    expect(d.current.host).toBeNull();
  });
});

describe('derive (simulator export)', () => {
  const j = load('journey.three_cities.json');

  it('is labelled as a simulation', () => {
    expect(j.source?.kind).toBe('simulation');
  });

  it('links each piece to the stop whose favor grew it, and counts those favors done', () => {
    const d = derive(j);
    expect(d.favorsDone).toBe(j.stats.favors_done);
    for (const [stopId, pid] of d.pieceOfStop) {
      const stop = j.stops.find((s) => s.stop_id === stopId)!;
      const piece = j.shell.find((p) => p.id === pid)!;
      expect(piece.favor_id).toBe(stop.favor_received?.id);
    }
  });

  it('copes with a raw export: repeated pieces, no stop links, stale statuses', () => {
    const raw = {
      ...j,
      shell: [...j.shell, ...j.shell],
      stops: j.stops.map((s) => ({
        ...s,
        shell_piece_id: null,
        favor_received: s.favor_received ? { ...s.favor_received, status: 'open' as const } : null,
      })),
    };
    const d = derive(raw);
    expect(d.pieces).toHaveLength(j.shell.length);
    expect(d.favorsDone).toBe(j.stats.favors_done);
    expect(d.pieceOfStop.size).toBe(j.shell.length);
  });

  it('never upgrades an expired favor to done', () => {
    const raw = {
      ...j,
      stops: j.stops.map((s) => ({
        ...s,
        favor_received: s.favor_received
          ? { ...s.favor_received, status: 'expired' as const }
          : null,
      })),
    };
    expect(derive(raw).favorsDone).toBe(0);
  });
});
