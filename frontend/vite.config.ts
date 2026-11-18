import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The FastAPI backend. In development the React app runs on Vite's own
// server (port 5173) and API calls are forwarded here, so the browser sees
// one site and no CORS setup is needed. In production FastAPI serves the
// built files itself, so the same relative URLs keep working.
const API = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': API,
      '/chat': API,
      '/chats': API,
      '/documents': API,
      '/upload': API,
      '/health': API,
    },
  },
  test: {
    // A simulated browser, so component tests run in the terminal and in CI.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
