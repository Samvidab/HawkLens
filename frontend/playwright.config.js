import { defineConfig } from '@playwright/test'
import { E2E_API } from './e2e/guard.js'

// End-to-end check of the wiring. Playwright starts its OWN backend (backend/scripts/e2e_backend.sh): a temp copy of the
// demo data and CACHE_MODE=read_only, so the tests can never write to the demo data dir; e2e/guard.js refuses any other API.
//   run:  cd frontend && npx playwright test
//   env:  DEMO_DATA_DIR (data to copy, default backend/data), CACHE_DIR (the warm cache), E2E_ENV_FILE (default backend/.env),
//         PYTHON (python with the backend deps)
const port = new URL(E2E_API).port || '8100'
export default defineConfig({
  testDir: './e2e',
  testIgnore: /emissions\.spec\.js/, // runs with its own config (flag on): playwright.emissions.config.js
  globalSetup: './e2e/guard.js',
  timeout: 120_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:5173', viewport: { width: 1500, height: 1050 }, screenshot: 'off' },
  webServer: [
    {
      command: 'bash ../backend/scripts/e2e_backend.sh',
      url: `${E2E_API}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { ...process.env, E2E_PORT: port },
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: false,
      env: { ...process.env, VITE_API_URL: E2E_API },
    },
  ],
})
