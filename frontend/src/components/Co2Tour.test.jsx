// @vitest-environment jsdom
// Verified CO2 equipment in the tour: tags only at the tour's own sweep for each verified item's panorama; label and
// click text as specified; no items -> the tour plus "No verified CO2 sources located in this scan"; SDK failure -> panel only.
// The items below are synthetic test data.
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import detail from '../test/fixtures/building_detail.json'
import { tagDescription, tagLabel, tagPlan } from '../lib/co2Tags'
import { AppRoutes } from '../App'
import { RunProvider } from '../lib/store'
import Co2Tour from './Co2Tour'

const m = vi.hoisted(() => ({ setupSdk: vi.fn(), tagAdd: vi.fn(), getCo2: vi.fn(), moveTo: vi.fn(), dock: vi.fn(), open: vi.fn(), tagState: null, setRotation: vi.fn() }))
vi.mock('@matterport/sdk', () => ({ setupSdk: m.setupSdk }))
vi.mock('../lib/api', async (orig) => ({ ...(await orig()), API_BASE: 'http://api', getCo2Equipment: m.getCo2 }))

const item = (kind, equipment, pano, extra = {}) => ({
  kind, equipment, pano_id: pano, image_id: pano ? `mpp_M_${pano}_0` : null, image_url: pano ? `/media/mpp_M_${pano}_0` : null,
  claim: { claim_id: `b1.interior.${kind === 'hvac' ? 'hvac' : 'lighting'}`, field: `interior.${kind === 'hvac' ? 'hvac' : 'lighting'}`, value: kind === 'hvac' ? 'vav_diffuser' : 'fluorescent', confidence: 0.9 },
  verifier: { status: 'verified', note: 'clearly visible' }, ...extra,
})
const DATA = {
  building_id: 'b1', model_id: 'M', tour_model_id: 'M', tour_url: 'https://my.matterport.com/show/?m=M', tags_in_tour: true,
  items: [item('lighting', 'fluorescent troffer', 'pA'), item('hvac', 'ceiling supply diffuser', 'pA'), item('lighting', 'troffer', 'pZ'), item('lighting', 'x', null)],
}
const SWEEPS = { s1: { id: 'pA', position: { x: 1, y: 1.5, z: -2 } }, s2: { sid: 'pB', position: { x: 3, y: 1.5, z: 0 } } }

beforeEach(() => {
  for (const f of [m.setupSdk, m.tagAdd, m.getCo2, m.moveTo, m.dock, m.open, m.setRotation]) f.mockReset()
  m.tagAdd.mockImplementation(async (...d) => d.map((_, i) => `t${i}`))
  m.moveTo.mockImplementation(async (id) => id)
  m.dock.mockResolvedValue(undefined)
  m.open.mockResolvedValue(undefined)
  m.setRotation.mockResolvedValue(undefined)
  const obs = () => ({ subscribe: () => ({ cancel() {} }) })
  m.setupSdk.mockImplementation(async () => ({
    Camera: { setRotation: m.setRotation },
    Tag: { add: m.tagAdd, dock: m.dock, open: m.open, openTags: { subscribe: (cb) => { m.tagState = cb; return { cancel() {} } } } },
    Sweep: { moveTo: m.moveTo, current: obs(), Transition: { FLY: 'transition.fly' },
      data: { subscribe: ({ onCollectionUpdated }) => { setTimeout(() => onCollectionUpdated(SWEEPS), 0); return { cancel() {} } } } },
  }))
  m.getCo2.mockResolvedValue(DATA)
  vi.stubEnv('VITE_MATTERPORT_SDK_KEY', 'test-key')
  vi.stubEnv('VITE_EMISSIONS_3D', '1')
  sessionStorage.clear()
})
afterEach(() => { cleanup(); vi.unstubAllEnvs() })

const status = () => screen.getByTestId('co2-tour').getAttribute('data-status')

describe('tag text and placement', () => {
  it('label and click text: the claim, the verifier result and the panorama', () => {
    const it0 = DATA.items[1]
    expect(tagLabel(it0)).toBe('ceiling supply diffuser seen (verified): CO₂ source')
    const d = tagDescription(it0, 'http://api')
    expect(d).toContain('Claim: interior.hvac = vav_diffuser (confidence 0.9)')
    expect(d).toContain('Verifier: verified — clearly visible')
    expect(d).toContain('[Panorama where it was seen](http://api/media/mpp_M_pA_0)')
    expect(tagDescription(DATA.items[3], 'http://api')).toContain('Panorama: not available')
  })

  it('anchored on the tour sweep of the same panorama; no sweep -> no tag', () => {
    const { descriptors, placed } = tagPlan(DATA.items, Object.values(SWEEPS), 'http://api')
    expect([...placed]).toEqual([0, 1])
    expect(descriptors.map((d) => d.anchorPosition)).toEqual([{ x: 1, y: 1.5, z: -2 }, { x: 1, y: 1.5, z: -2 }])
    expect(descriptors[1].label).toBe('Photo taken here')
    expect(descriptors[1].stemVector).toEqual({ x: 0, y: 0, z: 0 })
    expect(descriptors[1].description).toContain('Fixture position has not been established')
  })
})

