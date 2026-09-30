import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'

// Dev: the Vite server proxies /api to FastAPI so the browser sees a single origin
// (session cookie + CSRF). In production Caddy does the same.
const api = process.env.PULSO_API ?? 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // frappe-gantt's exports map hides its stylesheet (only reachable via the "style" condition,
      // which comes after "import"), so it gets an explicit alias.
      'frappe-gantt.css': fileURLToPath(new URL('./node_modules/frappe-gantt/dist/frappe-gantt.css', import.meta.url)),
    },
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': { target: api, changeOrigin: false } } },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy: { '/api': { target: api, changeOrigin: false } } },
  test: { environment: 'jsdom', include: ['tests/unit/**/*.spec.ts'] },
})
