import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import type { PluginOption } from 'vite';

export default defineConfig({
  plugins: [react() as unknown as PluginOption],
  base: './',
  build: {
    outDir: 'dist',
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
