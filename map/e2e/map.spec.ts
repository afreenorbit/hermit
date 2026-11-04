/** Journey map end-to-end. Owner: C/D. plan.md §7.8, §7.9, §9.2. */
import { expect, test, type Page } from '@playwright/test';

const log = (page: Page) => page.getByTestId('quest-log').locator('> li');

test.describe('Bengaluru journey (default)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('./');
    await expect(page.getByTestId('quest-log')).toBeVisible();
  });

  test('loads the sample journey, clearly labelled', async ({ page }) => {
    await expect(page.getByRole('note').getByText('Sample data')).toBeVisible();
    await expect(log(page)).toHaveCount(8);
    await expect(page.getByRole('status').first()).toContainText('Now with Abhishek');
    await expect(page.locator('.sim-stamp')).toHaveCount(0);
  });

  test('clicking a house filters the quest log to that friend', async ({ page, isMobile }) => {
    test.skip(isMobile, 'houses are covered by the desktop run');
    await page.getByRole('button', { name: /^Afreen, Indiranagar/ }).click();
    await expect(log(page)).toHaveCount(3);
    await expect(log(page).first()).toContainText('Afreen');
    await expect(page.getByText('3 of 8 stops')).toBeVisible();
  });

  test('the completed-favor filter hides stops without a done favor', async ({ page }) => {
    await page
      .getByRole('radiogroup', { name: 'Completed favors only' })
      .getByRole('radio', { name: /Favor done/ })
      .click();
    await expect(log(page)).toHaveCount(6);
  });

  test('MAKE A POSTCARD downloads a PNG', async ({ page }) => {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /make a postcard/i }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^hermit-postcard-.*\.png$/);
  });

  test('Hermit acts out a movement when one is picked', async ({ page }) => {
    await page.getByRole('radio', { name: /Sleeping/ }).click();
    await expect(page.locator('.scene__tilli .pocket-hermit--sleeping')).toBeVisible();
    await expect(page.locator('.scene__bubble')).toContainText('bedtime');
  });

  test('no horizontal page scroll', async ({ page }) => {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('theme toggle switches to dark and back', async ({ page }) => {
    const html = page.locator('html');
    await page.getByRole('button', { name: /Dark theme|Light theme/ }).click();
    const first = await html.getAttribute('data-theme');
    await page.getByRole('button', { name: /Dark theme|Light theme/ }).click();
    expect(await html.getAttribute('data-theme')).not.toBe(first);
  });

  test('replay walks Hermit along the whole route', async ({ page, isMobile }) => {
    test.skip(isMobile, 'one run is enough');
    await page.getByRole('button', { name: 'REPLAY', exact: true }).click();
    await expect(page.locator('.world__hop')).toContainText(/Hop \d+ of 7/);
    await page.getByRole('button', { name: 'STOP', exact: true }).click();
    await expect(page.locator('.world__hop')).toHaveCount(0);
  });
});

test.describe('scenario picker and honest labelling', () => {
  test('?journey=three_cities shows the simulator run with a SIMULATION badge', async ({
    page,
  }) => {
    await page.goto('./?journey=three_cities');
    await expect(page.getByTestId('quest-log')).toBeVisible();
    await expect(page.getByRole('note')).toContainText(/simulation/i);
    await expect(page.getByRole('note')).toContainText('three_cities_day');
    await expect(page.locator('.sim-stamp')).toHaveText('SIMULATION');
    await expect(page.locator('.world__sim')).toHaveText('SIMULATION');
    await expect(page.locator('.world__mode')).toContainText('WORLD VIEW');
    await expect(log(page)).toHaveCount(4);
    await expect(page).toHaveTitle(/SIMULATION/);
  });

  test('the picker flips between journeys and keeps the choice in the URL', async ({ page }) => {
    await page.goto('./');
    const picker = page.getByRole('radiogroup', { name: 'Which journey' });
    await picker.getByRole('radio', { name: /3 cities/ }).click();
    await expect(page).toHaveURL(/journey=three_cities/);
    await expect(page.locator('.sim-stamp')).toBeVisible();
    // pressing the active option keeps it
    await picker.getByRole('radio', { name: /3 cities/ }).click();
    await expect(page).toHaveURL(/journey=three_cities/);

    await picker.getByRole('radio', { name: /World/ }).click();
    await expect(page).toHaveURL(/journey=world/);
    await expect(page.locator('.sim-stamp')).toHaveCount(0);
    await expect(page.getByRole('note').getByText('Sample data')).toBeVisible();
    await expect(page.getByRole('status').first()).toContainText('Berlin');

    await picker.getByRole('radio', { name: 'Bengaluru' }).click();
    await expect(page.getByText(/CITY VIEW/)).toBeVisible();
  });

  test('the old ?data=wide link still works', async ({ page }) => {
    await page.goto('./?data=wide');
    await expect(page.locator('.world__mode')).toContainText('WORLD VIEW');
  });
});

