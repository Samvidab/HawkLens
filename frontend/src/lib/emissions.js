// Emissions in 3D: the top-3 CO2 sources of a building, from the run's layout only.
//
// Data (Lane A, backend/app/agents/emissions_3d.py -> emissions_breakdown.json), passed through by the resolver as
// building_header.props.emissions_3d (null when EMISSIONS_3D is off or the breakdown is not built):
//   { label: "building-wide estimate, shown where observed",
//     top: [{ end_use, category,
//             pct_of_building: { value: 25.0 | "unknown", estimate: true, basis },
//             citation: { citation, url, scope, basis },
//             evidence: [{ claim_id, value, status, evidence_note? }] | "unknown",
//             positions: [{ xyz: [x, y, z], label, claim_id, kind, note }] | "unknown" }] }
// and building_header.props.tour (tour.json: { available, showcase_url, visibility, basis }).
// Nothing here is computed: a source without positions gets no tag, anything missing reads "unknown"/"not available".

import { widget } from './viewModels'

/** VITE_EMISSIONS_3D=1 turns the feature on (read at call time so tests can stub it). */
export const emissions3dOn = () => ['1', 'true', 'on'].includes(String(import.meta.env.VITE_EMISSIONS_3D || '').toLowerCase())
/** The Showcase SDK key from frontend/.env.local (VITE_MATTERPORT_SDK_KEY); never committed. */
export const sdkKey = () => import.meta.env.VITE_MATTERPORT_SDK_KEY || ''
export const BASIS_NOTE = 'building-wide estimate, shown where observed'

// largest share first: red, orange, yellow (CSS for the legend, 0-1 RGB for the SDK)
export const SHARE_COLORS = [
  { name: 'red', css: '#d93a2b', rgb: { r: 0.85, g: 0.23, b: 0.17 } },
  { name: 'orange', css: '#f08a24', rgb: { r: 0.94, g: 0.54, b: 0.14 } },
  { name: 'yellow', css: '#f2c230', rgb: { r: 0.95, g: 0.76, b: 0.19 } },
]

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const pctOf = (r) => (isNum(r?.pct_of_building?.value) ? r.pct_of_building.value : null)
const pctText = (v) => (isNum(v) ? `${Math.round(v * 10) / 10}%` : 'unknown %')

const evidenceLine = (e) => [
  `${String(e.claim_id || 'claim').split('.').slice(1).join('.') || e.claim_id || 'finding'}: ${e.value ?? 'unknown'}`,
  e.status ? `(${e.status})` : '',
  e.evidence_note ? `— ${e.evidence_note}` : '',
].filter(Boolean).join(' ')

const positionsOf = (r) => (Array.isArray(r?.positions) ? r.positions : [])
  .filter((p) => Array.isArray(p?.xyz) && p.xyz.length === 3 && p.xyz.every(isNum))
  .map((p) => ({ x: p.xyz[0], y: p.xyz[1], z: p.xyz[2], label: p.label || null, note: p.note || null }))

/** The breakdown as the backend wrote it (or null). */
export const breakdownOf = (layout) => widget(layout, 'building_header')?.emissions_3d ?? null

/** The top-3 sources as given by the backend, sorted by share; null when the layout has no breakdown. */
export function emissionSources(layout) {
  const e = breakdownOf(layout)
  if (!e || !Array.isArray(e.top) || !e.top.length) return null
  const basis = e.label || BASIS_NOTE
  return [...e.top]
    .filter((r) => r && r.end_use)
    .sort((a, b) => (pctOf(b) ?? -1) - (pctOf(a) ?? -1))
    .slice(0, 3)
    .map((r, i) => {
      const citation = r.citation?.citation || 'citation not available'
      const evidence = Array.isArray(r.evidence) ? r.evidence.map(evidenceLine) : ['Evidence: unknown']
      const positions = positionsOf(r)
      const where = positions.find((p) => p.note)?.note
      return {
        source: r.end_use,
        share: pctOf(r),
        color: SHARE_COLORS[i],
        label: `${r.end_use}: ${pctText(pctOf(r))} of building CO₂ (estimated, ${citation})`,
        description: [...evidence, where ? `Tag position: ${where}` : '', basis].filter(Boolean).join('\n\n'),
        positions,
      }
    })
}

/** The tour link: the hero_3d showcase, else the profile's, else tour.json's when Matterport reports it viewable. */
export function tourUrlOf(layout) {
  const hero = widget(layout, 'hero_3d')
  const header = widget(layout, 'building_header')
  return (hero?.mode === 'showcase' && hero.showcase_url) || header?.profile?.showcase_url
    || (header?.tour?.available && header.tour.showcase_url) || null
}

/** Showcase model id from a showcase_url (".../show/?m=ID..."), else null. */
export function modelIdOf(url) {
  try { return new URL(url).searchParams.get('m') || null } catch { return null }
}

/** One Tag.add descriptor per observed position (never a position that was not given). */
export function tagDescriptors(sources) {
  return (sources || []).flatMap((s) => s.positions.map((p) => ({
    label: s.label, description: s.description, color: s.color.rgb,
    anchorPosition: { x: p.x, y: p.y, z: p.z }, stemVector: { x: 0, y: 0.3, z: 0 },
  })))
}
