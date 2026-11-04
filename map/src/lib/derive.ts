/**
 * Everything the map shows that is not literally in journey.json. Pure, so it
 * is tested against both fixtures. Owner: C. plan.md §7.0, §7.3.
 */
import { localHour, type BrainProvider, type ShellPieceInput } from '@hermit/ui';
import type { JourneyHostT, JourneyT, ShellPieceT, StopT } from '@hermit/ui/contracts';

export interface HostStats {
  hosted: number;
  /** Favors this friend left that someone else completed. */
  given: number;
  /** Favors this friend completed for someone else. */
  received: number;
  lastHosted: string | null;
  dwellS: number;
}

export interface FavorPair {
  from: string;
  to: string;
  count: number;
}

export interface Derived {
  hosts: Map<string, JourneyHostT>;
  hostIds: string[];
  /** Shell pieces in journey order, with local hour of arrival filled in. */
  pieces: ShellPieceInput[];
  rawPieces: ShellPieceT[];
  pieceIndex: Map<string, number>;
  stopByPiece: Map<string, StopT>;
  /** stop_id → the shell piece that stop produced, if any. */
  pieceOfStop: Map<string, string>;
  stopsNewestFirst: StopT[];
  perHost: Record<string, HostStats>;
  pairs: FavorPair[];
  favorsDone: number;
  /** True when this stop's received favor was completed. */
  receivedDone: (s: StopT) => boolean;
  friendsReached: number;
  longestChain: number;
  brains: BrainProvider[];
  places: number;
  range: { from: string; to: string } | null;
  current: { host: JourneyHostT | null; since: string | null; dwellS: number | null };
}

export function nameOf(d: Pick<Derived, 'hosts'>, hostId: string | null | undefined): string {
  if (!hostId) return 'nobody';
  if (hostId === 'hermit') return 'Hermit';
  return d.hosts.get(hostId)?.display_name ?? hostId;
}

export function derive(j: JourneyT, now: number = Date.parse(j.generated_at)): Derived {
  const hosts = new Map(j.hosts.map((h) => [h.host_id, h]));
  const stops = [...j.stops].sort((a, b) => a.seq - b.seq);
  // An export can repeat a piece; the shell is a set, so keep the first.
  const shell = j.shell.filter((p, i, all) => all.findIndex((q) => q.id === p.id) === i);
  const pieceByFavor = new Map<string, ShellPieceT>();
  for (const p of shell)
    if (p.favor_id && !pieceByFavor.has(p.favor_id)) pieceByFavor.set(p.favor_id, p);

  // A stop names its piece directly, or (older exports) through the favor it
  // completed: a piece carries the id of the favor that grew it.
  const stopByPiece = new Map<string, StopT>();
  const pieceOfStop = new Map<string, string>();
  for (const s of stops) {
    const fid = s.favor_received?.id;
    const pid = s.shell_piece_id ?? (fid ? pieceByFavor.get(fid)?.id : undefined);
    if (!pid || stopByPiece.has(pid)) continue;
    stopByPiece.set(pid, s);
    pieceOfStop.set(s.stop_id, pid);
  }
  /**
   * Done if the export says so, or if this stop's own piece grew from it (an
   * export that never updated the status). An explicit `expired` always wins.
   */
  const isDone = (s: StopT): boolean => {
    const r = s.favor_received;
    if (!r) return false;
    if (r.status === 'done') return true;
    if (r.status === 'expired' || !r.id) return false;
    const pid = pieceOfStop.get(s.stop_id);
    return !!pid && shell.some((p) => p.id === pid && p.favor_id === r.id);
  };

  const pieces: ShellPieceInput[] = shell.map((p) => {
    const stop = stopByPiece.get(p.id);
    const host = hosts.get(p.host);
    return {
      id: p.id,
      brain_provider: p.brain_provider,
      temp_c: p.temp_c ?? null,
      dwell_s: p.dwell_s,
      departure: p.departure,
      seed: p.seed,
      created_at: p.created_at,
      local_hour: localHour(stop?.arrived_at ?? p.created_at, { lon: host?.lon ?? null }),
    };
  });
  const pieceIndex = new Map(shell.map((p, i) => [p.id, i]));

  const perHost: Record<string, HostStats> = {};
  for (const h of j.hosts)
    perHost[h.host_id] = { hosted: 0, given: 0, received: 0, lastHosted: null, dwellS: 0 };

  // A favor counts once, however many stops mention it.
  const doneFavors = new Map<string, { from: string; to: string }>();
  let chain = 0;
  let longestChain = 0;
  for (const s of stops) {
    const stats = (perHost[s.host] ??= {
      hosted: 0,
      given: 0,
      received: 0,
      lastHosted: null,
      dwellS: 0,
    });
    stats.hosted += 1;
    stats.lastHosted = s.arrived_at;
    const end = s.left_at ? Date.parse(s.left_at) : now;
    stats.dwellS += Math.max(0, (end - Date.parse(s.arrived_at)) / 1000);

    const r = s.favor_received;
    if (isDone(s)) {
      chain += 1;
      if (r?.id && r.left_by && !doneFavors.has(r.id))
        doneFavors.set(r.id, { from: r.left_by, to: s.host });
    } else {
      chain = 0;
    }
    longestChain = Math.max(longestChain, chain);
  }

  const pairCounts = new Map<string, FavorPair>();
  for (const { from, to } of doneFavors.values()) {
    if (from === to) continue;
    const key = `${from}>${to}`;
    const pair = pairCounts.get(key) ?? { from, to, count: 0 };
    pair.count += 1;
    pairCounts.set(key, pair);
    if (perHost[from]) perHost[from].given += 1;
    if (perHost[to]) perHost[to].received += 1;
  }

  const brains = [...new Set(shell.map((p) => p.brain_provider))];
  const places = new Set(stops.map((s) => hosts.get(s.host)?.city ?? s.host)).size;
  const first = stops[0];
  const last = stops[stops.length - 1];
  const currentHost = j.hermit.current_host ? (hosts.get(j.hermit.current_host) ?? null) : null;

  return {
    hosts,
    hostIds: j.hosts.map((h) => h.host_id),
    pieces,
    rawPieces: shell,
    pieceIndex,
    stopByPiece,
    pieceOfStop,
    stopsNewestFirst: [...stops].reverse(),
    perHost,
    pairs: [...pairCounts.values()],
    favorsDone: doneFavors.size,
    receivedDone: isDone,
    friendsReached: new Set([...doneFavors.values()].map((f) => f.to)).size,
    longestChain,
    brains,
    places,
    range: first && last ? { from: first.arrived_at, to: last.left_at ?? j.generated_at } : null,
    current: {
      host: currentHost,
      since: j.hermit.since,
      dwellS: j.hermit.since ? Math.max(0, (now - Date.parse(j.hermit.since)) / 1000) : null,
    },
  };
}
