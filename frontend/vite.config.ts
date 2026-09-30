import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_BASE = process.env.VITE_API_BASE || 'https://bestbill-api.onrender.com'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API_BASE,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
