import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'electron-vite';

export default defineConfig({
  main: { build: { lib: { entry: 'src/main/index.ts' } } },
  preload: { build: { lib: { entry: 'src/preload/index.ts' } } },
  renderer: {
    root: 'src/renderer',
    plugins: [tailwindcss()],
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
