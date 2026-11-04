import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, externalizeDepsPlugin } from 'electron-vite';

export default defineConfig({
  main: { plugins: [externalizeDepsPlugin()], build: { lib: { entry: 'src/main/index.ts' } } },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: { lib: { entry: 'src/preload/index.ts' } },
  },
  renderer: {
    root: 'src/renderer',
    plugins: [react(), tailwindcss()],
    build: {
      rollupOptions: {
        input: {
          critter: 'src/renderer/critter/index.html',
          panel: 'src/renderer/panel/index.html',
        },
      },
    },
  },
});
