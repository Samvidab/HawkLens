import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import * as realApi from './api'

// Run state shared by all screens: the current run, its activity feed, the latest layout and the owner's actions.
// Pages show unavailable states without a loaded backend layout; there is no prototype fallback.

const STORAGE_KEY = 'hawklens.runId'
const POLL_MS = 400
const POLL_TRIES = 25

const store = (() => {
  try { return globalThis.sessionStorage } catch { return null }
})()
const remember = (id) => { try { id ? store?.setItem(STORAGE_KEY, id) : store?.removeItem(STORAGE_KEY) } catch { /* private mode */ } }
const recall = () => { try { return store?.getItem(STORAGE_KEY) || null } catch { return null } }

const Ctx = createContext(null)
export const INERT = { health: null, prefs: { target_pct: 40, budget_usd: null, risk_lambda: 0.2 }, setPrefs: () => {}, runId: null, phase: 'idle', events: [], state: null, layout: null, portfolio: null, busy: 0, error: null,
  start: async () => null, act: async () => null, refresh: async () => null, reset: () => {}, live: false }
export const useRun = () => useContext(Ctx) || INERT

/** Plan-oriented screens (portfolio, plan, risk, financing, memo) need the portfolio view: the layout has `plan_table` and
 *  no focused building. If the run is looking at a building (or at a screen without the plan), ask the backend to go back. */
export function useOverview({ requireTarget = false } = {}) {
  const run = useRun()
  const L = run.layout
  const need = !!L && (!!L.focus_building_id || !L.widgets.some((w) => w.type === 'plan_table') || (requireTarget && !L.widgets.some((w) => w.type === 'target_control')))
  const tries = useRef(0)
  useEffect(() => {
    if (!need) { tries.current = 0; return }
    if (run.busy || tries.current >= 2) return
    tries.current += 1
    run.act('open_building', { building_id: null }).catch(() => {})
  }, [need, run.busy]) // eslint-disable-line react-hooks/exhaustive-deps
  return run
}

/** Building screens need a focused building: open `fallbackId` (default: the portfolio's hero) when none is. */
export function useBuildingFocus(fallbackId) {
  const run = useRun()
  const L = run.layout
  const id = fallbackId || run.portfolio?.buildings?.find((b) => b.hero)?.building_id || run.portfolio?.buildings?.[0]?.building_id
  const need = !!L && !L.focus_building_id && !!id
  const tries = useRef(0)
  useEffect(() => {
    if (!need) { tries.current = 0; return }
    if (run.busy || tries.current >= 2) return
    tries.current += 1
    run.act('open_building', { building_id: id }).catch(() => {})
  }, [need, id, run.busy]) // eslint-disable-line react-hooks/exhaustive-deps
  return run
}

