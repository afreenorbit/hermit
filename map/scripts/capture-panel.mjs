/** Capture the local companion menu in Microsoft Edge, never a desktop window. */
import { chromium } from '@playwright/test';

const panelUrl = process.argv[2] ?? 'http://127.0.0.1:5177/panel/index.html';
const output = process.argv[3] ?? '../docs/assets/live-quest-afreen.png';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 720 }, deviceScaleFactor: 1 });
  await page.goto(panelUrl, { waitUntil: 'domcontentloaded' });
  await page.getByText('With you', { exact: false }).first().waitFor({ timeout: 15_000 });
  await page.locator('.menu__quest').waitFor({ timeout: 15_000 });
  await page.screenshot({ path: output, fullPage: true });
  process.stdout.write(`Captured live companion preview in Edge: ${output}\n`);
} finally {
  await browser.close();
}
