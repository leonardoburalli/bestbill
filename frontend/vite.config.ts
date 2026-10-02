/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'

// Single source of truth: version in ../pyproject.toml (fallback: package.json).
function appVersion(): string {
  try {
    const m = readFileSync(new URL('../pyproject.toml', import.meta.url), 'utf8').match(/^version = "([^"]+)"/m)
    if (m) return m[1]
  } catch {
    /* fall through */
  }
  return JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  // Dev proxy target. BESTBILL_API_PROXY=http://localhost:8000 → local API (make frontend-dev).
  const target = env.BESTBILL_API_PROXY || env.VITE_API_BASE || 'https://bestbill-api.onrender.com'
  return {
    define: { __APP_VERSION__: JSON.stringify(appVersion()) },
    plugins: [react(), tailwindcss()],
    server: {
      // The app calls same-origin /api/*; in dev the proxy forwards it.
      proxy: { '/api': { target, changeOrigin: true } },
    },
    build: { outDir: 'dist' },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
