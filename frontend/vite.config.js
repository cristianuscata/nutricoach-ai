import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Sube un nivel para leer el .env único en la raíz del repo
const REPO_ROOT = path.resolve(__dirname, '..')

export default defineConfig(({ mode }) => {
  // Carga variables VITE_* desde la raíz del repositorio
  const env = loadEnv(mode, REPO_ROOT, '')

  return {
    plugins: [react()],
    // Expone las variables al código de la app
    define: {
      'import.meta.env.VITE_API_BASE': JSON.stringify(env.VITE_API_BASE ?? ''),
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

