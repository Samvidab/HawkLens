// Client for the HawkLens backend.
// Base URL comes from VITE_API_URL (set in frontend/.env locally, and in Vercel's
// environment for production). Falls back to the local dev backend if unset.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body } = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    throw new ApiError(0, `Can't reach the backend at ${BASE} (${e.message})`)
  }
  if (!res.ok) {
    let detail = `${res.status}`
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

// ---- Matterport property data -------------------------------------------------------------
export async function fetchProperties({ q, limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return request(`/properties?${params.toString()}`)
}

export async function fetchProperty(id) {
  return request(`/properties/${id}`)
}

// ---- Portfolio, survey runs, plan -----------------------------------------------------------
/** data/portfolio.json: { city, buildings: [{ building_id, name, address, matterport_model_id, hero, ... }] } */
export const fetchPortfolio = () => request('/portfolio')

/** Start survey -> pricing -> compose in the background. Returns { run_id }. */
export const startRun = (goal) => request('/run', { method: 'POST', body: goal })

/** Survey status/results for a run: { status, results: { building_id: {status, upgrades, ...} }, plan_id, ... } */
export const fetchRunState = (runId) => request(`/state/${encodeURIComponent(runId)}`)

/** Owner action -> backend re-plan (set_target, set_budget, set_risk, goal, approve, ...). */
export const compose = (runId, type, payload = {}) =>
  request('/compose', { method: 'POST', body: { run_id: runId, type, payload } })

/** The one persisted plan every page shows, with approval verdict and funding mode. null before any plan. */
export async function fetchPlan() {
  try {
    return await request('/plan')
  } catch (e) {
    if (e.status === 404) return null
    throw e
  }
}

/** Nessie source account. Live: real balance. Stub: balance null, simulated true. */
export const fetchFundingAccount = () => request('/funding-account')

/** Live activity stream (EventSource URL). Ends after a `done` event. */
export const eventsUrl = (runId) => `${BASE}/events/${encodeURIComponent(runId)}`

/** Every recorded event of a run, at once (replay with no delay). */
export async function fetchEvents(runId) {
  const res = await fetch(`${eventsUrl(runId)}?replay=1&delay=0`)
  if (!res.ok) throw new ApiError(res.status, `events ${res.status}`)
  const text = await res.text()
  return text
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .map((l) => {
      try {
        return JSON.parse(l.slice(5))
      } catch {
        return null
      }
    })
    .filter(Boolean)
}

// Resolve a (possibly relative) asset URL from the API against the backend base.
export function assetUrl(url) {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${BASE}${url}`
}

// Matterport Showcase URL for an embedded interactive tour.
export function showcaseSrc(modelId, { play = 1 } = {}) {
  return `https://my.matterport.com/show/?m=${modelId}&play=${play}`
}
