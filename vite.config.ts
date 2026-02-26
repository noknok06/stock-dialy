import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  root: 'frontend',
  base: '/static/dist/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        'stock-search': 'frontend/src/stock-search.tsx',
      },
    },
  },
  server: {
    port: 5173,
    origin: 'http://localhost:5173',
  },
})
