import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { topAreas } from '../src/lib/co2Tags.js'

// Verified CO2 highlighting on the Portfolio tours, in light and dark mode (adapted from codex-3d-work's emissions.spec.js
// to main's homepage and ShowcaseModal). For every building card: a tour whose model id is a surveyed scan with verified
// items shows one observation marker per item located in it, the list beside it, list clicks fly to the observation sweep
// and open the marker (as reported by the tour itself), and the evidence close-up outlines sit exactly on the recorded
// box bounds. Every other tour is the plain iframe with no list. Read-only: nothing is written in the repo (screenshots go to the temp folder).
const API = (process.env.E2E_API || 'http://localhost:8000').replace(/\/+$/, '')
const SITE = process.env.E2E_SITE || 'http://localhost:3000'
const SHOTS = process.env.E2E_SHOTS || path.join(os.tmpdir(), 'hawklens-e2e-screens') // outside the repo

const getJson = async (path) => { const r = await fetch(API + path); if (!r.ok) throw new Error(`${path} ${r.status}`); return r.json() }
let ready = false
test.beforeAll(async () => {
  try { ready = (await fetch(SITE)).ok && (await fetch(`${API}/health`)).ok } catch { ready = false }
})

async function verifiedByModel() {
  const map = new Map()
  for (const b of (await getJson('/portfolio')).buildings) {
    const d = await fetch(`${API}/co2_equipment/${encodeURIComponent(b.building_id)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null)
    if (d?.model_id && d.items?.length) map.set(d.model_id, d)
  }
  return map
}

async function checkOutlines(page, item) {
  const image = page.getByTestId('evidence-image')
  await expect(image).toBeVisible()
  const matching = item.image_marks.filter((m) => m.image_id === item.image_id && m.bbox)
  await expect(page.getByTestId('evidence-mark')).toHaveCount(matching.length)
  await expect.poll(() => image.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true)
  const bounds = await image.boundingBox()
  const natural = await image.evaluate((el) => ({ w: el.naturalWidth, h: el.naturalHeight, blur: getComputedStyle(el).filter }))
  expect(natural.blur).toBe('none') // the recorded image, unfiltered
  expect(bounds.width).toBeLessThanOrEqual(natural.w + 0.5) // never upscaled when fitted
  for (const [j, mark] of matching.entries()) {
    const r = await page.getByTestId('evidence-mark').nth(j).locator('ellipse').first().evaluate((el) => {
      const b = el.getBBox(); const m = el.getScreenCTM()
      const a = new DOMPoint(b.x, b.y).matrixTransform(m); const z = new DOMPoint(b.x + b.width, b.y + b.height).matrixTransform(m)
      return { x: a.x, y: a.y, width: z.x - a.x, height: z.y - a.y }
    })
    // the ellipse's bounds are exactly the recorded box (within a pixel)
    expect(Math.abs(r.x - (bounds.x + mark.bbox[0] * bounds.width))).toBeLessThan(1)
    expect(Math.abs(r.y - (bounds.y + mark.bbox[1] * bounds.height))).toBeLessThan(1)
    expect(Math.abs(r.width - (mark.bbox[2] - mark.bbox[0]) * bounds.width)).toBeLessThan(1)
    expect(Math.abs(r.height - (mark.bbox[3] - mark.bbox[1]) * bounds.height)).toBeLessThan(1)
  }
}

for (const theme of ['light', 'dark']) {
  test(`every Portfolio tour, ${theme} mode: only the portfolio's buildings; top areas only from verified data`, async ({ page }) => {
    test.skip(!ready, `site ${SITE} or API ${API} not running`)
    fs.mkdirSync(SHOTS, { recursive: true })
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    const verified = await verifiedByModel()
    // the grid and the search show exactly the demo portfolio's buildings that have a Matterport tour (GET /portfolio)
    const properties = (await getJson('/portfolio')).buildings.filter((b) => b.matterport_model_id)
      .map((b) => ({ id: b.matterport_model_id, name: b.name }))
    await page.goto('/')
    const cards = page.locator('section div.grid > button')
    await expect(cards).toHaveCount(properties.length, { timeout: 30_000 })
    expect(await cards.locator('p.truncate.text-\\[13px\\]').allTextContents()).toEqual(properties.map((p) => p.name))
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+k' : 'Control+k')
    const found = page.locator('.command-item:has(.command-arrow:text-is("3D ↗")) strong')
    await expect(found).toHaveCount(properties.length, { timeout: 20_000 })
    expect((await found.allTextContents()).sort()).toEqual(properties.map((p) => p.name).sort())
    await page.keyboard.press('Escape')
    if (theme === 'dark') {
      await page.locator('.mission-toggle').click()
      await expect(page.locator('body')).toHaveClass(/mission-mode/)
    }
    await page.screenshot({ path: `${SHOTS}/home-${theme}.png` })

    const report = []
    for (const [i, p] of properties.entries()) {
      const data = verified.get(p.id)
      await cards.nth(i).click()
      await expect(page.locator('[data-testid="co2-checking"]')).toHaveCount(0, { timeout: 20_000 })
      const row = { card: p.name, model: p.id, matched: !!data, markers: 0, clicked: 0, outlines_checked: 0 }
      if (!data) {
        await expect(page.locator(`iframe[title^="Matterport tour of"]`)).toHaveCount(1)
        await expect(page.getByTestId('co2-panel')).toHaveCount(0)
      } else {
        const box = page.getByTestId('co2-tour')
        await expect(box).toHaveAttribute('data-status', /ready|failed|no-key/, { timeout: 90_000 })
        expect(await box.getAttribute('data-status')).toBe('ready')
        row.markers = Number(await box.getAttribute('data-tags'))
        // Top verified CO2 areas: as many as exist, at most 3, never padded; markers only for the shown areas' items
        const areas = topAreas(data.items)
        const shown = areas.flatMap((a) => a.indices)
        row.areas = areas.length
        await expect(page.getByTestId('co2-panel')).toContainText('Top verified CO₂ areas')
        await expect(page.locator('[data-co2-area]')).toHaveCount(areas.length)
        await expect(page.locator('[data-co2-item]')).toHaveCount(shown.length)
        expect(row.markers).toBeLessThanOrEqual(shown.length) // never a marker without a verified item in a shown area
        for (const [a, area] of areas.entries()) { // an area click goes to its first located source
          const btn = page.getByTestId(`co2-area-${a}`)
          if (await btn.isDisabled()) continue
          await btn.click()
          await expect(box).toHaveAttribute('data-focus-state', /open|failed/, { timeout: 40_000 })
          expect(area.indices).toContain(Number(await box.getAttribute('data-focus-index')))
          await expect(box).toHaveAttribute('data-current-sweep', await box.getAttribute('data-focus-sweep'), { timeout: 15_000 })
          row.areas_clicked = (row.areas_clicked || 0) + 1
        }
        for (const k of shown) {
          const btn = page.getByTestId(`co2-item-${k}`)
          if (await btn.isDisabled()) continue
          await btn.click()
          await expect(box).toHaveAttribute('data-focus-index', String(k))
          await expect(box).toHaveAttribute('data-focus-state', /open|failed/, { timeout: 40_000 })
          expect(await box.getAttribute('data-focus-state')).toBe('open')
          await expect(box).toHaveAttribute('data-current-sweep', await box.getAttribute('data-focus-sweep'), { timeout: 15_000 })
          await expect(box).toHaveAttribute('data-docked-tag', await box.getAttribute('data-focus-tag'), { timeout: 15_000 })
          // the camera ends at the evidence face's pitch (ceiling +80 / level 0), as the tour itself reports
          const wanted = Number((await box.getAttribute('data-focus-rotation')).split(',')[0])
          await expect.poll(async () => Number(((await box.getAttribute('data-camera-rotation')) || 'NaN').split(',')[0]), { timeout: 15_000 })
            .toBeCloseTo(wanted, 0)
          row.clicked++
          if (k === shown[0]) await page.waitForTimeout(2500), await page.screenshot({ path: `${SHOTS}/tour-${theme}-${p.id}.png` })
          // the recorded evidence with the recorded object outline
          await page.getByRole('button', { name: 'Inspection Close-Up', exact: true }).click()
          await expect(page.getByRole('dialog', { name: /Inspection Close-Up/ })).toBeVisible()
          await checkOutlines(page, data.items[k])
          row.outlines_checked++
          if (k === shown[0]) await page.screenshot({ path: `${SHOTS}/evidence-${theme}-${p.id}.png` })
          await page.getByRole('button', { name: 'Close evidence' }).click()
          await expect(page.getByRole('dialog', { name: /Inspection Close-Up/ })).toHaveCount(0)
        }
        expect(row.clicked).toBe(row.markers)
      }
      report.push(row)
      await page.locator('button:text-is("×")').click()
      await expect(page.locator('iframe, [data-testid="co2-tour"]')).toHaveCount(0)
    }
    fs.writeFileSync(`${SHOTS}/co2-report-${theme}.json`, JSON.stringify(report, null, 2))
    console.log(theme, JSON.stringify(report.filter((r) => r.matched)))
    expect(errors).toEqual([])
  })
}
