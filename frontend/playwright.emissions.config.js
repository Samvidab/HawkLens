import { defineConfig } from '@playwright/test'
import { E2E_API } from './e2e/guard.js'

// Verified CO2 sources in 3D (VITE_EMISSIONS_3D=1): opens all 8 building pages. Like the main suite, Playwright starts its
// own backend (backend/scripts/e2e_backend.sh: temp copy of the demo data, cache read-only; e2e/guard.js refuses any other
// API) and a dev server on :3000 with the flag on. The SDK key comes from frontend/.env.local (never committed).
//   run: npx playwright test -c playwright.emissions.config.js
const port = new URL(E2E_API).port || '8100'
export default defineConfig({
  testDir: './e2e',
  testMatch: /emissions\.spec\.js/,
  globalSetup: './e2e/guard.js',
  timeout: 300_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:3000', viewport: { width: 1500, height: 1050 }, screenshot: 'off' },
  webServer: [
    {
      command: 'bash ../backend/scripts/e2e_backend.sh',
      url: `${E2E_API}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { ...process.env, E2E_PORT: port },
    },
    {
      command: 'npm run dev -- --port 3000 --strictPort',
      url: 'http://localhost:3000',
      reuseExistingServer: false,
      env: { ...process.env, VITE_API_URL: E2E_API, VITE_EMISSIONS_3D: '1' },
    },
  ],
})
