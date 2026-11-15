// Unit tests for the verified CO2 highlighting (npm test). Separate from vite.config.js so the app's build config is
// unchanged; Playwright specs in e2e/ are not unit tests.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: { include: ['src/**/*.test.{js,jsx}'], environment: 'node' },
})
