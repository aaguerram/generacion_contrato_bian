import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Los alias siguen las capas de Feature-Sliced Design: un import dice a qué capa pertenece lo que
// trae, así que una violación de la regla de dependencias (una capa baja importando una alta) se
// ve leyendo la línea, sin abrir el archivo de destino.
const capa = (nombre: string) => fileURLToPath(new URL(`./src/${nombre}`, import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@app': capa('app'),
      '@pages': capa('pages'),
      '@widgets': capa('widgets'),
      '@features': capa('features'),
      '@entities': capa('entities'),
      '@shared': capa('shared'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // En desarrollo el navegador habla con Vite y Vite reenvía a la API: mismo origen, sin CORS.
    proxy: { '/api': { target: process.env.API_URL ?? 'http://api:8000', changeOrigin: true } },
  },
})
