import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/Atlas/',
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash]-habitat-ai.js',
        chunkFileNames: 'assets/[name]-[hash]-habitat-ai.js',
      },
    },
  },
});
