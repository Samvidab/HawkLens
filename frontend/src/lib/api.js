// Client for the HawkLens backend (agent API + Matterport property data).
//
//   POST /run            startRun(goal)                  -> { run_id }
//   GET  /events/{id}    openEvents(runId, handlers)     -> close()   (Server-Sent Events, ends with a `done` event)
//   GET  /state/{id}     getState(runId)                 -> { layout, plan_id, goal, status, results, view, ... }
//   POST /compose        compose(runId, type, payload)   -> layout    (an OwnerAction; see ACTIONS below)
//
// Base URL: VITE_API_URL (or the older VITE_API_BASE), default http://localhost:8000.
// The backend allows http://localhost:5173 by default; set CORS_ORIGINS on the server for a deployed origin.

const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
export const API_BASE = String(env.VITE_API_URL || env.VITE_API_BASE || 'http://localhost:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function detailOf(data, fallback) {
  const d = data && data.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ')
  return fallback
}

async function request(method, path, body, fetchImpl = globalThis.fetch) {
  let res
  try {
    res = await fetchImpl(API_BASE + path, {
      method,
      headers: body === undefined ? undefined : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (e) {
    throw new ApiError(0, `Cannot reach the backend at ${API_BASE}`)
  }
  let data = null
  try {
    data = await res.json()
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(data, res.statusText || `HTTP ${res.status}`))
  return data
}

export const getHealth = () => request('GET', '/health')
export const getPortfolio = () => request('GET', '/portfolio')
export const getRegistry = () => request('GET', '/registry')
/** The quant engine's sourced pricing assumptions for a city (GET /assumptions). */
export const getAssumptions = (city) => request('GET', `/assumptions${city ? `?city=${encodeURIComponent(city)}` : ''}`)

/** goal: { city, building_ids?, target_pct (0-100), budget_usd?, risk_lambda (0-1) } */
export const startRun = (goal) => request('POST', '/run', goal)
export const getState = (runId) => request('GET', `/state/${encodeURIComponent(runId)}`)

/**
 * OwnerAction types (payload):
 *   goal {Goal} | set_target {target_pct} | set_budget {budget_usd|null} | set_risk {risk_lambda}
 *   exclude_building / include_building {building_id} | toggle_upgrade {upgrade_id, on} | include_unverified {upgrade_id}
 *   select_bar {upgrade_id} | open_building {building_id|null} | approve {plan_id}
 * Resolves to the new layout. Errors: 409 (no goal yet / stale plan_id), 422 (bad payload), 502 (Nessie).
 */
export const compose = (runId, type, payload = {}) => request('POST', '/compose', { run_id: runId, type, payload })

export const mediaUrl = (imageId) => `${API_BASE}/media/${encodeURIComponent(imageId)}`

/**
 * Subscribe to a run's activity feed. Calls onEvent(ev) for every ActivityEvent
 * { ts, run_id, seq, agent, building_id, building_name, kind, message, evidence_id } (past events first),
 * then onDone(ev) and, for a LIVE run, CLOSES on the `done` event (otherwise EventSource reconnects and replays everything).
 * replay: stream a recorded run (paced ~35 s for the demo; `delay` seconds per event overrides, 0 = at once). A replay keeps
 * reading past `done` (owner actions are recorded after it) and calls onEnd() when the server ends the stream.
 * Returns close().
 */
export function openEvents(runId, { replay = false, delay, onEvent, onDone, onEnd, onError, EventSourceImpl } = {}) {
  const ES = EventSourceImpl || globalThis.EventSource
  const q = new URLSearchParams()
  if (replay) q.set('replay', '1')
  if (delay !== undefined) q.set('delay', String(delay))
  const es = new ES(`${API_BASE}/events/${encodeURIComponent(runId)}${q.size ? `?${q}` : ''}`)
  let finished = false
  let doneSeen = false
  const close = () => {
    finished = true
    es.close()
  }
  es.onmessage = (m) => {
    let ev
    try {
      ev = JSON.parse(m.data)
    } catch {
      return
    }
    onEvent && onEvent(ev)
    if (ev.kind === 'done' && !doneSeen) {
      doneSeen = true
      onDone && onDone(ev)
      // A live stream is over at `done` (the server closes it; EventSource would reconnect and replay everything).
      // A recorded run can carry later events (owner actions) after its `done`: keep reading until the server ends it.
      if (!replay) close()
    }
  }
  es.onerror = () => {
    if (finished) return
    close()
    if (replay) onEnd && onEnd() // the server ended the recorded stream: that is the normal end of a replay
    else onError && onError(new ApiError(0, 'Lost the activity stream'))
  }
  return close
}

// ---- Matterport property platform (branch matterport-ui) --------------------------------------------------------
export async function fetchProperties({ q, limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  return request('GET', `/properties?${params.toString()}`)
}

export const fetchProperty = (id) => request('GET', `/properties/${id}`)

// Resolve a (possibly relative) asset URL from the API against the backend base.
export function assetUrl(url) {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${API_BASE}${url}`
}

// Matterport Showcase URL for an embedded interactive tour (same format as `showcase_url` in hero_3d props).
export function showcaseSrc(modelId, { play = 1 } = {}) {
  return `https://my.matterport.com/show/?m=${modelId}&play=${play}`
}