describe('Co2Tour', () => {
  it('tour + verified items: the SDK opens the scan and adds one tag per item located in it', async () => {
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(m.setupSdk).toHaveBeenCalledWith('test-key', expect.objectContaining({ space: 'M' }))
    expect(m.tagAdd.mock.calls[0]).toHaveLength(2)
    expect(screen.getByTestId('co2-tour').getAttribute('data-tags')).toBe('2')
    const rows = screen.getAllByText(/seen \(verified\)/)
    expect(rows).toHaveLength(4)
    expect(screen.getByTestId('co2-panel').textContent).toContain('not located in the tour')
  })

  it('clicking an item moves the tour to its panorama and opens its tag; unplaced items are not clickable', async () => {
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    screen.getByTestId('co2-item-1').click()
    await waitFor(() => expect(screen.getByTestId('co2-tour').getAttribute('data-focus-state')).toBe('open'), { timeout: 3000 })
    expect(m.moveTo).toHaveBeenCalledWith('pA', expect.objectContaining({ transition: 'transition.fly', rotation: { x: 0, y: 0 } }))
    expect(m.open).toHaveBeenCalledWith('t1', { force: true })
    expect(m.setRotation).toHaveBeenCalledWith({ x: 0, y: 0 })
    expect(screen.getByTestId('co2-tour').getAttribute('data-focus-tag')).toBe('t1')
    expect(screen.getByTestId('co2-item-2').disabled).toBe(true) // its panorama is not in the tour: no tag, no move
  })

  it('tour tag selection jumps to its panorama without aiming down', async () => {
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    m.tagState({ selected: new Set(['t1']) })
    await waitFor(() => expect(m.moveTo).toHaveBeenCalledWith('pA', expect.objectContaining({ rotation: { x: 0, y: 0 } })))
    expect(m.open).toHaveBeenCalledWith('t1', { force: true })
  })

  it('image boxes and recorded xyz cannot establish a fixture anchor', () => {
    const plan = tagPlan([{ ...DATA.items[0], xyz: [99, 99, 99], image_marks: [{ image_id: DATA.items[0].image_id, bbox: [0, 0, 1, 1] }] }], Object.values(SWEEPS), '')
    expect(plan.descriptors[0].anchorPosition).toEqual(SWEEPS.s1.position)
    expect(plan.descriptors[0].label).toBe('Photo taken here')
    expect(plan.targets[0].rotation.x).toBe(90)
  })

  it('open unavailable -> the tag is docked instead', async () => {
    m.open.mockRejectedValueOnce(new Error('no open'))
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    screen.getByTestId('co2-item-0').click()
    await waitFor(() => expect(m.dock).toHaveBeenCalledWith('t0', { force: true }), { timeout: 3000 })
  })

  it('no verified items -> the tour plus the "no verified sources" line, no tags', async () => {
    m.getCo2.mockResolvedValue({ ...DATA, items: [] })
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(m.tagAdd).not.toHaveBeenCalled()
    expect(screen.getByTestId('co2-none').textContent).toBe('No verified CO₂ sources located in this scan')
  })

  it('a tour of a different scan is shown without tags', async () => {
    m.getCo2.mockResolvedValue({ ...DATA, tags_in_tour: false })
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(m.tagAdd).not.toHaveBeenCalled()
    expect(screen.getByTestId('co2-note').textContent).toContain('different scan')
  })

  it('SDK fails -> panel only, the tour is removed', async () => {
    m.setupSdk.mockRejectedValueOnce(new Error('bad key'))
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('failed'))
    expect(screen.getByTestId('co2-tour-frame').className).toContain('hidden')
    expect(screen.getByTestId('co2-tour-frame').childElementCount).toBe(0)
    expect(screen.getByTestId('co2-note').textContent).toContain('could not be loaded')
  })

  it('no tour -> panel only, the SDK is never called', async () => {
    m.getCo2.mockResolvedValue({ ...DATA, tour_url: null, tags_in_tour: false })
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('no-tour'))
    expect(m.setupSdk).not.toHaveBeenCalled()
  })

  it('no key -> panel only', async () => {
    vi.stubEnv('VITE_MATTERPORT_SDK_KEY', '')
    render(<Co2Tour buildingId="b1" />)
    await waitFor(() => expect(status()).toBe('no-key'))
    expect(m.setupSdk).not.toHaveBeenCalled()
  })
})

describe('building page behind VITE_EMISSIONS_3D', () => {
  const mount = () => {
    sessionStorage.setItem('hawklens.runId', 'r')
    const api = { getPortfolio: vi.fn(async () => ({ city: 'Houston', buildings: [] })), getHealth: vi.fn(async () => ({ engine_mode: 'live', nessie_mode: 'live' })),
      getState: vi.fn(async () => ({ status: 'ready', layout: detail })), compose: vi.fn(async () => detail), openEvents: vi.fn((i, h) => { h.onEnd?.(); return () => {} }) }
    render(<MemoryRouter initialEntries={['/building']}><RunProvider api={api}><AppRoutes /></RunProvider></MemoryRouter>)
  }
  it('on: the tour with verified CO2 tags', async () => {
    mount()
    await waitFor(() => expect(screen.getByTestId('co2-panel')).toBeTruthy())
  })
  it('off: unchanged', async () => {
    vi.stubEnv('VITE_EMISSIONS_3D', '')
    mount()
    await waitFor(() => expect(document.body.textContent).toContain('About this building'))
    expect(screen.queryByTestId('co2-panel')).toBeNull()
  })
})
