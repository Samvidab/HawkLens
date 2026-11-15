// OUR backend (the agent/quant API with GET /co2_equipment), for the verified CO2 highlighting. Configured by
// VITE_API_URL only: the teammate's Matterport property API keeps using VITE_API_BASE (see lib/api.js), so the two
// backends can never be mixed up. Unset VITE_API_URL or VITE_EMISSIONS_3D off -> the feature does nothing.
import { modelMap } from './co2Tags'

/** VITE_EMISSIONS_3D=true turns the highlighting on (read at call time). */
export const emissions3dOn = () => ['1', 'true', 'on'].includes(String(import.meta.env.VITE_EMISSIONS_3D || '').toLowerCase())
export const ourApiBase = () => String(import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')

async function getJson(base, path) {
  const res = await fetch(`${base}${path}`)
  if (!res.ok) throw new Error(`${path} ${res.status}`)
  return res.json()
}

let cache = null // { base, promise }

/** Map of Matterport model id -> verified CO2 data, for the buildings in our portfolio that have verified items.
 *  Resolves to an empty map when the feature is off, our API is not configured, or it cannot be reached. */
export function loadCo2Models() {
  const base = ourApiBase()
  if (!emissions3dOn() || !base) return Promise.resolve(new Map())
  if (cache && cache.base === base) return cache.promise
  const promise = (async () => {
    try {
      const portfolio = await getJson(base, '/portfolio')
      const responses = await Promise.all((portfolio.buildings || []).map((b) =>
        getJson(base, `/co2_equipment/${encodeURIComponent(b.building_id)}`).catch(() => null)))
      return modelMap(responses)
    } catch {
      cache = null // try again next time (the backend may not be up yet)
      return new Map()
    }
  })()
  cache = { base, promise }
  return promise
}
