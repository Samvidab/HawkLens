import { defineConfig } from '@playwright/test'

// End-to-end check of the wiring against a RUNNING backend (see e2e/README.md).
//   backend:  cd backend && scripts/run_server.sh        (CACHE_MODE=read_only + a warm cache makes the survey take seconds)
//   run:      cd frontend && npx playwright test
const API = process.env.E2E_API_URL || 'http://localhost:8000'
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:5173', viewport: { width: 1500, height: 1050 }, screenshot: 'off' },
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    env: { VITE_API_URL: API },
  },
})
