/**
 * Runtime contracts for the UI — zod mirrors of shared/schemas/*. Owner: C.
 *
 * Hand-written rather than generated: the schemas cross-reference each other
 * and the generators flatten that badly. `contracts.test.ts` keeps them honest
 * by parsing every committed fixture. If the UI and the keeper ever disagree,
 * the JSON Schema wins and this file changes.
 */
import { z } from 'zod';

const ulid = (prefix: string) => z.string().regex(new RegExp(`^${prefix}_[0-9A-HJKMNP-TV-Z]{26}$`));
const isoDate = z.string().datetime({ offset: true });

export const HostId = z.string().regex(/^[a-z0-9-]{2,24}$/);
export const BrainProvider = z.enum(['claude-code', 'codex', 'opencode', 'other']);
export const Departure = z.enum(['graceful', 'bedtime', 'abrupt', 'manual']);
export const StopDeparture = z.enum(['graceful', 'bedtime', 'abrupt', 'manual', 'present']);
export const FavorStatus = z.enum(['open', 'assigned', 'done', 'expired']);
export const FavorKind = z.enum(['share', 'note', 'dare', 'question']);

export const EventType = z.enum([
  'PRESENCE_CHANGED',
  'SOUL_FREE',
  'SOUL_CLAIMED',
  'SOUL_CLAIM_REJECTED',
  'DEPARTURE_STARTED',
  'SOUL_RELEASED',
  'ARRIVAL_ANNOUNCED',
  'FAVOR_LEFT',
  'FAVOR_ASSIGNED',
  'FAVOR_COMPLETED',
  'SHELL_PIECE_ADDED',
  'BEDTIME_EVICTION',
  'OVERLAP_SUGGESTED',
  'NUDGE_SENT',
  'ERROR',
]);

export const Event = z
  .object({
    v: z.literal(1),
    id: ulid('evt'),
    type: EventType,
    host: HostId,
    ts: isoDate,
    data: z.record(z.unknown()),
  })
  .strict();

export const Favor = z
  .object({
    v: z.literal(1),
    id: ulid('fav'),
    left_by: z.string(),
    text: z.string().min(1).max(280),
    kind: FavorKind,
    created_at: isoDate,
    assignee: z.string().nullable(),
    status: FavorStatus,
    switch_task_id: z.string().nullable().optional(),
    completed_at: isoDate.nullable().optional(),
  })
  .strict();

export const ShellPiece = z
  .object({
    v: z.literal(1),
    id: ulid('pc'),
    host: HostId,
    city: z.string(),
    brain_provider: BrainProvider,
    temp_c: z.number().nullable().optional(),
    weather_code: z.number().int().nullable().optional(),
    dwell_s: z.number().int().min(0),
    departure: Departure,
    favor_id: z.string().nullable().optional(),
    created_at: isoDate,
    seed: z.number().int(),
  })
  .strict();

export const FavorRef = z
  .object({
    id: z.string().optional(),
    text: z.string().optional(),
    left_by: z.string().optional(),
    for: z.string().optional(),
    status: FavorStatus.optional(),
  })
  .strict()
  .nullable();

export const JourneyHost = z
  .object({
    host_id: HostId,
    display_name: z.string(),
    city: z.string(),
    lat: z.number(),
    lon: z.number(),
    brain_provider: BrainProvider,
  })
  .strict();

export const Stop = z
  .object({
    stop_id: ulid('stop'),
    seq: z.number().int().min(1),
    host: z.string(),
    arrived_at: isoDate,
    left_at: isoDate.nullable().optional(),
    departure: StopDeparture,
    weather: z
      .object({
        temp_c: z.number().nullable().optional(),
        code: z.number().int().nullable().optional(),
      })
      .strict()
      .nullable()
      .optional(),
    favor_received: FavorRef.optional(),
    favor_left: FavorRef.optional(),
    shell_piece_id: z.string().nullable().optional(),
  })
  .strict();

export const Journey = z
  .object({
    v: z.literal(1),
    generated_at: isoDate,
    hermit: z
      .object({
        current_host: z.string().nullable(),
        current_city: z.string().nullable(),
        since: isoDate.nullable(),
      })
      .strict(),
    hosts: z.array(JourneyHost),
    stops: z.array(Stop),
    shell: z.array(ShellPiece),
    stats: z
      .object({
        handoffs: z.number().int().optional(),
        favors_done: z.number().int().optional(),
        favors_left: z.number().int().optional(),
        overlaps_suggested: z.number().int().optional(),
        overlaps_taken: z.number().int().optional(),
        median_handoff_ms: z.number().int().nullable().optional(),
      })
      .passthrough(),
  })
  .strict();

/** GET /v1/status — keeper-api.openapi.yaml */
export const KeeperStatus = z.object({
  host: z.string(),
  state: z.enum(['IDLE_AWAY', 'WAITING', 'CLAIMING', 'HOLDING', 'DEPARTING', 'ASLEEP']),
  present: z.boolean(),
  soul_holder: z.string().nullable(),
  since: isoDate.nullable().optional(),
  mood: z.enum(['arriving', 'curious', 'sleepy', 'leaving', 'away']),
  favor_pending: z.record(z.unknown()).nullable().optional(),
  last_line: z.string().nullable().optional(),
});

export const KeeperShell = z.object({ pieces: z.array(ShellPiece) });

export type EventT = z.infer<typeof Event>;
export type EventTypeT = z.infer<typeof EventType>;
export type FavorT = z.infer<typeof Favor>;
export type ShellPieceT = z.infer<typeof ShellPiece>;
export type FavorRefT = NonNullable<z.infer<typeof FavorRef>>;
export type JourneyHostT = z.infer<typeof JourneyHost>;
export type StopT = z.infer<typeof Stop>;
export type JourneyT = z.infer<typeof Journey>;
export type KeeperStatusT = z.infer<typeof KeeperStatus>;
