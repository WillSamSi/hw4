import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Respect PORT if set (e.g. when 5173 is already taken); default to Vite's 5173.
    port: Number(process.env.PORT) || 5173,
    // Forward API and product-image requests to the FastAPI backend.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/images': 'http://127.0.0.1:8000',
    },
  },
})