test.describe('the map fits every friend', () => {
  for (const journey of ['bengaluru', 'three_cities', 'world']) {
    test(`all houses are inside the map (${journey})`, async ({ page }) => {
      await page.goto(`./?journey=${journey}`);
      await expect(page.getByTestId('quest-log')).toBeVisible();
      const stage = await page.locator('.world__stage').boundingBox();
      const houses = page.locator('.world__house');
      await expect(houses).toHaveCount(3);
      for (const box of await houses.evaluateAll((els) =>
        els.map((e) => e.getBoundingClientRect().toJSON() as DOMRect),
      )) {
        expect(box.left).toBeGreaterThanOrEqual(stage!.x);
        expect(box.top).toBeGreaterThanOrEqual(stage!.y);
        expect(box.right).toBeLessThanOrEqual(stage!.x + stage!.width);
        expect(box.bottom).toBeLessThanOrEqual(stage!.y + stage!.height);
      }
    });
  }
});

test.describe('empty, loading and error states', () => {
  test('a missing journey says so and can retry', async ({ page }) => {
    let fail = true;
    await page.route('**/data/journey.three_cities.json', (route) =>
      fail ? route.fulfill({ status: 404, body: 'nope' }) : route.fallback(),
    );
    await page.goto('./?journey=three_cities');
    const alert = page.getByRole('alert');
    await expect(alert).toContainText('couldn’t find this journey');
    await expect(alert).toContainText('HTTP 404');
    fail = false;
    await alert.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByTestId('quest-log')).toBeVisible();
  });

  test('a journey that breaks the schema is reported, not rendered', async ({ page }) => {
    await page.route('**/data/journey.three_cities.json', (route) =>
      route.fulfill({ json: { v: 2 } }),
    );
    await page.goto('./?journey=three_cities');
    await expect(page.getByRole('alert')).toContainText('does not match the schema');
    await page.getByRole('button', { name: 'Show the Bengaluru journey' }).click();
    await expect(page.getByTestId('quest-log')).toBeVisible();
  });

  test('a journey with no stops yet shows the empty state', async ({ page }) => {
    await page.route('**/data/journey.three_cities.json', async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      await route.fulfill({
        json: {
          ...j,
          stops: [],
          shell: [],
          hermit: { current_host: null, current_city: null, since: null },
        },
      });
    });
    await page.goto('./?journey=three_cities');
    await expect(page.getByText('Hermit hasn’t left its first laptop yet.')).toBeVisible();
    await expect(page.getByText('No shell yet.', { exact: false })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('while loading, Hermit follows the footprints', async ({ page }) => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => (release = r));
    await page.route('**/data/journey.three_cities.json', async (route) => {
      await gate;
      await route.fallback();
    });
    await page.goto('./?journey=three_cities');
    await expect(page.getByRole('status').filter({ hasText: 'footprints' })).toBeVisible();
    release();
    await expect(page.getByTestId('quest-log')).toBeVisible();
  });
});
