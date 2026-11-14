import { expect, test } from '@playwright/test'
import fs from 'node:fs'

const API = process.env.E2E_API_URL || 'http://localhost:8000'
const SHOTS = 'e2e/screens'
fs.mkdirSync(SHOTS, { recursive: true })
const shot = (page, name) => page.screenshot({ path: `${SHOTS}/${name}.png` })

test.describe.configure({ mode: 'serial' })
let backendUp = false
test.beforeAll(async () => {
  try { backendUp = (await fetch(`${API}/health`)).ok } catch { backendUp = false }
})
test.beforeEach(() => test.skip(!backendUp, `no backend at ${API}`))

test('goal form -> live survey -> workspace -> actions -> evidence -> approval, all from the API', async ({ page }) => {
  const calls = []
  page.on('request', (r) => { if (r.url().startsWith(API)) calls.push(`${r.method()} ${new URL(r.url()).pathname}`) })
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  const portfolio = await (await fetch(`${API}/portfolio`)).json()
  const names = portfolio.buildings.map((b) => b.name)

  // 1. Start survey: the building list is the real portfolio, not the prototype's HOU-01..08
  await page.goto('/start-survey')
  await expect(page.getByText(names[0], { exact: true })).toBeVisible()
  await expect(page.getByText(`${names.length} buildings`).first()).toBeVisible()
  await shot(page, '1-start-survey')

  // 2. POST /run, then the SSE feed fills the survey screen and the page advances by itself on `done`
  await page.getByRole('button', { name: 'Start survey' }).click()
  await expect(page).toHaveURL(/survey-in-progress/)
  await expect(page.getByText(/· [1-9]\d* events/).first()).toBeVisible({ timeout: 30_000 }) // the feed is filling
  await shot(page, '2-survey-in-progress')
  await expect(page).toHaveURL(/survey-complete/, { timeout: 90_000 })
  await expect(page.getByText(new RegExp(`${names.length} buildings ready`))).toBeVisible()
  await expect(page.getByText('Workspace ready').first()).toBeVisible({ timeout: 30_000 })
  await shot(page, '3-survey-complete')

  // 3. Workspace: Portfolio shows the layout's numbers; the slider sends set_target when it settles
  await page.getByRole('button', { name: 'Open workspace' }).click()
  await expect(page.getByText('Live backend')).toBeVisible()
  const slider = page.getByRole('slider', { name: 'Carbon reduction target' })
  await slider.focus()
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowLeft') // 40 % -> 20 %
  await expect(slider).toHaveAttribute('aria-valuenow', '20')
  await expect(page.getByText(/Your goal is covered|Short of your goal/)).toBeVisible()
  await page.waitForResponse((r) => r.url().endsWith('/compose') && r.request().postDataJSON().type === 'set_target')
  await expect(page.getByText(/updating…/)).toHaveCount(0)
  await expect(page.getByText('Your goal is covered')).toBeVisible()
  await shot(page, '4-portfolio-20pct')

  // 4. Plan: metrics, abatement bars and the per-type table come from the plan
  await page.getByRole('button', { name: 'Review plan' }).click()
  await expect(page).toHaveURL(/\/plan/)
  await expect(page.getByText('tonnes / year').first()).toBeVisible()
  expect(await page.locator('[title*=" · "][class*="absolute"]').count()).toBeGreaterThan(3) // bars are titled "<upgrade> · <building>"
  await expect(page.getByText('Rooftop solar').first()).toBeVisible()
  await shot(page, '5-plan')

  // 5. Risk and target: 30 real histogram bins
  await page.getByRole('button', { name: /Risk & target details/ }).click()
  await expect(page).toHaveURL(/risk-and-target/)
  await expect(page.getByText('Chance of a loss')).toBeVisible()
  await shot(page, '6-risk')

  // 6. Building detail from a real building: toggle an upgrade -> POST /compose toggle_upgrade -> plan changes
  await page.goto('/')
  await page.getByRole('button', { name: /View building/ }).click()
  await expect(page).toHaveURL(/\/building/)
  const hero = portfolio.buildings.find((b) => b.hero) || portfolio.buildings[0]
  await expect(page.getByRole('heading', { name: hero.name })).toBeVisible()
  const sw = page.getByRole('switch').first()
  const before = await sw.getAttribute('aria-checked')
  const toggled = page.waitForResponse((r) => r.url().endsWith('/compose') && ['toggle_upgrade', 'include_unverified'].includes(r.request().postDataJSON().type))
  await sw.click()
  await toggled
  await expect(page.getByRole('switch').first()).not.toHaveAttribute('aria-checked', before, { timeout: 15_000 })
  await shot(page, '7-building')

  // 7. Evidence: images are served by /media/{image_id}
  await page.goto('/survey-evidence')
  await expect(page.locator(`img[src^="${API}/media/"]`).first()).toBeVisible()
  expect(await page.locator(`img[src^="${API}/media/"]`).first().evaluate((i) => i.complete && i.naturalWidth > 0)).toBe(true)
  await shot(page, '8-evidence')

  // 8. Approve: consent + Approve & fund -> POST /compose approve {plan_id} -> confirmation with Nessie ids
  await page.goto('/financing-approval')
  await expect(page.getByText('Hawk Lens Retrofit Reserve')).toBeVisible({ timeout: 15_000 }) // the resumed run's plan has loaded
  await page.getByRole('checkbox').click()
  const approved = page.waitForResponse((r) => r.url().endsWith('/compose') && r.request().postDataJSON().type === 'approve')
  await page.getByRole('button', { name: 'Approve & fund' }).click()
  expect((await approved).status()).toBe(200)
  await expect(page).toHaveURL(/funding-confirmation/)
  const nessieMode = (await (await fetch(`${API}/health`)).json()).nessie_mode
  await expect(page.getByText(nessieMode === 'live' ? /Recorded in the Nessie sandbox/ : /Simulated confirmation \(stub Nessie\)/)).toBeVisible()
  await expect(page.getByText(/\d+ upgrades across \d+ buildings/)).toBeVisible() // the summary is the approved plan's, not the prototype's
  await shot(page, '9-funded')

  // the contract calls the App Flow spec lists were all made
  for (const c of ['GET /portfolio', 'POST /run', 'GET /events/' + calls.find((x) => x.startsWith('GET /events/'))?.split('/')[2], 'POST /compose']) {
    expect(calls.some((x) => x.startsWith(c.split(' /')[0] + ' /' + c.split(' /')[1].split('/')[0])), c).toBe(true)
  }
  expect(calls.filter((c) => c.startsWith('GET /state/')).length).toBeGreaterThan(0)
  expect(errors).toEqual([])
})

