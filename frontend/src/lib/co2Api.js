// The backend's verified CO2 data (GET /portfolio, GET /co2_equipment/{building_id}) for the tour highlighting. Same backend
// and same base as lib/api.js: VITE_API_URL (frontend/.env locally, Vercel's environment in production), falling back to
// the local dev backend. VITE_EMISSIONS_3D off, or a backend without /co2_equipment -> the feature does nothing.
import { modelMap } from './co2Tags'

/** VITE_EMISSIONS_3D=true turns the highlighting on (read at call time). */
export const emissions3dOn = () => ['1', 'true', 'on'].includes(String(import.meta.env.VITE_EMISSIONS_3D || '').toLowerCase())
export const ourApiBase = () => String(import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

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
