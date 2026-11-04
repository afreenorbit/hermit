/// <reference types="node" />
/**
 * Photographs the map and the critter for the README and the submission.
 *
 *   pnpm --filter @hermit/map capture        (playwright.capture.config.ts)
 *
 * Writes docs/assets/*.png, route-replay.gif and route-replay.webm. The critter
 * runs as its browser preview against a tiny scripted keeper started here, one
 * fixed status per shot, so every state is deterministic. Not part of the e2e
 * gate. Sample and simulated journeys keep their on-page labels in every shot.
 */
import { execFileSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { homedir } from 'node:os';
import { createServer, type Server, type ServerResponse } from 'node:http';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test, type Browser, type Locator, type Page } from '@playwright/test';
import gifenc from 'gifenc';

// gifenc ships CommonJS only
const { applyPalette, GIFEncoder, quantize } = gifenc;
const here = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(here, '../../docs/assets');
const MAP = 'http://localhost:4174/';
const CRITTER = 'http://localhost:5175/';
const KEEPER_PORT = 47_877;
const DEAD_KEEPER = 'http://127.0.0.1:47876';

mkdirSync(OUT, { recursive: true });
const out = (name: string): string => resolve(OUT, name);

test.describe.configure({ mode: 'serial' });

// --- helpers -----------------------------------------------------------------

async function settle(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
}

async function openMap(
  browser: Browser,
  query: string,
  opts: { dark?: boolean; width?: number; height?: number; scale?: number; motion?: boolean } = {},
): Promise<Page> {
  const width = opts.width ?? 1440;
  const ctx = await browser.newContext({
    viewport: { width, height: opts.height ?? 900 },
    deviceScaleFactor: opts.scale ?? 1,
    colorScheme: opts.dark ? 'dark' : 'light',
    reducedMotion: opts.motion ? 'no-preference' : 'reduce',
    isMobile: width < 768,
    hasTouch: width < 768,
  });
  const page = await ctx.newPage();
  await page.goto(`${MAP}${query}`);
  await expect(page.getByTestId('quest-log')).toBeVisible();
  await settle(page);
  return page;
}

/** One screenshot covering several elements (e.g. the map and the shell beside it). */
async function shootUnion(page: Page, locators: Locator[], path: string, pad = 12): Promise<void> {
  const boxes = await Promise.all(locators.map((l) => l.boundingBox()));
  const b = boxes.filter((x): x is NonNullable<typeof x> => !!x);
  const x = Math.max(0, Math.min(...b.map((r) => r.x)) - pad);
  const y = Math.max(0, Math.min(...b.map((r) => r.y)) - pad);
  const w = Math.max(...b.map((r) => r.x + r.width)) + pad - x;
  const h = Math.max(...b.map((r) => r.y + r.height)) + pad - y;
  await page.screenshot({ path, clip: { x, y, width: w, height: h }, fullPage: true });
}

// --- the map -----------------------------------------------------------------

test('map: journey and shell, light and dark', async ({ browser }) => {
  for (const dark of [false, true]) {
    const page = await openMap(browser, '?journey=bengaluru', { dark });
    await shootUnion(
      page,
      [page.locator('.panel--world'), page.locator('.panel--shell')],
      out(`map-${dark ? 'dark' : 'light'}.png`),
    );
    await page.context().close();
  }
});

test('map: first screen, as a judge lands on it', async ({ browser }) => {
  const page = await openMap(browser, '?journey=bengaluru');
  await page.screenshot({ path: out('map-overview.png') });
  await page.context().close();
});

test('map: impact panel and quest log', async ({ browser }) => {
  const page = await openMap(browser, '?journey=bengaluru');
  await page.locator('.panel--impact').screenshot({ path: out('map-impact.png') });
  await page.context().close();
});

test('map: the wide (three-continent) fixture', async ({ browser }) => {
  const page = await openMap(browser, '?journey=world');
  await shootUnion(
    page,
    [page.locator('.panel--world'), page.locator('.panel--shell')],
    out('map-wide.png'),
  );
  await page.context().close();
});

test('map: the simulator run, stamped SIMULATION', async ({ browser }) => {
  const page = await openMap(browser, '?journey=three_cities', { dark: true });
  await expect(page.locator('.world__sim')).toHaveText('SIMULATION');
  // the map carries its own SIMULATION stamp, so this crop stays labelled
  await shootUnion(
    page,
    [page.locator('.panel--world'), page.locator('.panel--shell')],
    out('map-simulation.png'),
  );
  await page.context().close();
});

