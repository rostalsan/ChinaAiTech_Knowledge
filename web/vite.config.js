import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发态：client 跑在 5173，API 与全文走 8787 的 Express
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8787',
      '/fulltext': 'http://localhost:8787'
    }
  }
})
