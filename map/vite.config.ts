import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Relative base ('./') so `map/dist` works wherever it is hosted: the domain
// root (Vercel), a sub-path (GitHub Pages /<repo>/) or a plain folder. Data is
// fetched relative to the page too. HERMIT_BASE still overrides it.
export default defineConfig({
  base: process.env.HERMIT_BASE ?? './',
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  build: { chunkSizeWarningLimit: 800 },
  test: { include: ['src/**/*.test.ts'] },
});
