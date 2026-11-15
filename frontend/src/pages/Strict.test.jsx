// @vitest-environment jsdom
// Strict demo mode: nothing shown to the user may be invented. Every route is rendered with no run and with each
// sample layout from the backend; none may show the prototype's sample content, and stub/estimate values are labelled.
import { cleanup, render, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import overview from '../test/fixtures/portfolio_overview.json'
import gap from '../test/fixtures/target_gap.json'
import detail from '../test/fixtures/building_detail.json'
import noMatterport from '../test/fixtures/building_detail_no_matterport.json'
import showcase from '../test/fixtures/building_detail_showcase.json'
import approved from '../test/fixtures/approved.json'
import { AppRoutes } from '../App'
import { RunProvider } from '../lib/store'
import { ToastProvider } from '../lib/ui'
import { PROTOTYPE_IMAGES, ROUTES, inventedIn } from '../test/forbidden'

const PORTFOLIO = { city: 'Houston', buildings: [
  { building_id: 'b1', name: 'Real Tower', hero: true, coverage: { vexcel: 'overhead' }, matterport_model_id: 'm1' },
  { building_id: 'b2', name: 'Second Plaza', coverage: {} },
] }

function mount(route, { layout = null, health = { engine_mode: 'live', nessie_mode: 'live' }, portfolio = PORTFOLIO } = {}) {
  if (layout) sessionStorage.setItem('hawklens.runId', 'run_1')
  const api = {
    getPortfolio: vi.fn(async () => portfolio), getHealth: vi.fn(async () => health),
    getState: vi.fn(async () => ({ status: 'ready', layout, plan_id: 'p1', results: {} })), compose: vi.fn(async () => layout),
    openEvents: vi.fn((id, h) => { h.onEnd?.(); return () => {} }), startRun: vi.fn(),
    getAssumptions: vi.fn(async () => ({ city: 'Houston', global: { discount_rate: 0.075, n_scenarios: 10000, source: 'x' }, city_values: { grid_kg_co2_per_kwh: 0.334 } })),
  }
  render(<MemoryRouter initialEntries={[route]}><RunProvider api={api}><ToastProvider><AppRoutes /></ToastProvider></RunProvider></MemoryRouter>)
  return api
}

const text = () => document.body.textContent
function expectNothingInvented() {
  const body = text()
  expect(inventedIn(body), "prototype strings on the page").toEqual([])
  for (const img of document.querySelectorAll('img')) expect(img.getAttribute('src') || '').not.toMatch(PROTOTYPE_IMAGES)
}

beforeEach(() => sessionStorage.clear())
afterEach(cleanup)

describe('strict mode: without a run no page shows prototype content', () => {
  for (const route of ROUTES) {
    it(route, async () => {
      mount(route)
      await waitFor(() => expect(text().length).toBeGreaterThan(0))
      if (!['/demo-document-notice', '/start-survey'].includes(route)) {
        expect(document.querySelector('[data-testid="no-data"]'), 'shows the no-data state').not.toBeNull()
      }
      expectNothingInvented()
    })
  }

  it('start-survey without a portfolio says so instead of listing sample buildings', async () => {
    mount('/start-survey', { portfolio: { buildings: [] } })
    await waitFor(() => expect(text()).toContain('Portfolio not available'))
    expectNothingInvented()
  })
})

describe('strict mode: with each sample layout every page shows only data from it', () => {
  const layouts = { overview, gap, detail, noMatterport, showcase, approved }
  for (const [name, layout] of Object.entries(layouts)) {
    for (const route of ROUTES) {
      it(`${name} ${route}`, async () => {
        mount(route, { layout })
        await waitFor(() => expect(document.querySelector('[data-testid="no-data"]')).toBeNull())
        expectNothingInvented()
      })
    }
  }
})

describe('strict mode: stub and estimate values are labelled', () => {
  it('stub engine: the portfolio numbers carry STUB badges and the footer names the stub', async () => {
    mount('/', { layout: overview, health: { engine_mode: 'stub', nessie_mode: 'stub' } })
    await waitFor(() => expect(document.querySelectorAll('[data-stub]').length).toBeGreaterThan(2))
    expect(document.querySelector('[data-testid="sources"]').textContent).toContain('stub engine')
  })

  it('live engine: no STUB badge where nothing is stubbed', async () => {
    const live = { ...overview, widgets: overview.widgets.map((w) => (w.type === 'plan_table' ? { ...w, props: { ...w.props, sample_pricing: false } } : w)) }
    mount('/', { layout: live })
    await waitFor(() => expect(text()).toContain('quant engine'))
    expect(document.querySelectorAll('[data-stub]').length).toBe(0)
  })

  it('the building baseline is labelled an estimate', async () => {
    mount('/building', { layout: detail })
    await waitFor(() => expect(text()).toContain('Annual emissions'))
    expect(document.querySelectorAll('[data-estimate]').length).toBeGreaterThan(0)
  })

  it('stub Nessie: the funding screens say simulated and show STUB', async () => {
    mount('/funding-confirmation', { layout: approved, health: { engine_mode: 'live', nessie_mode: 'stub' } })
    await waitFor(() => expect(text()).toContain('Simulated'))
    expect(document.querySelectorAll('[data-stub]').length).toBeGreaterThan(0)
  })

  it('the memo page renders the backend memo, not a summary card', async () => {
    mount('/investment-memo', { layout: approved })
    await waitFor(() => expect(document.querySelector('[data-testid="memo"]')).not.toBeNull())
    const md = approved.widgets.find((w) => w.type === 'memo').props.markdown
    const firstHeading = md.split('\n').find((l) => l.startsWith('# ')).slice(2)
    await waitFor(() => expect(text()).toContain(firstHeading))
  })
})
