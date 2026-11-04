/** Journey map end-to-end. Owner: C/D. plan.md §7.8. */
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('quest-log')).toBeVisible();
});

test('loads the sample journey, clearly labelled', async ({ page }) => {
  await expect(page.getByRole('note').getByText('Sample data')).toBeVisible();
  await expect(page.getByTestId('quest-log').locator('> li')).toHaveCount(8);
  await expect(page.getByRole('status').first()).toContainText('Now with Abhishek');
});

test('clicking a house filters the quest log to that friend', async ({ page, isMobile }) => {
  test.skip(isMobile, 'houses are covered by the desktop run');
  await page.getByRole('button', { name: /^Afreen, Indiranagar/ }).click();
  const cards = page.getByTestId('quest-log').locator('> li');
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText('Afreen');
  await expect(page.getByText('3 of 8 stops')).toBeVisible();
});

test('the completed-favor filter hides stops without a done favor', async ({ page }) => {
  await page
    .getByRole('radiogroup', { name: 'Completed favors only' })
    .getByRole('radio', { name: /Favor done/ })
    .click();
  await expect(page.getByTestId('quest-log').locator('> li')).toHaveCount(6);
});

test('the world sample switches the map to a world view', async ({ page }) => {
  await page.getByRole('radio', { name: 'World' }).click();
  await expect(page).toHaveURL(/data=wide/);
  await expect(page.getByText('WORLD VIEW')).toBeVisible();
  await expect(page.getByRole('status').first()).toContainText('Berlin');
});

test('MAKE A POSTCARD downloads a PNG', async ({ page }) => {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /make a postcard/i }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^hermit-postcard-.*\.png$/);
});

test('Tilli acts out a movement when one is picked', async ({ page }) => {
  await page.getByRole('radio', { name: /Sleeping/ }).click();
  await expect(page.locator('.scene__tilli .tilli--sleeping')).toBeVisible();
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
