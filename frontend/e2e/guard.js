// Playwright global setup: refuse to run unless the API is the e2e sandbox (backend/scripts/e2e_backend.sh: a temp copy of
// the demo data, cache read-only). The tests start surveys and approve plans, so they must never reach the demo backend.
export const E2E_API = process.env.E2E_API_URL || 'http://localhost:8100'

export default async function guard() {
  let h
  try { h = await (await fetch(`${E2E_API}/health`)).json() } catch (e) {
    throw new Error(`e2e guard: no backend at ${E2E_API} (${e.message})`)
  }
  if (h.sandbox !== true || h.cache_mode !== 'read_only') {
    throw new Error(`e2e guard: refusing to run against ${E2E_API}: it is not the e2e sandbox ` +
      `(sandbox=${h.sandbox}, cache_mode=${h.cache_mode}). Start the tests with their own backend (see playwright.config.js).`)
  }
}
