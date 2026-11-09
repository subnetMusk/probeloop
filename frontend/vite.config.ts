import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the SPA runs on Vite (port 5173) and calls the backend through this proxy, so
// the browser sees a single origin. In production the backend serves the built files itself.
const backend = process.env.PROBELOOP_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: backend },
      '/health': { target: backend },
      // The Sign in with ChatGPT callback (http://127.0.0.1:<port>/auth/callback).
      '/auth': { target: backend },
      '/ws': { target: backend, ws: true },
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
