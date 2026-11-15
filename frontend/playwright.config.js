import { defineConfig } from '@playwright/test'
import os from 'node:os'
import path from 'node:path'

// Browser checks of the verified CO2 highlighting (npm run e2e) against a RUNNING site and backend:
//   E2E_SITE (default http://localhost:3000): the frontend started with VITE_EMISSIONS_3D=true
//   E2E_API  (default http://localhost:8000): the same VITE_API_URL backend the site uses
// Nothing is started by these tests and nothing is written in the repo: results and screenshots go to the temp folder.
export default defineConfig({
  testDir: './e2e',
  outputDir: path.join(os.tmpdir(), 'hawklens-playwright-results'),
  timeout: 900_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_SITE || 'http://localhost:3000', viewport: { width: 1500, height: 1050 }, screenshot: 'off' },
})
