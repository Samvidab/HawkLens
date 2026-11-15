import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { E2E_API } from './guard.js'
import { ROUTES, inventedIn } from '../src/test/forbidden.js'

const API = E2E_API // the e2e sandbox backend (temp data copy, cache read-only); see playwright.config.js
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
  await expect(page.getByTestId('sources')).toContainText('Pricing:')
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
  await expect.poll(() => page.locator(`img[src^="${API}/media/"]`).first().evaluate((i) => i.complete && i.naturalWidth > 0), { timeout: 10_000 }).toBe(true) // the real image loaded
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
  await expect(page.getByText(nessieMode === 'live' ? /Recorded in the Nessie sandbox/ : /Simulated booking \(stub Nessie\)/)).toBeVisible()
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
  await expect(page.getByText('20% reduction goal')).toBeVisible({ timeout: 20_000 })
  await page.reload() // and again: still resumes
  await expect(page.getByText('20% reduction goal')).toBeVisible({ timeout: 20_000 })
  await shot(page, '10-resumed-plan')
})

test('the risk control is live: Growth -> Balanced -> Cautious re-plans and changes the plan', async ({ page }) => {
  const health = await (await fetch(`${API}/health`)).json()
  // a run at lambda 0 (Growth: expected NPV only), target 20 %
  const { run_id } = await (await fetch(`${API}/run`, { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ city: 'Houston', target_pct: 20, risk_lambda: 0 }) })).json()
  let st = null
  for (let i = 0; i < 60 && !st?.layout; i++) { await new Promise((r) => setTimeout(r, 500)); st = await (await fetch(`${API}/state/${run_id}`)).json().catch(() => null) }
  expect(st?.layout).toBeTruthy()
  const supported = st.layout.widgets.find((w) => w.type === 'target_control').props.risk_supported
  await page.addInitScript((id) => sessionStorage.setItem('hawklens.runId', id), run_id)

  const metric = (label) => page.locator(`p:has-text("${label}") + p`).first()
  const planNumbers = async () => {
    await page.goto('/plan')
    await expect(page.getByText(/reduction goal/)).toBeVisible({ timeout: 20_000 })
    return { upfront: await metric('Upfront investment').textContent(), npv: await metric('Lifetime net value').textContent(), text: await page.locator('body').innerText() }
  }
  const pickRisk = async (name, lambda) => {
    await page.goto('/plan-preferences')
    const chip = page.getByRole('button', { name, exact: true })
    await expect(chip).toBeVisible({ timeout: 20_000 })
    const done = page.waitForResponse((r) => r.url().endsWith('/compose') && r.request().postDataJSON().type === 'set_risk' && r.request().postDataJSON().payload.risk_lambda === lambda, { timeout: 30_000 })
    await chip.click()
    expect((await done).status()).toBe(200)
    await expect(chip).toHaveAttribute('aria-pressed', 'true')
  }

  if (!supported) { // stub engine: the control must be disabled and say why
    await page.goto('/plan-preferences')
    await expect(page.getByRole('button', { name: 'Balanced', exact: true })).toBeDisabled({ timeout: 20_000 })
    await expect(page.getByText(/not applied by the current pricing engine/)).toBeVisible()
    return
  }
  expect(health.engine_mode).toBe('live')
  const growth = await planNumbers()
  await shot(page, '11-plan-growth')
  await expect(page.getByText('Midtown roof verified')).toHaveCount(0) // never the prototype's activity next to a real plan
  await expect(page.getByText('Workspace ready').first()).toBeVisible({ timeout: 15_000 }) // this run's own events
  await page.goto('/plan-preferences')                     // the loaded plan's own position is shown after a reload
  await expect(page.getByRole('button', { name: 'Growth', exact: true })).toHaveAttribute('aria-pressed', 'true', { timeout: 20_000 })
  await expect(page.getByText(/Budget No cap · Growth risk/)).toBeVisible()

  await pickRisk('Balanced', 0.2)                      // the middle position = lambda 0.2
  await shot(page, '12-preferences-balanced')
  const balanced = await planNumbers()
  await shot(page, '13-plan-balanced')
  await expect(page.getByText('re-plan: risk appetite 0.2')).toBeVisible({ timeout: 15_000 }) // the action just taken (recorded events after the survey's `done`)
  expect(balanced.upfront !== growth.upfront || balanced.npv !== growth.npv, `plan unchanged: ${JSON.stringify([growth.upfront, balanced.upfront])}`).toBe(true)

  await pickRisk('Cautious', 0.4)                      // sent and applied; may equal Balanced when the effect has saturated
  await pickRisk('Growth', 0)
  const back = await planNumbers()
  expect(back.upfront).toBe(growth.upfront)            // back to the first position: the first plan again
  expect(back.npv).toBe(growth.npv)
})

test('strict mode: without a backend no page shows prototype data', async ({ page }) => {
  await page.route(`${API}/**`, (r) => r.abort())
  await page.addInitScript(() => sessionStorage.clear())
  for (const route of ROUTES) {
    await page.goto(route)
    await expect(page.locator('body')).not.toBeEmpty()
    if (!['/demo-document-notice'].includes(route)) await expect(page.getByTestId('no-data')).toBeVisible()
    expect(inventedIn(await page.locator('body').innerText()), route).toEqual([])
  }
  await shot(page, '14-no-backend')
})

test('strict mode: with a real run no page shows prototype data or prototype images', async ({ page }) => {
  const { run_id } = await (await fetch(`${API}/run`, { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ city: 'Houston', target_pct: 20, risk_lambda: 0.2 }) })).json()
  let st = null
  for (let i = 0; i < 60 && !st?.layout; i++) { await new Promise((r) => setTimeout(r, 500)); st = await (await fetch(`${API}/state/${run_id}`)).json().catch(() => null) }
  expect(st?.layout).toBeTruthy()
  await page.addInitScript((id) => sessionStorage.setItem('hawklens.runId', id), run_id)
  for (const route of ROUTES) {
    await page.goto(route)
    await expect(page.getByTestId('no-data')).toHaveCount(0, { timeout: 20_000 })
    await page.waitForLoadState('networkidle')
    expect(inventedIn(await page.locator('body').innerText()), route).toEqual([])
    for (const src of await page.locator('img').evaluateAll((els) => els.map((e) => e.getAttribute('src') || ''))) {
      expect(src, route).not.toMatch(/evidence-(roof|facade|interior)|portfolio-3d|building-model/)
    }
  }
})
