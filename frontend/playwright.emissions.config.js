import { defineConfig } from '@playwright/test'

// Emissions in 3D, against a RUNNING backend: a dev server with VITE_EMISSIONS_3D=1 on port 3000 (allowed by the backend's default CORS), so the main suite
// (playwright.config.js, flag off) is unaffected. The SDK key comes from frontend/.env.local (never committed).
//   run: npx playwright test -c playwright.emissions.config.js
const API = process.env.E2E_API_URL || 'http://localhost:8000'
export default defineConfig({
  testDir: './e2e',
  testMatch: /emissions\.spec\.js/,
  timeout: 300_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:3000', viewport: { width: 1500, height: 1050 }, screenshot: 'off' },
  webServer: {
    command: 'npm run dev -- --port 3000 --strictPort',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    env: { VITE_API_URL: API, VITE_EMISSIONS_3D: '1' },
  },
})