test('map: phone', async ({ browser }) => {
  const page = await openMap(browser, '?journey=bengaluru', { width: 390, height: 844, scale: 2 });
  await page.locator('#journey').scrollIntoViewIfNeeded();
  await page.evaluate(() => {
    const el = document.getElementById('journey')!;
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 70);
  });
  await page.waitForTimeout(300);
  await page.screenshot({ path: out('map-phone.png') });
  await page.context().close();
});

test('postcard: the share card, as downloaded', async ({ browser }) => {
  const page = await openMap(browser, '?journey=bengaluru');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /make a postcard/i }).click(),
  ]);
  await download.saveAs(out('postcard.png'));
  await page.context().close();
});

// --- the route, moving ----------------------------------------------------------

test('map: route replay as GIF and WebM', async ({ browser }) => {
  const W = 1000;
  const H = 620;
  const videoDir = resolve(here, '../test-results/capture-video');
  rmSync(videoDir, { recursive: true, force: true });
  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    reducedMotion: 'no-preference',
    recordVideo: { dir: videoDir, size: { width: W, height: H } },
  });
  const page = await ctx.newPage();
  await page.goto(`${MAP}?journey=bengaluru`);
  await expect(page.getByTestId('quest-log')).toBeVisible();
  await settle(page);
  const stage = page.locator('.world__stage');
  await page.evaluate(() => {
    const el = document.querySelector('.world__stage')!;
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 64);
  });
  await page.waitForTimeout(600);

  // the GIF: frames of the map itself, encoded with one shared palette
  const helper = await ctx.newPage();
  const box = (await stage.boundingBox())!;
  const gw = 560;
  const gh = Math.round((box.height / box.width) * gw);
  const frames: Array<{ rgba: Uint8Array; delay: number }> = [];
  await page.getByRole('button', { name: 'REPLAY', exact: true }).click();
  let last = Date.now();
  const grab = async (): Promise<void> => {
    const png = (await stage.screenshot()).toString('base64');
    const b64 = await helper.evaluate(
      async ({ png, gw, gh }) => {
        const blob = await (await fetch(`data:image/png;base64,${png}`)).blob();
        const bmp = await createImageBitmap(blob);
        const c = new OffscreenCanvas(gw, gh);
        const x = c.getContext('2d')!;
        x.imageSmoothingQuality = 'high';
        x.drawImage(bmp, 0, 0, gw, gh);
        const d = x.getImageData(0, 0, gw, gh).data;
        let s = '';
        for (let i = 0; i < d.length; i += 0x8000)
          s += String.fromCharCode(...d.subarray(i, i + 0x8000));
        return btoa(s);
      },
      { png, gw, gh },
    );
    const now = Date.now();
    if (frames.length) frames[frames.length - 1]!.delay = now - last;
    last = now;
    frames.push({ rgba: new Uint8Array(Buffer.from(b64, 'base64')), delay: 100 });
  };
  while ((await page.locator('.world__hop').count()) > 0 || frames.length === 0) await grab();
  frames[frames.length - 1]!.delay = 1800; // rest on the finished trail
  const sample = new Uint8Array(frames[0]!.rgba.length * 3);
  [0, Math.floor(frames.length / 2), frames.length - 1].forEach((k, i) =>
    sample.set(frames[k]!.rgba, i * frames[0]!.rgba.length),
  );
  const palette = quantize(sample, 96);
  const gif = GIFEncoder();
  for (const f of frames)
    gif.writeFrame(applyPalette(f.rgba, palette), gw, gh, { palette, delay: f.delay });
  gif.finish();
  writeFileSync(out('route-replay.gif'), gif.bytes());

  await helper.close();
  const video = page.video();
  await ctx.close();
  // Playwright records ~1 Mbit/s VP8. Its own bundled ffmpeg (there is no
  // system ffmpeg on most machines) can re-encode that to a small VP9 file;
  // without it, keep the GIF only rather than commit a 3 MB video.
  const ffmpeg = playwrightFfmpeg();
  const raw = await video!.path();
  if (ffmpeg) {
    execFileSync(ffmpeg, [
      '-y',
      '-loglevel',
      'error',
      '-i',
      raw,
      '-c:v',
      'libvpx-vp9',
      '-b:v',
      '0',
      '-crf',
      '42',
      '-an',
      out('route-replay.webm'),
    ]);
  } else {
    rmSync(out('route-replay.webm'), { force: true });
    console.log('route-replay.webm skipped: Playwright ffmpeg not found (run playwright install)');
  }
});

