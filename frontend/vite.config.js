import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,           // ★ 监听所有网卡（0.0.0.0），穿透工具才能连进来
    allowedHosts: true,   // ★ 允许任意 Host 头，穿透域名不会被 403
    port: 5173,
    proxy: {
      // SSE 跨域代理：前端 /api/* → 后端 http://localhost:8000/*
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE 必须禁用缓冲
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-Accel-Buffering', 'no')
          })
        },
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