export function RunProvider({ children, api = realApi, demoRunId }) {
  const [runId, setRunId] = useState(null)
  const [events, setEvents] = useState([])
  const [state, setState] = useState(null)
  const [phase, setPhase] = useState('idle') // idle | surveying | ready | error
  const [busy, setBusy] = useState(0)
  const [error, setError] = useState(null)
  const [portfolio, setPortfolio] = useState(null)
  const [health, setHealth] = useState(null) // { engine_mode, nessie_mode, cache_mode, ... }
  const [prefs, setPrefsState] = useState({ target_pct: 40, budget_usd: null, risk_lambda: 0.2 }) // the goal the owner is shaping (no budget cap until chosen: the prototype's $1500k would not fit a real portfolio)
  const closeFeed = useRef(null)
  const alive = useRef(true)
  const idRef = useRef(null)
  const actionQueue = useRef(Promise.resolve())
  const [connectionLoading, setConnectionLoading] = useState(true)

  const fail = useCallback((e) => { if (alive.current) setError(e?.message || String(e)) }, [])

  const loadState = useCallback(async (id) => {
    const s = await api.getState(id)
    if (alive.current && idRef.current === id) {
      setState(s)
      if (s.goal) setPrefsState((p) => ({ ...p, ...s.goal }))
    }
    return s
  }, [api])

  // Wait for the pipeline to leave a workspace in state.json (status `ready` or `error`).
  const settle = useCallback(async (id, { replay = false } = {}) => {
    let s = null
    for (let i = 0; i < POLL_TRIES; i++) {
      try { s = await loadState(id) } catch (e) { if (e.status !== 404) throw e }
      if (s && (s.layout || s.status === 'ready' || s.status === 'error')) break
      if (replay && s) break // an old recorded run will never finish by itself: build its workspace below
      await new Promise((r) => setTimeout(r, POLL_MS))
    }
    if (!s) throw new Error('The run left no state')
    if (!s.layout && s.status !== 'error' && s.goal) { // a replayed/old run with no workspace yet: build it from its goal
      await api.compose(id, 'goal', s.goal)
      s = await loadState(id)
    }
    if (!alive.current) return s
    if (s.layout) { setPhase('ready') } else { setPhase('error'); setError(s.error || 'The run finished without a workspace') }
    return s
  }, [api, loadState])

  // Recorded events of a run (the server replays its events.jsonl instantly with delay=0): used after a reload and after
  // every action, because the live stream ended at `done`.
  const loadEvents = useCallback((id) => new Promise((resolve) => {
    const acc = []
    const commit = () => { if (alive.current && idRef.current === id && acc.length) setEvents(acc); resolve() }
    api.openEvents(id, { replay: true, delay: 0, onEvent: (e) => acc.push(e), onEnd: commit, onError: commit })
  }), [api])

  const attach = useCallback((id, { replay = false } = {}) => {
    closeFeed.current?.()
    idRef.current = id
    setRunId(id); remember(id); setEvents([]); setState(null); setError(null); setPhase('surveying')
    let doneSeen = false
    closeFeed.current = api.openEvents(id, {
      replay,
      onEvent: (ev) => alive.current && setEvents((evs) => (evs.some((e) => e.seq === ev.seq) ? evs : [...evs, ev])),
      onEnd: () => { if (replay && !doneSeen) { fail(new Error('Recorded activity stream ended before completion')); setPhase('error') } },
      onDone: () => { doneSeen = true; settle(id, { replay }).catch((e) => { fail(e); setPhase('error') }) },
      onError: (e) => { fail(e); setPhase('error') },
    })
    return id
  }, [api, settle, fail])

  /** goal: { city, building_ids?, target_pct, budget_usd?, risk_lambda }. With demoRunId (or opts.replayRunId) the recorded
   *  run's feed is replayed offline instead of surveying again. */
  const start = useCallback(async (goal, opts = {}) => {
    setError(null)
    const replayId = opts.replayRunId ?? (opts.replay ? demoRunId : null)
    try {
      if (replayId) return attach(replayId, { replay: true })
      const { run_id } = await api.startRun(goal)
      return attach(run_id)
    } catch (e) { fail(e); setPhase('error'); return null }
  }, [api, attach, fail, demoRunId])

  const setPrefs = useCallback((patch) => setPrefsState((p) => ({ ...p, ...patch })), [])

  const refresh = useCallback(async () => {
    try { const result = idRef.current ? await loadState(idRef.current) : null; setError(null); return result }
    catch (e) { fail(e); throw e }
  }, [loadState, fail])

  /** Send an OwnerAction; resolves to the new layout and keeps `state` (plan_id, view) in sync. */
  const act = useCallback((type, payload = {}) => {
    const id = idRef.current
    if (!id) return Promise.reject(new Error('No run yet: load a recorded survey or start a survey first'))
    setBusy((n) => n + 1)
    const execute = async () => {
      if (idRef.current !== id) throw new Error('The active survey changed; retry this action')
      try {
        const layout = await api.compose(id, type, payload)
        if (alive.current && idRef.current === id) { setError(null); setState((s) => ({ ...(s || {}), layout })) }
        try { localStorage.setItem('hawklens.backend-update', JSON.stringify({runId:id,at:Date.now()})) } catch {}
        await loadState(id) // approval and later actions must use the matching backend plan id
        loadEvents(id).catch(fail)
        return layout
      } catch (e) { fail(e); throw e }
    }
    const next = actionQueue.current.then(execute)
    actionQueue.current = next.catch(() => {})
    return next.finally(() => setBusy((n) => n - 1))
  }, [api, loadState, loadEvents, fail])

  // Samvidab's cross-tab goal persistence, adapted to backend-owned results rather than prototype figures.
  useEffect(() => {
    const update = (event) => {
      if(event.key !== 'hawklens.backend-update') return
      try { if(JSON.parse(event.newValue)?.runId === idRef.current) refresh().catch(() => {}) } catch {}
    }
    window.addEventListener('storage', update)
    return () => window.removeEventListener('storage', update)
  }, [refresh])

  const reset = useCallback(() => {
    closeFeed.current?.(); idRef.current = null
    setRunId(null); remember(null); setEvents([]); setState(null); setError(null); setPhase('idle')
  }, [])

  useEffect(() => {
    alive.current = true
    Promise.allSettled([
      api.getPortfolio().then((p) => alive.current && setPortfolio(p)).catch(fail),
      api.getHealth().then((h) => alive.current && setHealth(h)).catch(fail),
    ]).then(() => alive.current && setConnectionLoading(false))
    const saved = recall()
    if (saved) { // resume after a reload
      idRef.current = saved; setRunId(saved)
      loadState(saved).then((s) => { if (alive.current) setPhase(s.layout ? 'ready' : s.status === 'error' ? 'error' : 'surveying'); loadEvents(saved) })
        .catch((e) => { fail(e); setPhase('error'); if (e.status === 404) { remember(null); idRef.current = null; setRunId(null) } })
    }
    return () => { alive.current = false; closeFeed.current?.() }
  }, [api, loadState, loadEvents])

  const value = useMemo(() => ({
    connectionLoading, runId, phase, events, state, layout: state?.layout ?? null, portfolio, busy, error, start, act, refresh, reset, live: true, demoRunId, prefs, setPrefs, health,
  }), [connectionLoading, runId, phase, events, state, portfolio, busy, error, start, act, refresh, reset, demoRunId, prefs, setPrefs, health])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