/** The ffmpeg Playwright installs next to its browsers, if any. */
function playwrightFfmpeg(): string | null {
  const roots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    process.env.LOCALAPPDATA && resolve(process.env.LOCALAPPDATA, 'ms-playwright'),
    resolve(homedir(), '.cache/ms-playwright'),
    resolve(homedir(), 'Library/Caches/ms-playwright'),
  ].filter((r): r is string => !!r && existsSync(r));
  for (const root of roots)
    for (const dir of readdirSync(root).filter((d) => d.startsWith('ffmpeg-')))
      for (const exe of readdirSync(resolve(root, dir)).filter((f) => f.startsWith('ffmpeg')))
        return resolve(root, dir, exe);
  return null;
}

// --- the critter (browser preview, scripted keeper) -------------------------------

interface FakeStatus {
  host: string;
  state: string;
  present: boolean;
  soul_holder: string | null;
  since: string | null;
  mood: string;
  favor_pending: Record<string, unknown> | null;
  last_line: string | null;
}

const sampleShell = (
  JSON.parse(readFileSync(resolve(here, '../public/data/journey.sample.json'), 'utf8')) as {
    shell: unknown[];
  }
).shell;

const FAVOR = {
  v: 1,
  id: 'fav_01JC5Z8W9X0Y1Z2A3B4C5D6E7F',
  left_by: 'abhishek',
  text: 'Send the group the last song stuck in your head',
  kind: 'share',
  created_at: '2026-11-05T09:00:00Z',
  assignee: 'afreen',
  status: 'assigned',
  switch_task_id: null,
  completed_at: null,
};

const STATES: Record<string, FakeStatus> = {
  visiting: {
    host: 'afreen',
    state: 'HOLDING',
    present: true,
    soul_holder: 'afreen',
    since: new Date('2026-11-05T13:18:00').toISOString(), // 42 min before the fixed clock
    mood: 'visiting',
    favor_pending: FAVOR,
    last_line: 'Hello, small kingdom of tabs. Abhishek sent a little note with me.',
  },
  waiting: {
    host: 'afreen',
    state: 'AWAKE_WAITING',
    present: true,
    soul_holder: 'abhishek',
    since: null,
    mood: 'waiting',
    favor_pending: null,
    last_line: null,
  },
  sleeping: {
    host: 'afreen',
    state: 'ASLEEP',
    present: false,
    soul_holder: 'abhishek',
    since: null,
    mood: 'sleeping',
    favor_pending: null,
    last_line: null,
  },
};

let current: FakeStatus = STATES.visiting!;
let keeper: Server;
const streams = new Set<ServerResponse>();

