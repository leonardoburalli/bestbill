/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const target = env.VITE_API_BASE || 'https://bestbill-api.onrender.com'
  return {
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
