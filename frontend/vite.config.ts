import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production'
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      host: true, // Allow external connections
      allowedHosts: [
        'localhost',
        '127.0.0.1',
        'weevoice-web-production.up.railway.app',
        '.railway.app', // Allow all Railway subdomains
      ],
      proxy: {
        '/api': {
          target: process.env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: !isProduction,
    },
    preview: {
      port: 3000,
      host: true,
      allowedHosts: [
        'localhost',
        '127.0.0.1',
        'weevoice-web-production.up.railway.app',
        '.railway.app',
      ],
    },
  }
})