test.describe('critter', () => {
  test.beforeAll(async () => {
    keeper = createServer((req, res) => {
      res.setHeader('Access-Control-Allow-Origin', req.headers.origin ?? '*');
      const path = new URL(req.url ?? '/', 'http://x').pathname;
      const json = (body: unknown): void => {
        res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(body));
      };
      if (path === '/v1/status') return json(current);
      if (path === '/v1/shell') return json({ pieces: sampleShell });
      if (path === '/v1/events') {
        res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
        res.write(': hello\n\n');
        streams.add(res);
        req.on('close', () => streams.delete(res));
        return;
      }
      res.writeHead(404).end();
    });
    await new Promise<void>((r) => keeper.listen(KEEPER_PORT, '127.0.0.1', r));
  });

  test.afterAll(async () => {
    for (const s of streams) s.end();
    keeper.closeAllConnections();
    await new Promise((r) => keeper.close(r));
  });

  const shots: Record<string, string> = {};

  async function critterPage(browser: Browser, keeperUrl: string): Promise<Page> {
    const ctx = await browser.newContext({
      viewport: { width: 320, height: 300 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    // daytime, so the host is not sent to bed by the clock
    await page.clock.setFixedTime(new Date('2026-11-05T14:00:00'));
    await page.goto(`${CRITTER}critter/index.html?keeper=${encodeURIComponent(keeperUrl)}`);
    await settle(page);
    return page;
  }

  for (const mood of ['visiting', 'waiting', 'sleeping'] as const) {
    test(`critter: ${mood}`, async ({ browser }) => {
      current = STATES[mood]!;
      const page = await critterPage(browser, `http://127.0.0.1:${KEEPER_PORT}`);
      await expect(page.locator(`.pocket-hermit--${mood}`)).toBeVisible();
      if (mood === 'visiting') await page.waitForTimeout(3500); // let the line type out
      const path = out(`critter-${mood}.png`);
      await page.screenshot({ path, omitBackground: true });
      shots[mood] = path;
      await page.context().close();
    });
  }

  test('critter: offline', async ({ browser }) => {
    const page = await critterPage(browser, DEAD_KEEPER);
    await expect(page.locator('.pocket-hermit--offline')).toBeVisible();
    const path = out('critter-offline.png');
    await page.screenshot({ path, omitBackground: true });
    shots.offline = path;
    await page.context().close();
  });

  test('critter: the menu panel', async ({ browser }) => {
    current = STATES.visiting!;
    const ctx = await browser.newContext({
      viewport: { width: 360, height: 520 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.clock.setFixedTime(new Date('2026-11-05T14:00:00'));
    await page.goto(
      `${CRITTER}panel/index.html?keeper=${encodeURIComponent(`http://127.0.0.1:${KEEPER_PORT}`)}`,
    );
    await settle(page);
    await page.waitForTimeout(800);
    await page.screenshot({ path: out('critter-panel.png') });
    shots.panel = out('critter-panel.png');
    await ctx.close();
  });

  test('critter: all states on one card', async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1760, height: 700 } });
    const page = await ctx.newPage();
    const img = (p: string): string =>
      `data:image/png;base64,${readFileSync(p).toString('base64')}`;
    const tile = (k: string, title: string, sub: string): string =>
      `<figure><img src="${img(shots[k]!)}" width="320" height="300"><figcaption><b>${title}</b><span>${sub}</span></figcaption></figure>`;
    await page.setContent(`<!doctype html><html><head>
      <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600&family=Nunito:wght@600&display=swap" rel="stylesheet">
      <style>
        body{margin:0;background:linear-gradient(160deg,#cfe8f1,#f8f1e5 60%,#fbe3d7);font-family:Nunito,system-ui,sans-serif;color:#483424}
        h1{margin:0 0 4px;font:600 30px Fredoka,system-ui}
        p{margin:0 0 18px;font-size:16px}
        .row{display:flex;gap:18px;align-items:flex-end}
        figure{margin:0;display:flex;flex-direction:column;align-items:center}
        figcaption{display:flex;flex-direction:column;align-items:center;gap:2px;margin-top:-6px}
        .menu figcaption{margin-top:12px}
        main{display:inline-block;padding:28px 32px 32px}
        b{font:600 18px Fredoka,system-ui} span{font-size:14px;color:#74604a}
        .panel{border:2.5px solid #5b3d27;border-radius:18px;box-shadow:0 6px 0 #e2d0ad;overflow:hidden;width:270px;height:390px}
        .panel img{width:270px;height:390px;display:block}
      </style></head><body>
      <main><h1>Hermit on every laptop in the group</h1>
      <p>Only one laptop ever has Hermit. Every other one still shows where it is — and says so when it cannot tell.</p>
      <div class="row">
        ${tile('visiting', 'Visiting', 'this laptop has Hermit, and a favor')}
        ${tile('waiting', 'Waiting', 'awake; Hermit is with Abhishek')}
        ${tile('sleeping', 'Sleeping', 'nobody at the keyboard')}
        ${tile('offline', 'Offline', 'cannot reach this keeper')}
        <figure class="menu"><div class="panel"><img src="${img(shots.panel!)}"></div><figcaption><b>Menu</b><span>click Hermit</span></figcaption></figure>
      </div></main></body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(500);
    await page.locator('main').screenshot({ path: out('critter-states.png') });
    await ctx.close();
  });
});

test.afterAll(() => {
  const files = [
    'map-light.png',
    'map-dark.png',
    'map-overview.png',
    'map-impact.png',
    'map-wide.png',
    'map-simulation.png',
    'map-phone.png',
    'postcard.png',
    'route-replay.gif',
    'route-replay.webm',
    'critter-visiting.png',
    'critter-waiting.png',
    'critter-sleeping.png',
    'critter-offline.png',
    'critter-panel.png',
    'critter-states.png',
  ];
  let total = 0;
  for (const f of files) {
    try {
      const n = statSync(out(f)).size;
      total += n;
      console.log(`${f.padEnd(22)} ${(n / 1024).toFixed(0).padStart(6)} KB`);
    } catch {
      console.log(`${f.padEnd(22)}  missing`);
    }
  }
  console.log(`${'total'.padEnd(22)} ${(total / 1024).toFixed(0).padStart(6)} KB`);
});
