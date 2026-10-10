import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    // 仅监听本机回环（显式 IPv4，localhost 与 127.0.0.1 都可达）：
    // 启动时只打印 Local 一行，不再输出 VMware 虚拟网卡等无效 Network 地址
    // （需要手机 / 局域网设备联调时，改回 '0.0.0.0' 并放行防火墙入站即可）
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
