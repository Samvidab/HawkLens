// @vitest-environment jsdom
// Verified CO2 highlighting in the tour modal (adapted from codex-3d-work's Co2Tour.test.jsx to main's ShowcaseModal):
// observation markers only on the tour's own sweep for each verified item's panorama, the evidence face as the view,
// selection from the list or the marker, and the plain iframe whenever there is nothing verified to show.
// The items below are synthetic test data.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { modelIdOf, modelMap, sweepFor, tagDescription, tagLabel, tagPlan } from '../lib/co2Tags'
import Co2Highlight, { Co2Tour } from './Co2Tour'
import ShowcaseModal from './ShowcaseModal'

const m = vi.hoisted(() => ({ setupSdk: vi.fn(), tagAdd: vi.fn(), moveTo: vi.fn(), dock: vi.fn(), open: vi.fn(), setRotation: vi.fn(), tagState: null, models: new Map() }))
vi.mock('@matterport/sdk', () => ({ setupSdk: m.setupSdk }))
vi.mock('../lib/co2Api', async (orig) => ({ ...(await orig()), loadCo2Models: () => Promise.resolve(m.models) }))

const item = (kind, equipment, pano, face = 0, extra = {}) => ({
  kind, equipment, pano_id: pano, image_id: pano ? `mpp_M_${pano}_${face}` : null, image_url: pano ? `/media/mpp_M_${pano}_${face}` : null,
  claim: { claim_id: `b1.interior.${kind === 'hvac' ? 'hvac' : 'lighting'}`, field: `interior.${kind === 'hvac' ? 'hvac' : 'lighting'}`,
    value: kind === 'hvac' ? 'vav_diffuser' : 'fluorescent', confidence: 0.9, evidence_ids: pano ? [`mpp_M_${pano}_${face}`] : [] },
  verifier: { status: 'verified', note: 'clearly visible' },
  image_marks: pano ? [{ image_id: `mpp_M_${pano}_${face}`, label: equipment, bbox: [0.2, 0.1, 0.6, 0.5] }] : [], ...extra,
})
const DATA = {
  building_id: 'b1', model_id: 'M', tour_model_id: 'M', tour_url: 'https://my.matterport.com/show/?m=M', tags_in_tour: true,
  items: [item('lighting', 'fluorescent troffer', 'pA', 0), item('hvac', 'ceiling supply diffuser', 'pB', 2), item('lighting', 'troffer', 'pZ'), item('lighting', 'x', null)],
}
const SWEEPS = {
  s1: { id: 'pA', position: { x: 1, y: 1.5, z: -2 }, puckPosition: { x: 1, y: 0, z: -2 }, rotation: { x: 0, y: 40 } },
  s2: { sid: 'pB', position: { x: 3, y: 1.5, z: 0 }, rotation: { x: 0, y: 10 } },
}
const PLAIN = <iframe title="plain tour" src="https://my.matterport.com/show/?m=M&play=1" />

beforeEach(() => {
  for (const f of [m.setupSdk, m.tagAdd, m.moveTo, m.dock, m.open, m.setRotation]) f.mockReset()
  m.models = new Map([['M', DATA]])
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
  vi.stubEnv('VITE_MATTERPORT_SDK_KEY', 'test-key')
  vi.stubEnv('VITE_EMISSIONS_3D', '1')
  vi.stubEnv('VITE_API_URL', 'http://api')
})
afterEach(() => { cleanup(); vi.unstubAllEnvs() })

const status = () => screen.getByTestId('co2-tour').getAttribute('data-status')
const tour = () => screen.getByTestId('co2-tour')

describe('marker text and placement', () => {
  it('label and click text: the claim, the verifier result and the panorama', () => {
    const d = tagDescription(DATA.items[1], 'http://api')
    expect(tagLabel(DATA.items[1])).toBe('ceiling supply diffuser seen (verified): CO₂ source')
    expect(d).toContain('Claim: interior.hvac = vav_diffuser (confidence 0.9)')
    expect(d).toContain('Verifier: verified — clearly visible')
    expect(d).toContain('[Panorama where it was seen](http://api/media/mpp_M_pB_2)')
    expect(tagDescription(DATA.items[3], 'http://api')).toContain('Panorama: not available')
  })

  it('an observation marker on the sweep of the same panorama, never on a guessed fixture position', () => {
    const { descriptors, placed, targets } = tagPlan(DATA.items, Object.values(SWEEPS), 'http://api')
    expect([...placed]).toEqual([0, 1]) // pZ is not a sweep of this tour, the last item has no panorama: no marker
    expect(descriptors.map((d) => d.label)).toEqual(['Photo taken here', 'Photo taken here'])
    expect(descriptors[0].description).toContain('Fixture position has not been established.')
    expect(descriptors[0].anchorPosition).toEqual({ x: 1, y: 0, z: -2 }) // the sweep's own puck
    expect(descriptors.every((d) => d.stemVector.x === 0 && d.stemVector.y === 0 && d.stemVector.z === 0)).toBe(true)
    // ceiling-face evidence (face 0) looks up; a horizon face keeps a level view at the sweep heading
    expect(targets).toEqual([{ index: 0, sweepId: 'pA', rotation: { x: 80, y: 40 } }, { index: 1, sweepId: 'pB', rotation: { x: 0, y: 10 } }])
  })

  it('image boxes and recorded xyz never become marker positions', () => {
    const moved = { ...DATA.items[0], xyz: [9, 9, 9], image_marks: [{ image_id: 'mpp_M_pA_0', bbox: [0.9, 0.9, 1, 1] }] }
    expect(tagPlan([moved], Object.values(SWEEPS), '').descriptors[0].anchorPosition).toEqual({ x: 1, y: 0, z: -2 })
  })

  it('matching by model id: only scans with verified items and an id', () => {
    expect([...modelMap([{ model_id: 'A', items: [{}] }, { model_id: 'B', items: [] }, { model_id: null, items: [{}] }, null]).keys()]).toEqual(['A'])
    expect(sweepFor(Object.values(SWEEPS), 'pB').sid).toBe('pB')
    expect(modelIdOf('https://my.matterport.com/show/?m=AbC&play=1')).toBe('AbC')
  })
})

