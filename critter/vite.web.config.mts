// Browser-only preview of both renderer windows, for design work without
// Electron: `pnpm --filter @hermit/critter dev:web` → http://localhost:5174
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  root: 'src/renderer',
  plugins: [react(), tailwindcss()],
  server: { port: 5174 },
  test: { root: '.', include: ['src/**/*.test.ts'] },
});
