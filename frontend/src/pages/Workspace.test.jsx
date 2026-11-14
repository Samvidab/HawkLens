// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import overview from '../test/fixtures/portfolio_overview.json'
import gap from '../test/fixtures/target_gap.json'
import detail from '../test/fixtures/building_detail.json'
import showcase from '../test/fixtures/building_detail_showcase.json'
import approved from '../test/fixtures/approved.json'
import issue from '../test/fixtures/verification_issue.json'
import { RENDERERS } from '../components/widgets'
import { RunProvider } from '../lib/store'
import Workspace from './Workspace'

const REGISTRY_TYPES = ['target_control', 'portfolio_3d', 'hero_3d', 'abatement_curve', 'plan_table', 'risk_histogram', 'evidence_gallery',
  'facade_compass', 'floor_plan', 'upgrade_list', 'building_header', 'target_gap_card', 'financing_card', 'memo', 'activity_feed']

function show(layout, health = { engine_mode: 'live', nessie_mode: 'live' }) {
  sessionStorage.setItem('hawklens.runId', 'run_1')
  const api = {
    getPortfolio: vi.fn(async () => ({ buildings: [] })), getHealth: vi.fn(async () => health),
    getState: vi.fn(async () => ({ status: 'ready', layout, plan_id: 'p1' })), compose: vi.fn(async () => layout),
    openEvents: vi.fn(() => () => {}), startRun: vi.fn(),
  }
  render(<MemoryRouter><RunProvider api={api}><Workspace /></RunProvider></MemoryRouter>)
  return api
}
const cards = () => [...document.querySelectorAll('[data-widget]')]

beforeEach(() => sessionStorage.clear())
afterEach(cleanup)

describe('Workspace renders the composer layout', () => {
  it('has a renderer for every widget type in the backend registry', () => {
    expect(Object.keys(RENDERERS).sort()).toEqual([...REGISTRY_TYPES].sort())
  })

  for (const [name, layout] of Object.entries({ overview, gap, detail, showcase, approved, issue })) {
    it(`${name}: the composer's order, sizes and why lines, nothing else`, async () => {
      show(layout)
      await waitFor(() => expect(cards().length).toBe(layout.widgets.length))
      expect(cards().map((c) => c.dataset.widget)).toEqual(layout.widgets.map((w) => w.type))
      expect(cards().map((c) => c.dataset.size)).toEqual(layout.widgets.map((w) => w.size))
      const span = { full: 'col-span-12', wide: 'col-span-8', half: 'col-span-6', side: 'col-span-4' }
      cards().forEach((c, i) => {
        expect(c.className).toContain(span[layout.widgets[i].size])
        expect(within(c).getByText(layout.widgets[i].title)).toBeTruthy()
        expect(c.querySelector('[data-why]').textContent).toBe(layout.widgets[i].why)
      })
      expect(screen.queryByText(/is not supported by this page/)).toBeNull()
    })
  }

  it('reorders when the composer reorders (no fixed page structure)', async () => {
    const reversed = { ...overview, widgets: [...overview.widgets].reverse() }
    show(reversed)
    await waitFor(() => expect(cards().length).toBe(reversed.widgets.length))
    expect(cards().map((c) => c.dataset.widget)).toEqual(reversed.widgets.map((w) => w.type))
  })

  it('shows STUB badges on stub-engine numbers and "not available" for missing values', async () => {
    const l = JSON.parse(JSON.stringify(overview))
    l.widgets.find((w) => w.type === 'target_control').props.p_hit_target = null
    show(l, { engine_mode: 'stub', nessie_mode: 'stub' })
    await waitFor(() => expect(cards().length).toBe(l.widgets.length))
    expect(document.querySelectorAll('[data-stub]').length).toBeGreaterThan(3)
    const tc = document.querySelector('[data-widget="target_control"]')
    expect(within(tc).getByText('not available')).toBeTruthy()
  })

  it('shows the showcase tour for hero_3d in showcase mode and links the mesh in mesh mode', async () => {
    show(showcase)
    await waitFor(() => expect(document.querySelector('iframe[title="Matterport 3D tour"]')).toBeTruthy())
    expect(document.querySelector('iframe').getAttribute('src')).toMatch(/^https:\/\/my\.matterport\.com\//)
    cleanup(); sessionStorage.clear()
    show(detail)
    await waitFor(() => expect(screen.getByText('OBJ')).toBeTruthy())
  })

  it('renders the memo markdown (table included) without injecting HTML', async () => {
    const l = JSON.parse(JSON.stringify(approved))
    l.widgets.find((w) => w.type === 'memo').props.markdown += '\n\n<img src=x onerror="alert(1)">'
    show(l)
    await waitFor(() => expect(document.querySelector('[data-widget="memo"] table')).toBeTruthy())
    expect(document.querySelector('[data-widget="memo"] img')).toBeNull()
  })

  it('without a run it says so and offers to start one (no prototype content)', async () => {
    const api = { getPortfolio: vi.fn(async () => ({})), getHealth: vi.fn(async () => ({})), getState: vi.fn(), compose: vi.fn(), openEvents: vi.fn(), startRun: vi.fn() }
    render(<MemoryRouter><RunProvider api={api}><Workspace /></RunProvider></MemoryRouter>)
    expect(screen.getByText('No workspace yet.')).toBeTruthy()
    expect(cards()).toHaveLength(0)
  })
})