test('a reload resumes the run from sessionStorage and shows the same workspace', async ({ page }) => {
  // a run made earlier (here: through the API), remembered by the page like after a browser reload
  const { run_id } = await (await fetch(`${API}/run`, { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ city: 'Houston', target_pct: 20, risk_lambda: 0.5 }) })).json()
  let st = null
  for (let i = 0; i < 60 && !st?.layout; i++) { await new Promise((r) => setTimeout(r, 500)); st = await (await fetch(`${API}/state/${run_id}`)).json().catch(() => null) }
  expect(st?.layout).toBeTruthy()
  await page.addInitScript((id) => sessionStorage.setItem('hawklens.runId', id), run_id)
  await page.goto('/plan')
  await expect(page.getByText(/Quant engine pricing|Sample pricing/)).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('20% reduction goal')).toBeVisible()
  await page.reload() // and again: still resumes
  await expect(page.getByText(/Quant engine pricing|Sample pricing/)).toBeVisible({ timeout: 20_000 })
  await shot(page, '10-resumed-plan')
})

test('the prototype still renders without a backend (static fallback)', async ({ page }) => {
  await page.route(`${API}/**`, (r) => r.abort())
  await page.addInitScript(() => sessionStorage.clear())
  await page.goto('/')
  await expect(page.getByText('Interactive demo')).toBeVisible()
  await expect(page.getByText('Your goal is covered')).toBeVisible()
  await page.goto('/plan')
  await expect(page.getByText('1032 tonnes / year')).toBeVisible()
})
