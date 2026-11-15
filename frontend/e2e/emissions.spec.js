import { expect, test } from '@playwright/test'
import fs from 'node:fs'

// Opens every building page with VITE_EMISSIONS_3D on. For each building: the legend is always shown; a building with a
// showcase_url gets the Matterport tour through the SDK (or legend only if the SDK fails); tags appear only at positions
// the backend's emissions_3d widget gives, never otherwise. Writes e2e/screens/emissions-report.json.
const API = process.env.E2E_API_URL || 'http://localhost:8000'
const SHOTS = 'e2e/screens'
fs.mkdirSync(SHOTS, { recursive: true })

let backendUp = false
test.beforeAll(async () => {
  try { backendUp = (await fetch(`${API}/health`)).ok } catch { backendUp = false }
})

const post = async (path, body) => (await fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })).json()

test('every building page: tour via the SDK where there is one, tags only from data, legend always', async ({ page }) => {
  test.skip(!backendUp, `no backend at ${API}`)
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  const portfolio = await (await fetch(`${API}/portfolio`)).json()
  const { run_id } = await post('/run', { city: portfolio.city, target_pct: 40, risk_lambda: 0.2 })
  let st = null
  for (let i = 0; i < 120 && !st?.layout; i++) { await new Promise((r) => setTimeout(r, 500)); st = await (await fetch(`${API}/state/${run_id}`)).json().catch(() => null) }
  expect(st?.layout).toBeTruthy()
  await page.addInitScript((id) => sessionStorage.setItem('hawklens.runId', id), run_id)

  const report = []
  for (const b of portfolio.buildings) {
    const layout = await post('/compose', { run_id, type: 'open_building', payload: { building_id: b.building_id } })
    const hero = layout.widgets.find((w) => w.type === 'hero_3d')?.props
    const header = layout.widgets.find((w) => w.type === 'building_header')?.props
    const tourUrl = (hero?.mode === 'showcase' && hero.showcase_url) || header?.profile?.showcase_url || (header?.tour?.available && header.tour.showcase_url) || null
    const em = header?.emissions_3d || null
    const expectedTags = (em?.top || []).slice(0, 3)
      .flatMap((r) => (Array.isArray(r.positions) ? r.positions : []).filter((p) => Array.isArray(p.xyz) && p.xyz.length === 3 && p.xyz.every(Number.isFinite))).length

    await page.goto('/building')
    await expect(page.getByRole('heading', { name: b.name })).toBeVisible({ timeout: 20_000 })
    const box = page.getByTestId('emissions-3d')
    await expect(page.getByTestId('emissions-legend')).toBeVisible()
    if (tourUrl) await expect(box).toHaveAttribute('data-status', /ready|failed|no-key/, { timeout: 60_000 })
    else await expect(box).toHaveAttribute('data-status', 'no-tour')
    const status = await box.getAttribute('data-status')
    const tags = Number(await box.getAttribute('data-tags'))
    const iframe = await page.locator('[data-testid="emissions-tour"] iframe').count()
    const legend = await page.getByTestId('emissions-legend').innerText()

    if (status === 'ready') expect(iframe).toBe(1)
    else expect(iframe).toBe(0) // legend only
    expect(tags).toBe(status === 'ready' ? expectedTags : 0) // never a tag without a backend position
    if (!em) expect(legend).toContain('Emission sources not available')

    await page.screenshot({ path: `${SHOTS}/emissions-${b.building_id}.png` })
    report.push({ building: b.name, building_id: b.building_id, tour: !!tourUrl, status, tags, emissions_data: !!em, legend: legend.replace(/\s+/g, ' ') })
  }
  fs.writeFileSync(`${SHOTS}/emissions-report.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 1))
  expect(report).toHaveLength(portfolio.buildings.length)
  expect(errors).toEqual([])
})

// TEST ONLY: no building has emissions data yet, so this injects SYNTHETIC sources into the API response (in this test's
// browser only) to prove the real Showcase SDK places one coloured tag per given position. Never shown to users.
test('tag pipeline with the real SDK (synthetic test data, test browser only)', async ({ page }) => {
  test.skip(!backendUp, `no backend at ${API}`)
  const portfolio = await (await fetch(`${API}/portfolio`)).json()
  const hero = portfolio.buildings.find((b) => b.hero) || portfolio.buildings[0]
  const { run_id } = await post('/run', { city: portfolio.city, target_pct: 40, risk_lambda: 0.2 })
  let st = null
  for (let i = 0; i < 120 && !st?.layout; i++) { await new Promise((r) => setTimeout(r, 500)); st = await (await fetch(`${API}/state/${run_id}`)).json().catch(() => null) }
  const layout = await post('/compose', { run_id, type: 'open_building', payload: { building_id: hero.building_id } })
  test.skip(!layout.widgets.some((w) => w.type === 'hero_3d' && w.props.showcase_url), 'hero has no tour')
  const row = (end_use, pct, positions) => ({ end_use, category: 'test', pct_of_building: { value: pct, estimate: true, basis: 'TEST' },
    citation: { citation: 'TEST' }, evidence: 'unknown', positions })
  const synthetic = { building_id: hero.building_id, label: 'building-wide estimate, shown where observed', top: [
    row('TEST lighting', 40, [{ xyz: [0, 1, 0] }, { xyz: [1, 1, 0] }]), row('TEST cooling', 30, [{ xyz: [0, 1, 1] }]), row('TEST plug', 10, 'unknown')] }
  await page.route(`${API}/state/${run_id}`, async (route) => {
    const res = await route.fetch(); const body = await res.json()
    const hdr = body.layout?.widgets?.find((w) => w.type === 'building_header')
    if (hdr) hdr.props.emissions_3d = synthetic
    await route.fulfill({ response: res, json: body })
  })
  await page.addInitScript((id) => sessionStorage.setItem('hawklens.runId', id), run_id)
  await page.goto('/building')
  const box = page.getByTestId('emissions-3d')
  await expect(box).toHaveAttribute('data-status', /ready|failed/, { timeout: 60_000 })
  expect(await box.getAttribute('data-status')).toBe('ready')
  expect(await box.getAttribute('data-tags')).toBe('3') // 2 + 1 positions; the source without positions gets none
  await expect(page.getByTestId('emissions-legend')).toContainText('TEST lighting: 40% of building CO₂ (estimated, TEST)')
  await expect(page.getByTestId('emissions-legend')).toContainText('location not observed')
  await page.waitForTimeout(8000)
  await page.screenshot({ path: `${SHOTS}/emissions-tags-synthetic.png` })
})
