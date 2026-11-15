// Verified CO2-emitting equipment in the 3D tour (VITE_EMISSIONS_3D). Data: GET /co2_equipment/{building_id}
// (backend/app/widgets/co2_equipment.py): only lighting fixtures and air diffusers that the agents saw and the verifier
// confirmed, each with its claim, the verifier's result and the panorama it was seen in. No shares, tonnes or plan links.
// A tag is anchored on the tour's own sweep for that panorama (matched by id), so no coordinate is converted or guessed;
// an item whose panorama is not in the tour gets no tag.

/** VITE_EMISSIONS_3D=1 turns the feature on (read at call time so tests can stub it). */
export const emissions3dOn = () => ['1', 'true', 'on'].includes(String(import.meta.env.VITE_EMISSIONS_3D || '').toLowerCase())
/** The Showcase SDK key from frontend/.env.local (VITE_MATTERPORT_SDK_KEY); never committed. */
export const sdkKey = () => import.meta.env.VITE_MATTERPORT_SDK_KEY || ''

export const NO_SOURCES = 'No verified CO₂ sources located in this scan'
export const KIND = {
  lighting: { name: 'Lighting', css: '#e0a800', rgb: { r: 0.88, g: 0.66, b: 0 }, stem: 0.6 },
  hvac: { name: 'Ventilation / HVAC', css: '#2f7fd1', rgb: { r: 0.18, g: 0.5, b: 0.82 }, stem: 0.35 },
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

/** Tag.add descriptors for the items whose panorama is a sweep of the tour; returns { descriptors, placed: Set(index) }. */
export function tagPlan(items, sweeps, apiBase) {
  const descriptors = []
  const placed = new Set()
  items.forEach((it, i) => {
    const s = sweepFor(sweeps, it.pano_id)
    const k = KIND[it.kind]
    if (!s?.position || !k) return
    placed.add(i)
    descriptors.push({
      label: tagLabel(it), description: tagDescription(it, apiBase), color: k.rgb,
      anchorPosition: { ...s.position }, stemVector: { x: 0, y: k.stem, z: 0 },
    })
  })
  return { descriptors, placed }
}
