import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws/chat': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/ws/dashboard': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
