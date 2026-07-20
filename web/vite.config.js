import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serves this repo at /ledgerhawk/ (a project page, not a
  // user/org page) -- only the static (VITE_STATIC) build needs that
  // subpath base; local dev keeps serving from /.
  base: process.env.VITE_STATIC === 'true' ? '/ledgerhawk/' : '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    pool: 'threads',
  },
})
