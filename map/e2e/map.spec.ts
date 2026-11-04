/** Journey map end-to-end. Owner: C/D. plan.md §7.8. */
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('quest-log')).toBeVisible();
});

test('loads the sample journey, clearly labelled', async ({ page }) => {
  await expect(page.getByRole('note').getByText('SAMPLE DATA')).toBeVisible();
  await expect(page.getByTestId('quest-log').locator('> li')).toHaveCount(8);
  await expect(page.getByRole('status').first()).toContainText('NOW: WITH ABHISHEK');
});

test('clicking a house filters the quest log to that friend', async ({ page, isMobile }) => {
  test.skip(isMobile, 'houses are covered by the desktop run');
  await page.getByRole('button', { name: /^Afreen, Indiranagar/ }).click();
  const cards = page.getByTestId('quest-log').locator('> li');
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText('Afreen');
  await expect(page.getByText('3 OF 8 STOPS')).toBeVisible();
});

test('the completed-favor filter hides stops without a done favor', async ({ page }) => {
  await page.getByRole('radio', { name: /FAVOR DONE/ }).click();
  await expect(page.getByTestId('quest-log').locator('> li')).toHaveCount(6);
});

test('the world sample switches the map to a world view', async ({ page }) => {
  await page.getByRole('radio', { name: 'WORLD' }).click();
  await expect(page).toHaveURL(/data=wide/);
  await expect(page.getByText('WORLD VIEW')).toBeVisible();
  await expect(page.getByRole('status').first()).toContainText('BERLIN');
});

test('MAKE A POSTCARD downloads a PNG', async ({ page }) => {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /MAKE A POSTCARD/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^hermit-postcard-.*\.png$/);
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
