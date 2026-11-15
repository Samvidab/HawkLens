import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { E2E_API } from './guard.js'

// Opens every building page with VITE_EMISSIONS_3D on. Each page embeds the building's Matterport tour (Showcase SDK)
// and tags the verified CO2-emitting equipment the survey saw (GET /co2_equipment). Tags are never more than the verified
// items located in the tour; a building without items shows "No verified CO2 sources located in this scan".
// Writes e2e/screens/co2-tags-report.json.
const API = E2E_API // the e2e sandbox backend (temp data copy, cache read-only)
const SHOTS = 'e2e/screens'
fs.mkdirSync(SHOTS, { recursive: true })

let backendUp = false
test.beforeAll(async () => {
  try { backendUp = (await fetch(`${API}/health`)).ok } catch { backendUp = false }
})

const post = async (path, body) => (await fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })).json()

test('every building page: tour via the SDK, one tag per verified CO2 source located in it', async ({ page }) => {
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
    const co2 = await (await fetch(`${API}/co2_equipment/${b.building_id}`)).json()
    for (const it of co2.items) { // only verified claims and pins reach the page
      expect(it.verifier.status).toBe('verified')
      expect(['lighting', 'hvac']).toContain(it.kind)
    }
    await post('/compose', { run_id, type: 'open_building', payload: { building_id: b.building_id } })
    await page.goto('/building')
    await expect(page.getByRole('heading', { name: b.name })).toBeVisible({ timeout: 20_000 })
    const box = page.getByTestId('co2-tour')
    await expect(page.getByTestId('co2-panel')).toBeVisible()
    if (co2.tour_url) await expect(box).toHaveAttribute('data-status', /ready|failed|no-key/, { timeout: 90_000 })
    else await expect(box).toHaveAttribute('data-status', 'no-tour', { timeout: 20_000 })
    const status = await box.getAttribute('data-status')
    const tags = Number(await box.getAttribute('data-tags'))
    const iframes = await page.locator('[data-testid="co2-tour-frame"] iframe').count()

    if (status === 'ready') expect(iframes).toBe(1)
    else expect(iframes).toBe(0)
    expect(tags).toBeLessThanOrEqual(co2.tags_in_tour ? co2.items.length : 0) // never a tag without a verified item
    if (!co2.items.length) await expect(page.getByTestId('co2-none')).toHaveText('No verified CO₂ sources located in this scan')
    await expect(page.getByText(/seen \(verified\)/)).toHaveCount(co2.items.length)

    // click every tagged item in the list: the tour moves to its panorama (the tour itself reports the sweep) and opens its tag
    let visited = 0
    if (status === 'ready') {
      for (let i = 0; i < co2.items.length; i++) {
        const btn = page.getByTestId(`co2-item-${i}`)
        if (await btn.isDisabled()) continue
        await btn.click()
        await expect(box).toHaveAttribute('data-focus-index', String(i))
        await expect(box).toHaveAttribute('data-focus-state', /open|failed/, { timeout: 30_000 })
        expect(await box.getAttribute('data-focus-state')).toBe('open')
        const sweep = await box.getAttribute('data-focus-sweep')
        const tag = await box.getAttribute('data-focus-tag')
        await expect(box).toHaveAttribute('data-current-sweep', sweep, { timeout: 15_000 })
        await expect(box).toHaveAttribute('data-docked-tag', tag, { timeout: 15_000 })
        visited++
        if (visited === 1) { await page.waitForTimeout(2500); await page.screenshot({ path: `${SHOTS}/co2-${b.building_id}-item.png` }) }
      }
      expect(visited).toBe(tags)
    }

    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${SHOTS}/co2-${b.building_id}.png` })
    report.push({
      building: b.name, building_id: b.building_id, scan: co2.model_id, tour: co2.tour_url ? co2.tour_model_id : null, status,
      verified_items: co2.items.length, lighting: co2.items.filter((i) => i.kind === 'lighting').length,
      hvac: co2.items.filter((i) => i.kind === 'hvac').length, tags, visited,
    })
  }
  fs.writeFileSync(`${SHOTS}/co2-tags-report.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
  expect(report).toHaveLength(portfolio.buildings.length)
  expect(errors).toEqual([])
})
