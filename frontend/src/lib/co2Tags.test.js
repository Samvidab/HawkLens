// Pure-logic tests for the verified CO2 highlighting (run: npm test). No dependencies: node:test.
// Synthetic data only.
import assert from 'node:assert/strict'
import test from 'node:test'
import { KIND, modelMap, modelIdOf, sweepFor, tagDescription, tagLabel, tagPlan } from './co2Tags.js'

const item = (kind, equipment, pano, extra = {}) => ({
  kind, equipment, pano_id: pano, image_url: pano ? `/media/mpp_M_${pano}_0` : null,
  claim: { field: 'interior.lighting', value: 'fluorescent', confidence: 0.9 }, verifier: { status: 'verified', note: 'clearly visible' }, ...extra,
})
const sweeps = [
  { id: 'pA', position: { x: 1, y: 1.5, z: -2 }, puckPosition: { x: 1, y: 0, z: -2 }, rotation: { y: 40 } },
  { id: 'pB', sid: 'pB', position: { x: 3, y: 1.5, z: 0 } },
]

test('matching by model id: only scans with verified items and an id', () => {
  const m = modelMap([{ model_id: 'A', items: [{}] }, { model_id: 'B', items: [] }, { model_id: null, items: [{}] }, null, { model_id: 'C' }])
  assert.deepEqual([...m.keys()], ['A'])
})

test('label and click text: claim, verifier result, panorama link; missing panorama says so', () => {
  const it = item('hvac', 'ceiling supply diffuser', 'pA')
  assert.equal(tagLabel(it), 'ceiling supply diffuser seen (verified): CO₂ source')
  const d = tagDescription(it, 'http://ours')
  assert.match(d, /Claim: interior\.lighting = fluorescent \(confidence 0\.9\)/)
  assert.match(d, /Verifier: verified — clearly visible/)
  assert.match(d, /\[Panorama where it was seen\]\(http:\/\/ours\/media\/mpp_M_pA_0\)/)
  assert.match(tagDescription(item('hvac', 'x', null), 'http://ours'), /Panorama: not available/)
})

test('a tag exists only for an item whose panorama is a sweep of the tour, on the floor under it', () => {
  const items = [item('lighting', 'troffer', 'pA'), item('hvac', 'diffuser', 'pZ'), item('lighting', 'x', null), item('other', 'y', 'pB')]
  const { descriptors, placed, targets } = tagPlan(items, sweeps, 'http://ours')
  assert.deepEqual([...placed], [0])
  assert.deepEqual(targets, [{ index: 0, sweepId: 'pA', heading: 40 }])
  assert.deepEqual(descriptors[0].anchorPosition, { x: 1, y: 0, z: -2 })
  assert.equal(descriptors[0].label, 'troffer seen (verified): CO₂ source')
  assert.deepEqual(descriptors[0].color, KIND.lighting.rgb)
})

test('sweepFor and modelIdOf', () => {
  assert.equal(sweepFor(sweeps, 'pB').id, 'pB')
  assert.equal(sweepFor(sweeps, null), null)
  assert.equal(modelIdOf('https://my.matterport.com/show/?m=AbC&play=1'), 'AbC')
  assert.equal(modelIdOf('nope'), null)
})
