import { defineConfig, devices } from '@playwright/test';

// pnpm --filter @hermit/map e2e   (first time: pnpm --filter @hermit/map exec playwright install chromium)
export default defineConfig({
  testDir: 'e2e',
  testIgnore: ['capture.spec.ts'],
  fullyParallel: true,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
    // Local Windows runs can use installed Edge without downloading Chromium.
    channel: process.env.HERMIT_BROWSER === 'edge' ? 'msedge' : undefined,
  },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js build && node node_modules/vite/bin/vite.js preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
});
