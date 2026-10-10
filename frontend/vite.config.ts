import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In Docker Compose the backend is reachable as 'backend:8500'
const BACKEND_TARGET = process.env.VITE_API_URL
  ? undefined  // explicit URL set — use direct fetch
  : 'http://backend:8500';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3500,
    proxy: BACKEND_TARGET
      ? {
          '/ingest':       { target: BACKEND_TARGET, changeOrigin: true },
          '/documents':    { target: BACKEND_TARGET, changeOrigin: true },
          '/qa':           { target: BACKEND_TARGET, changeOrigin: true },
          '/settings':     { target: BACKEND_TARGET, changeOrigin: true },
          '/collections':  { target: BACKEND_TARGET, changeOrigin: true },
          '/health':       { target: BACKEND_TARGET, changeOrigin: true },
        }
      : undefined,
  },
});
