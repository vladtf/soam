import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: true, // Enable source maps for better error messages
    minify: false,   // Disable minification in development builds
  },
  server: {
    port: 3000,
  }
})