describe('Co2Tour in the modal', () => {
  it('matched model: the SDK opens the scan and adds one observation marker per item located in it', async () => {
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(m.setupSdk).toHaveBeenCalledWith('test-key', expect.objectContaining({ space: 'M' }))
    expect(m.tagAdd.mock.calls[0]).toHaveLength(2)
    expect(tour().getAttribute('data-tags')).toBe('2')
    expect(screen.getByTestId('co2-panel').textContent).toContain('not located in the tour')
  })

  it('list click: flies to the observation sweep with the evidence-face rotation and opens the marker', async () => {
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('ready'))
    fireEvent.click(screen.getByTestId('co2-item-0'))
    await waitFor(() => expect(tour().getAttribute('data-focus-state')).toBe('open'), { timeout: 3000 })
    expect(m.moveTo).toHaveBeenCalledWith('pA', expect.objectContaining({ transition: 'transition.fly', rotation: { x: 80, y: 40 } }))
    expect(m.open).toHaveBeenCalledWith('t0', { force: true })
    expect(m.setRotation).toHaveBeenCalledWith({ x: 80, y: 40 })
    expect(screen.getByTestId('co2-item-2').disabled).toBe(true)
  })

  it('a marker selected in the tour jumps to its sweep too', async () => {
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('ready'))
    m.tagState({ selected: new Set(['t1']), docked: null })
    // the sweep id is the tour's own (the Sweep.data collection key), the one Sweep.moveTo takes
    await waitFor(() => expect(m.moveTo).toHaveBeenCalledWith('s2', expect.objectContaining({ rotation: { x: 0, y: 10 } })), { timeout: 3000 })
  })

  it('a different scan than the surveyed one gets no markers', async () => {
    render(<Co2Tour data={DATA} modelId="OTHER" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('ready'))
    expect(m.tagAdd).not.toHaveBeenCalled()
  })

  it('View evidence opens the recorded image with its recorded outline', async () => {
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('ready'))
    fireEvent.click(screen.getByTestId('co2-evidence-0'))
    expect(screen.getByTestId('evidence-image').getAttribute('src')).toBe('http://api/media/mpp_M_pA_0')
  })

  it('SDK fails -> the plain iframe and the list, read-only', async () => {
    m.setupSdk.mockImplementationOnce(() => Promise.reject(new Error('bad key')))
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('failed'))
    expect(screen.getByTitle('plain tour')).toBeTruthy()
    expect(screen.getByTestId('co2-tour-frame').childElementCount).toBe(0)
    expect(screen.getByTestId('co2-item-0').disabled).toBe(true)
  })

  it('no key -> the plain iframe, the SDK is never called', async () => {
    vi.stubEnv('VITE_MATTERPORT_SDK_KEY', '')
    render(<Co2Tour data={DATA} modelId="M" plain={PLAIN} />)
    await waitFor(() => expect(status()).toBe('no-key'))
    expect(m.setupSdk).not.toHaveBeenCalled()
    expect(screen.getByTitle('plain tour')).toBeTruthy()
  })
})

describe('ShowcaseModal', () => {
  const property = (id) => ({ id, name: `Building ${id}`, address: 'x', show_url: `https://my.matterport.com/show/?m=${id}` })

  it('a surveyed scan gets the highlighted tour', async () => {
    render(<ShowcaseModal property={property('M')} onClose={() => {}} />)
    await waitFor(() => expect(screen.getByTestId('co2-tour')).toBeTruthy())
  })

  it('any other model: the plain iframe, no list', async () => {
    render(<ShowcaseModal property={property('NOT_OURS')} onClose={() => {}} />)
    await waitFor(() => expect(screen.queryByTestId('co2-checking')).toBeNull())
    expect(screen.queryByTestId('co2-tour')).toBeNull()
    expect(screen.queryByTestId('co2-panel')).toBeNull()
    expect(screen.getByTitle('Matterport tour of Building NOT_OURS')).toBeTruthy()
  })

  it('feature off: the plain iframe, nothing fetched', () => {
    vi.stubEnv('VITE_EMISSIONS_3D', '')
    render(<ShowcaseModal property={property('M')} onClose={() => {}} />)
    expect(screen.queryByTestId('co2-tour')).toBeNull()
    expect(screen.getByTitle('Matterport tour of Building M')).toBeTruthy()
  })
})

describe('Co2Highlight', () => {
  it('renders its children unchanged when nothing matches', async () => {
    m.models = new Map()
    render(<Co2Highlight modelId="M">{PLAIN}</Co2Highlight>)
    await waitFor(() => expect(screen.getByTitle('plain tour')).toBeTruthy())
    expect(screen.queryByTestId('co2-panel')).toBeNull()
  })
})
