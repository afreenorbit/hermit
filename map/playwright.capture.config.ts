import { defineConfig } from '@playwright/test';

// README / submission assets → docs/assets/.   pnpm --filter @hermit/map capture
// Serves the built map and the critter's browser preview, then e2e/capture.spec.ts
// photographs them. Not part of the e2e gate; run it when the UI changes.
export default defineConfig({
  testDir: 'e2e',
  testMatch: 'capture.spec.ts',
  workers: 1,
  timeout: 180_000,
  reporter: 'list',
  use: { trace: 'off' },
  webServer: [
    {
      command: 'pnpm exec vite build && pnpm exec vite preview --port 4174 --strictPort',
      url: 'http://localhost:4174',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        'pnpm --dir ../critter exec vite --config vite.web.config.mts --port 5175 --strictPort',
      url: 'http://localhost:5175/critter/index.html',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
