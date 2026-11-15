// Emissions in 3D: the top-3 CO2 sources of a building, from the run's layout only.
//
// Proposed contract (Lane A owns the data; nothing here is computed or filled in by the frontend):
//   layout widget type "emissions_3d", props:
//   { building_id, sources: [{ source: "Lighting",            // what emits
//                              share_pct: 31.0,                 // % of the building's CO2 (an estimate)
//                              citation: "CBECS 2018 office end-use share",
//                              evidence: ["Fluorescent fixtures seen in panorama 4"],  // what the survey observed
//                              positions: [{ x, y, z }] }] }    // Showcase coordinates where it was observed
// A source without positions gets no tag (legend only). No widget -> legend says "not available".

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
const isPos = (p) => p && isNum(p.x) && isNum(p.y) && isNum(p.z)
const pctText = (v) => (isNum(v) ? `${Math.round(v * 10) / 10}%` : 'unknown %')

/** The top-3 sources as given by the backend, sorted by share; null when the layout has no emissions data. */
export function emissionSources(layout) {
  const w = widget(layout, 'emissions_3d')
  if (!w || !Array.isArray(w.sources) || !w.sources.length) return null
  return [...w.sources]
    .filter((s) => s && s.source)
    .sort((a, b) => (isNum(b.share_pct) ? b.share_pct : -1) - (isNum(a.share_pct) ? a.share_pct : -1))
    .slice(0, 3)
    .map((s, i) => {
      const citation = s.citation || 'citation not available'
      const evidence = (s.evidence || []).filter(Boolean)
      return {
        source: s.source,
        share: isNum(s.share_pct) ? s.share_pct : null,
        color: SHARE_COLORS[i],
        label: `${s.source}: ${pctText(s.share_pct)} of building CO₂ (estimated, ${citation})`,
        description: [...(evidence.length ? evidence : ['Evidence not available']), BASIS_NOTE].join('\n\n'),
        positions: (s.positions || []).filter(isPos),
      }
    })
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
