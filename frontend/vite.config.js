import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// En local sube un nivel para leer el .env único en la raíz del repo.
// En Railway/Docker el .env no existe: usa la variable de entorno directamente.
const REPO_ROOT = path.resolve(__dirname, '..')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, REPO_ROOT, '')

  // process.env.VITE_API_BASE tiene prioridad (inyectado por Docker ARG/Railway)
  const apiBase = process.env.VITE_API_BASE ?? env.VITE_API_BASE ?? ''

  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_API_BASE': JSON.stringify(apiBase),
    },
    server: {
      port: 5173,
      // Proxy para evitar CORS en dev local
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})

