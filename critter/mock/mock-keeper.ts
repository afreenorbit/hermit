/**
 * Fake keeper API + SSE stream, so the critter can be built before the keeper
 * exists. Owner: C.  `pnpm --filter @hermit/critter mock`
 *
 * Must match shared/schemas/keeper-api.openapi.yaml. It loops a scripted visit
 * that hits every row of plan.md §6.3: arrive, talk, quest, shell piece,
 * goodbye, someone else's turn, and an abrupt (lid-slam) arrival.
 *
 * Env: PORT (47800), HERMIT_HOST (akshay), MOCK_STEP_MS (3500).
 */
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';

const PORT = Number(process.env.PORT ?? 47800);
const HOST = process.env.HERMIT_HOST ?? 'akshay';
const STEP_MS = Number(process.env.MOCK_STEP_MS ?? 3500);
const OTHER = HOST === 'afreen' ? 'abhishek' : 'afreen';
const BRAIN = { afreen: 'claude-code', abhishek: 'opencode', akshay: 'codex' }[HOST] ?? 'codex';

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
const ulid = (prefix: string): string =>
  `${prefix}_${Array.from({ length: 26 }, () => CROCKFORD[Math.floor(Math.random() * 32)]).join('')}`;
const now = (): string => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

let seedCounter = 0;
function piece(
  host: string,
  brain: string,
  departure: string,
  dwell: number,
  temp: number,
  hoursAgo: number,
) {
  const id = ulid('pc');
  return {
    v: 1,
    id,
    host,
    city:
      { afreen: 'Indiranagar', abhishek: 'Kengeri', akshay: 'Koramangala' }[host] ?? 'Bengaluru',
    brain_provider: brain,
    temp_c: temp,
    weather_code: 2,
    dwell_s: dwell,
    departure,
    favor_id: ulid('fav'),
    created_at: new Date(Date.now() - hoursAgo * 3600_000).toISOString().replace(/\.\d{3}Z$/, 'Z'),
    seed: 1000 + seedCounter++ * 7919,
  };
}

const shell = [
  piece('afreen', 'claude-code', 'graceful', 5400, 24, 20),
  piece('abhishek', 'opencode', 'bedtime', 7200, 21, 16),
  piece(HOST, BRAIN, 'graceful', 3600, 27, 11),
  piece('afreen', 'claude-code', 'abrupt', 900, 26, 7),
  piece('abhishek', 'opencode', 'graceful', 10800, 23, 3),
];

const favor = {
  v: 1,
  id: ulid('fav'),
  left_by: OTHER,
  text: 'Send the group the last song stuck in your head',
  kind: 'share',
  created_at: now(),
  assignee: HOST,
  status: 'assigned',
  switch_task_id: null,
  completed_at: null,
};

const LINES: Record<string, string[]> = {
  'claude-code': [
    'Hello, small kingdom of tabs. The light here is the colour of tea — I think I’ll stay a while.',
    'A favor, carried all the way across town in my claws. Gently, now.',
    'Look at that — a new ring on my shell, warm as an afternoon.',
    'I’ll go before the evening gets heavy. Leave something for whoever’s next?',
  ],
  codex: [
    'Arrived. 26°C, light cloud. Shell intact. Mostly.',
    'Quest from Afreen: last song stuck in your head. Takes 10 seconds.',
    'Shell +1 piece. Efficient.',
    'You went quiet. I’m off. Leave a favor for the next one.',
  ],
  opencode: [
    'HELLO!!! New laptop!!! Is that a FOLDER?? I love it here already!!!',
    'QUEST TIME!!! Abhishek says: send the group a song!!! GO GO GO!!',
    'NEW SHELL PIECE!!! It’s SO SHINY!!!',
    'Byeee!!! Leave a favor!!! Any favor!!! I’ll carry it!!!',
  ],
};
const lines = LINES[BRAIN] ?? LINES.codex!;

type Status = {
  host: string;
  state: 'IDLE_AWAY' | 'WAITING' | 'CLAIMING' | 'HOLDING' | 'DEPARTING' | 'ASLEEP';
  present: boolean;
  soul_holder: string | null;
  since: string | null;
  mood: 'arriving' | 'curious' | 'sleepy' | 'leaving' | 'away';
  favor_pending: typeof favor | null;
  last_line: string | null;
};

const status: Status = {
  host: HOST,
  state: 'WAITING',
  present: true,
  soul_holder: OTHER,
  since: now(),
  mood: 'away',
  favor_pending: null,
  last_line: null,
};

const clients = new Set<ServerResponse>();
function emit(type: string, data: Record<string, unknown>, host = HOST): void {
  const evt = { v: 1, id: ulid('evt'), type, host, ts: now(), data };
  const frame = `data: ${JSON.stringify(evt)}\n\n`;
  for (const c of clients) c.write(frame);
  console.log(`→ ${type}`, JSON.stringify(data).slice(0, 90));
}

