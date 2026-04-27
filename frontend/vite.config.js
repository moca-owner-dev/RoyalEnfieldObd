import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // bind explícito a IPv4 — algunos clientes hacen DNS lookup por IPv6 primero
    host: '127.0.0.1',
    proxy: {
      '/api': {
        // 127.0.0.1 directo (sin DNS) — evita ENOTFOUND cuando estás
        // conectado al WiFi del dongle (que no tiene DNS server)
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
