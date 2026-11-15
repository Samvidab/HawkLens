// @vitest-environment jsdom
// Emissions in 3D: tags only at positions the backend gives, colours by share, legend always, legend-only on any failure.
// The emission numbers below are synthetic test data (no real building data is committed).
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import detail from '../test/fixtures/building_detail.json'
import { emissionSources, modelIdOf, tagDescriptors } from '../lib/emissions'
import EmissionsTour from './EmissionsTour'
import { AppRoutes } from '../App'
import { RunProvider } from '../lib/store'

const sdk = vi.hoisted(() => ({ setupSdk: vi.fn(), tagAdd: vi.fn() }))
vi.mock('@matterport/sdk', () => ({ setupSdk: sdk.setupSdk }))

const SOURCES = [
  { source: 'Plug loads', share_pct: 18, citation: 'CBECS 2018', evidence: ['Desks with monitors in panorama 2'], positions: [] },
  { source: 'Lighting', share_pct: 31.4, citation: 'CBECS 2018', evidence: ['Fluorescent fixtures in panorama 4'], positions: [{ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6 }] },
  { source: 'Cooling', share_pct: 27, evidence: [], positions: [{ x: 7, y: 8, z: 9 }, { x: 'bad' }] },
  { source: 'Heating', share_pct: 5, citation: 'x', evidence: [], positions: [{ x: 0, y: 0, z: 0 }] },
]
const TOUR = 'https://my.matterport.com/show/?m=AbC123xyz&play=1'
const layoutWith = ({ sources = SOURCES, tour = TOUR } = {}) => ({
  ...detail,
  widgets: [
    ...detail.widgets.filter((w) => w.type !== 'hero_3d'),
    ...(tour ? [{ id: 'h', type: 'hero_3d', title: '', why: '', size: 'wide', data_ref: '', props: { mode: 'showcase', showcase_url: tour, pins: [] } }] : []),
    ...(sources ? [{ id: 'e', type: 'emissions_3d', title: '', why: '', size: 'wide', data_ref: '', props: { building_id: 'b1', sources } }] : []),
  ],
})

beforeEach(() => {
  sdk.setupSdk.mockReset(); sdk.tagAdd.mockReset()
  sdk.tagAdd.mockImplementation(async (...d) => d.map((_, i) => `t${i}`))
  sdk.setupSdk.mockImplementation(async () => ({ Tag: { add: sdk.tagAdd } }))
  vi.stubEnv('VITE_MATTERPORT_SDK_KEY', 'test-key')
  vi.stubEnv('VITE_EMISSIONS_3D', '1')
  sessionStorage.clear()
})
afterEach(() => { cleanup(); vi.unstubAllEnvs() })

describe('emission sources from the layout', () => {
  it('top 3 by share, red/orange/yellow, labelled as estimates with the citation', () => {
    const s = emissionSources(layoutWith())
    expect(s.map((x) => x.source)).toEqual(['Lighting', 'Cooling', 'Plug loads'])
    expect(s.map((x) => x.color.name)).toEqual(['red', 'orange', 'yellow'])
    expect(s[0].label).toBe('Lighting: 31.4% of building CO₂ (estimated, CBECS 2018)')
    expect(s[1].label).toBe('Cooling: 27% of building CO₂ (estimated, citation not available)')
    expect(s[0].description).toContain('Fluorescent fixtures in panorama 4')
    expect(s[0].description).toContain('building-wide estimate, shown where observed')
    expect(s[1].description).toContain('Evidence not available')
  })

  it('no emissions widget -> null (the legend says not available)', () => {
    expect(emissionSources(layoutWith({ sources: null }))).toBeNull()
  })

  it('tags only at the positions given; a bad position is dropped, never guessed', () => {
    const d = tagDescriptors(emissionSources(layoutWith()))
    expect(d.map((x) => x.anchorPosition)).toEqual([{ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6 }, { x: 7, y: 8, z: 9 }])
    expect(d[0].color).toEqual({ r: 0.85, g: 0.23, b: 0.17 })
  })

  it('model id from the showcase url', () => {
    expect(modelIdOf(TOUR)).toBe('AbC123xyz')
    expect(modelIdOf('not a url')).toBeNull()
  })
})

