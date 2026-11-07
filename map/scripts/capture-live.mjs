/** Capture the local live card in Microsoft Edge, never the desktop or ChatGPT. */
import { chromium } from '@playwright/test';
import { resolve } from 'node:path';

const mapUrl = process.argv[2] ?? 'http://127.0.0.1:5173/';
const keeperUrl = process.argv[3] ?? 'http://127.0.0.1:47800';
const output = process.argv[4] ?? resolve('..', 'docs', 'assets', 'live-presence-afreen.png');
const url = new URL(mapUrl);
url.searchParams.set('live', keeperUrl);

const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(url.toString(), { waitUntil: 'networkidle' });
  const live = page.locator('#live');
  await live.locator('.live__host').first().waitFor({ timeout: 15_000 });
  const text = await live.innerText();
  if (!text.includes('Afreen') || text.includes('stale ·')) {
    throw new Error(`Live panel was not healthy: ${text.slice(0, 400)}`);
  }
  await live.screenshot({ path: output });
  process.stdout.write(`Captured live Edge page: ${output}\n`);
} finally {
  await browser.close();
}
