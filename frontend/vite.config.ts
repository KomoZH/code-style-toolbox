import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 构建产物 → backend/app/static，由 FastAPI 托管；dev 代理 /api 到本地后端
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:18765',
    },
  },
});
