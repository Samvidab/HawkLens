// Verified CO2-emitting equipment in the 3D tour (VITE_EMISSIONS_3D). Data: the backend's GET /co2_equipment/{building_id}
// (backend/app/widgets/co2_equipment.py): only lighting fixtures and air diffusers that the agents saw and the verifier
// confirmed, each with its claim, the verifier's result, the panorama it was seen in and the recorded image marks.
// No shares, tonnes or plan links.
//
// Placement (from the Codex 3D work, docs/agent/FIXTURE-PLACEMENT.md on codex-3d-work): no 3D fixture position is
// recorded, so a marker is an observation marker, "Photo taken here", on the tour's own sweep for the panorama the
// evidence was taken from (matched by id; no coordinate is converted or guessed). An item whose panorama is not in the
// tour gets no marker. The recorded object outline (2D, on the evidence image) is shown by InspectionEvidence.
//
// Buildings are matched by Matterport model id: a tour gets markers only when its model id is the scan our agents surveyed
// (data.model_id) and that scan has verified items. Anything else: nothing, never invented.

/** The Showcase SDK key from frontend/.env.local (VITE_MATTERPORT_SDK_KEY); never committed. */
export const sdkKey = () => import.meta.env.VITE_MATTERPORT_SDK_KEY || ''

export const NO_SOURCES = 'No verified CO₂ sources located in this scan'
export const OBSERVATION = 'Photo taken here'
export const KIND = {
  lighting: { name: 'Lighting', css: '#e0a800', rgb: { r: 0.88, g: 0.66, b: 0 } },
  hvac: { name: 'Ventilation / HVAC', css: '#2f7fd1', rgb: { r: 0.18, g: 0.5, b: 0.82 } },
}

/** Showcase model id from a showcase_url (".../show/?m=ID..."), else null. */
export function modelIdOf(url) {
  try { return new URL(url).searchParams.get('m') || null } catch { return null }
}

export const tagLabel = (item) => `${item.equipment} seen (verified): CO₂ source`

/** What a click on the tag shows: the claim, the verifier's result and the panorama (a link to the survey image). */
export function tagDescription(item, apiBase) {
  const c = item.claim || {}
  const v = item.verifier || {}
  const conf = typeof c.confidence === 'number' ? ` (confidence ${c.confidence})` : ''
  return [
    `Claim: ${c.field || 'unknown'} = ${c.value ?? 'unknown'}${conf}`,
    `Verifier: ${v.status || 'unknown'}${v.note ? ` — ${v.note}` : ''}`,
    item.image_url ? `[Panorama where it was seen](${apiBase}${item.image_url})` : 'Panorama: not available',
  ].join('\n\n')
}

/** The tour's sweep for a panorama id (SDK sweeps expose id / sid / uuid), else null. */
export function sweepFor(sweeps, panoId) {
  if (!panoId) return null
  return sweeps.find((s) => s && (s.id === panoId || s.sid === panoId || s.uuid === panoId)) || null
}

/** Tag.add descriptors for the items whose panorama is a sweep of the tour. Returns { descriptors, placed: Set(index),
 *  targets: [{ index, sweepId, rotation }] } with targets[k] belonging to descriptors[k] (so Tag.add's ids map back). */
export function tagPlan(items, sweeps, apiBase) {
  const descriptors = []
  const placed = new Set()
  const targets = []
  items.forEach((it, i) => {
    const s = sweepFor(sweeps, it.pano_id)
    const k = KIND[it.kind]
    if (!s?.position || !k) return
    placed.add(i)
    // An observation marker: never promote a scan position to a fixture anchor, no guessed height, no decorative stem.
    // Face 0 is the recorder's ceiling face, so ceiling evidence selects the ceiling view; it does not locate a fixture
    // within that face. Horizon-face yaw cannot be inferred from a face number, so other evidence gets a level view.
    // The SDK leaves the pitch unchanged for +90 (measured: the camera stayed at -19), so the ceiling view uses +80.
    const ceiling = it.image_marks?.some((m) => m.image_id === it.image_id && m.image_id.endsWith('_0'))
    targets.push({ index: i, sweepId: s.id || s.sid || s.uuid, rotation: { x: ceiling ? 80 : 0, y: s.rotation?.y ?? 0 } })
    descriptors.push({
      label: OBSERVATION,
      description: `${OBSERVATION}. Fixture position has not been established.\n\n${tagLabel(it)}\n\n${tagDescription(it, apiBase)}`,
      color: k.rgb, anchorPosition: { ...(s.puckPosition || s.position) }, stemVector: { x: 0, y: 0, z: 0 },
    })
  })
  return { descriptors, placed, targets }
}

/** model id -> co2 data, from /co2_equipment responses: only scans with verified items and an id. Pure. */
export function modelMap(responses) {
  const map = new Map()
  for (const d of responses) {
    if (d && d.model_id && Array.isArray(d.items) && d.items.length) map.set(d.model_id, d)
  }
  return map
}
