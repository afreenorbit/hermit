import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// HERMIT_BASE lets GitHub Pages serve the map from /<repo>/.
export default defineConfig({
  base: process.env.HERMIT_BASE ?? '/',
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  test: { include: ['src/**/*.test.ts'] },
});