// --- the scripted visit ----------------------------------------------------
const STEPS: Array<() => void> = [
  () => {
    status.soul_holder = null;
    emit('SOUL_FREE', { previous_holder: OTHER, freed_by: 'release' }, OTHER);
  },
  () => {
    Object.assign(status, { soul_holder: HOST, state: 'HOLDING', mood: 'arriving', since: now() });
    emit('SOUL_CLAIMED', { holder: HOST, previous_holder: OTHER, latency_ms: 8400 });
  },
  () => {
    Object.assign(status, { mood: 'curious', last_line: lines[0] });
    emit('ARRIVAL_ANNOUNCED', {
      stop_id: ulid('stop'),
      weather: { temp_c: 26, code: 2 },
      favor_id: favor.id,
    });
  },
  () => {
    Object.assign(status, { favor_pending: favor, last_line: lines[1] });
    emit('FAVOR_ASSIGNED', { favor_id: favor.id, assignee: HOST });
  },
  () => {
    const p = piece(HOST, BRAIN, 'graceful', 2400, 26, 0);
    shell.push(p);
    Object.assign(status, { favor_pending: null, last_line: lines[2] });
    emit('FAVOR_COMPLETED', { favor_id: favor.id, completed_by: HOST });
    emit('SHELL_PIECE_ADDED', { piece: p });
  },
  () => {},
  () => {
    Object.assign(status, { state: 'DEPARTING', mood: 'leaving', last_line: lines[3] });
    emit('DEPARTURE_STARTED', { reason: 'idle' });
  },
  () => {
    Object.assign(status, {
      state: 'WAITING',
      mood: 'away',
      soul_holder: null,
      favor_pending: null,
    });
    emit('SOUL_RELEASED', { departure: 'graceful' });
  },
  () => {
    status.soul_holder = OTHER;
    emit('SOUL_CLAIMED', { holder: OTHER, previous_holder: HOST, latency_ms: 7900 }, OTHER);
  },
  () => {},
  () => {
    status.soul_holder = null;
    emit('SOUL_FREE', { previous_holder: OTHER, freed_by: 'lease_expiry' }, OTHER);
  },
  () => {
    Object.assign(status, {
      soul_holder: HOST,
      state: 'HOLDING',
      mood: 'arriving',
      since: now(),
      last_line: null,
    });
    emit('SOUL_CLAIMED', { holder: HOST, previous_holder: OTHER, latency_ms: 31000 });
  },
  () => {
    Object.assign(status, {
      mood: 'curious',
      last_line: 'I left in a hurry — someone slammed a lid on me. Where was I?',
    });
    emit('PRESENCE_CHANGED', { present: true, reason: 'input' });
  },
  () => {},
];

let step = 0;
let timer: NodeJS.Timeout;
function schedule(): void {
  clearTimeout(timer);
  timer = setTimeout(() => {
    STEPS[step % STEPS.length]!();
    step = (step + 1) % STEPS.length;
    // after the abrupt arrival, loop back to the talk/quest part of the visit
    if (step === 0) step = 2;
    schedule();
  }, STEP_MS);
}
const jump = (to: number): void => {
  step = to;
  schedule();
};

// --- http --------------------------------------------------------------------
const LOOPBACK = /^(null|https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?)$/;

function cors(req: IncomingMessage, res: ServerResponse): boolean {
  const origin = req.headers.origin;
  if (origin && !LOOPBACK.test(origin)) {
    res.writeHead(403).end('loopback origins only');
    return false;
  }
  if (origin) res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
  return true;
}

const json = (res: ServerResponse, code: number, body: unknown): void => {
  res.writeHead(code, { 'content-type': 'application/json' }).end(JSON.stringify(body));
};

async function body(req: IncomingMessage): Promise<Record<string, unknown>> {
  let raw = '';
  for await (const chunk of req) raw += chunk;
  try {
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

createServer(async (req, res) => {
  if (!cors(req, res)) return;
  if (req.method === 'OPTIONS') return void res.writeHead(204).end();
  const path = new URL(req.url ?? '/', 'http://x').pathname;

  if (req.method === 'GET' && path === '/v1/health')
    return json(res, 200, { ok: true, version: '0.1.0-mock' });
  if (req.method === 'GET' && path === '/v1/status') return json(res, 200, status);
  if (req.method === 'GET' && path === '/v1/shell') return json(res, 200, { pieces: shell });
  if (req.method === 'GET' && path === '/v1/metrics')
    return json(res, 200, { handoffs: [{ from: OTHER, to: HOST, latency_ms: 8400 }] });
  if (req.method === 'GET' && path === '/v1/events') {
    res.writeHead(200, {
      'content-type': 'text/event-stream',
      'cache-control': 'no-cache',
      connection: 'keep-alive',
    });
    res.write(': hello\n\n');
    clients.add(res);
    const ping = setInterval(() => res.write(': ping\n\n'), 15000);
    req.on('close', () => {
      clearInterval(ping);
      clients.delete(res);
    });
    return;
  }
  if (req.method === 'POST' && path === '/v1/depart') {
    if (status.soul_holder === HOST) jump(6);
    return json(res, 202, { ok: true });
  }
  if (req.method === 'POST' && path === '/v1/presence/override') {
    const { mode } = await body(req);
    if (mode === 'asleep' && status.soul_holder === HOST) jump(6);
    if (mode === 'awake' && status.soul_holder !== HOST) jump(11);
    return json(res, 200, { ok: true, mode });
  }
  json(res, 404, { error: 'not found' });
}).listen(PORT, '127.0.0.1', () => {
  console.log(
    `mock keeper for "${HOST}" (${BRAIN}) on http://127.0.0.1:${PORT} — a step every ${STEP_MS}ms`,
  );
  schedule();
});