describe('EmissionsTour', () => {
  const status = () => screen.getByTestId('emissions-3d').getAttribute('data-status')

  it('tour + key: the SDK opens the space and adds one tag per observed position', async () => {
    render(<EmissionsTour layout={layoutWith()} />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(sdk.setupSdk).toHaveBeenCalledWith('test-key', expect.objectContaining({ space: 'AbC123xyz' }))
    expect(sdk.tagAdd.mock.calls[0]).toHaveLength(3)
    expect(screen.getByTestId('emissions-3d').getAttribute('data-tags')).toBe('3')
    expect(screen.getByTestId('emissions-legend').textContent).toContain('3 tags placed')
    expect([...document.querySelectorAll('[data-source]')].map((e) => e.getAttribute('data-source'))).toEqual(['Lighting', 'Cooling', 'Plug loads'])
  })

  it('SDK fails -> legend only, the tour is removed', async () => {
    sdk.setupSdk.mockRejectedValueOnce(new Error('bad key'))
    render(<EmissionsTour layout={layoutWith()} />)
    await waitFor(() => expect(status()).toBe('failed'))
    expect(screen.getByTestId('emissions-tour').className).toContain('hidden')
    expect(screen.getByTestId('emissions-tour').childElementCount).toBe(0)
    expect(screen.getByTestId('emissions-legend').textContent).toContain('could not be loaded')
    expect(document.querySelectorAll('[data-source]')).toHaveLength(3)
  })

  it('no tour -> legend only, the SDK is never called', async () => {
    render(<EmissionsTour layout={layoutWith({ tour: null })} />)
    expect(status()).toBe('no-tour')
    expect(sdk.setupSdk).not.toHaveBeenCalled()
    expect(screen.getByTestId('emissions-legend').textContent).toContain('No 3D tour')
  })

  it('no key -> legend only', async () => {
    vi.stubEnv('VITE_MATTERPORT_SDK_KEY', '')
    render(<EmissionsTour layout={layoutWith()} />)
    expect(status()).toBe('no-key')
    expect(sdk.setupSdk).not.toHaveBeenCalled()
  })

  it('tour but no emissions data -> tour without tags, legend says not available', async () => {
    render(<EmissionsTour layout={layoutWith({ sources: null })} />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(sdk.tagAdd).not.toHaveBeenCalled()
    expect(screen.getByTestId('emissions-na')).toBeTruthy()
  })
})

describe('building page behind VITE_EMISSIONS_3D', () => {
  const mount = (layout) => {
    sessionStorage.setItem('hawklens.runId', 'r')
    const api = { getPortfolio: vi.fn(async () => ({ city: 'Houston', buildings: [] })), getHealth: vi.fn(async () => ({ engine_mode: 'live', nessie_mode: 'live' })),
      getState: vi.fn(async () => ({ status: 'ready', layout })), compose: vi.fn(async () => layout), openEvents: vi.fn((i, h) => { h.onEnd?.(); return () => {} }) }
    render(<MemoryRouter initialEntries={['/building']}><RunProvider api={api}><AppRoutes /></RunProvider></MemoryRouter>)
  }

  it('on: the emissions tour and legend replace the picture', async () => {
    mount(layoutWith())
    await waitFor(() => expect(screen.getByTestId('emissions-legend')).toBeTruthy())
  })

  it('off: the page is unchanged (no legend)', async () => {
    vi.stubEnv('VITE_EMISSIONS_3D', '')
    mount(layoutWith())
    await waitFor(() => expect(document.body.textContent).toContain('About this building'))
    expect(screen.queryByTestId('emissions-legend')).toBeNull()
  })
})
