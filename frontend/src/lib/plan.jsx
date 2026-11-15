import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { compose, fetchPlan, startRun } from './api'
import { clampTarget } from './model'

// ---------------------------------------------------------------------------
// The plan store. Every page reads the same persisted plan (GET /plan, written by the backend's pricing node
// from the quant engine). Controls never change numbers locally: they send an owner action to POST /compose
// (set_target / set_budget / set_risk / goal / approve), wait for the re-plan, then re-read GET /plan.
//
// Only owner *inputs* live here before a plan exists (the goal to start a survey with). No metric does.
// ---------------------------------------------------------------------------
const RUN_KEY = 'hawklens.runId'
const DEFAULT_DRAFT = { target_pct: 40, budget_usd: null, risk_lambda: 0.5 } // App Flow default target 40 %
const TARGET_DEBOUNCE_MS = 450

function readRunId() {
  try {
    return window.localStorage.getItem(RUN_KEY)
  } catch {
    return null
  }
}

function writeRunId(id) {
  try {
    if (id) window.localStorage.setItem(RUN_KEY, id)
  } catch {
    /* storage unavailable: the plan's own run_id is the fallback */
  }
}

const PlanContext = createContext(null)

export function PlanProvider({ children }) {
  const [plan, setPlan] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [runId, setRunIdState] = useState(readRunId)
  const [draft, setDraft] = useState(DEFAULT_DRAFT)
  const [pendingTarget, setPendingTarget] = useState(null)
  const seq = useRef(0)
  const inflight = useRef(0)
  const targetTimer = useRef(null)

  const setRunId = useCallback((id) => {
    setRunIdState(id)
    writeRunId(id)
  }, [])

  // Latest request wins: an older GET /plan that resolves late never overwrites a newer one.
  const refresh = useCallback(async () => {
    const id = ++seq.current
    try {
      const p = await fetchPlan()
      if (id === seq.current) {
        setPlan(p)
        setLoadError(null)
      }
      return p
    } catch (e) {
      if (id === seq.current) setLoadError(e.message)
      return null
    } finally {
      if (id === seq.current) setLoaded(true)
    }
  }, [])

  useEffect(() => {
    refresh()
    const onFocus = () => refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refresh])

  const activeRunId = runId || plan?.run_id || null

  /** Send one owner action and re-read the plan. Returns { ok, error }. */
  const act = useCallback(
    async (type, payload = {}, { runIdOverride } = {}) => {
      const rid = runIdOverride || activeRunId
      if (!rid) {
        const msg = 'Run the survey first: there is no plan to change yet.'
        setActionError(msg)
        return { ok: false, error: new Error(msg) }
      }
      inflight.current += 1
      setBusy(true)
      try {
        await compose(rid, type, payload)
        setActionError(null)
        await refresh()
        return { ok: true }
      } catch (e) {
        setActionError(e.message)
        await refresh() // show whatever the backend now holds, not a guess
        return { ok: false, error: e }
      } finally {
        inflight.current -= 1
        setBusy(inflight.current > 0)
      }
    },
    [activeRunId, refresh],
  )

  const hasGoal = Boolean(plan?.goal)
  const goal = plan?.goal || draft

  /** Carbon target: re-plans on the backend (debounced while dragging); before any plan it sets the draft. */
  const requestTarget = useCallback(
    (value) => {
      const v = clampTarget(value)
      if (!hasGoal) {
        setDraft((d) => ({ ...d, target_pct: v }))
        return
      }
      setPendingTarget(v)
      if (targetTimer.current) window.clearTimeout(targetTimer.current)
      targetTimer.current = window.setTimeout(async () => {
        await act('set_target', { target_pct: v })
        setPendingTarget(null)
      }, TARGET_DEBOUNCE_MS)
    },
    [act, hasGoal],
  )

  const setDraftOr = useCallback(
    (type, key) => async (value) => {
      if (hasGoal) return act(type, { [key]: value })
      setDraft((d) => ({ ...d, [key]: value }))
      return { ok: true }
    },
    [act, hasGoal],
  )
  const requestBudget = useMemo(() => setDraftOr('set_budget', 'budget_usd'), [setDraftOr])
  const requestRisk = useMemo(() => setDraftOr('set_risk', 'risk_lambda'), [setDraftOr])

  const goalForRun = useCallback(
    () => ({
      city: 'Houston',
      target_pct: goal.target_pct,
      budget_usd: goal.budget_usd ?? null,
      risk_lambda: goal.risk_lambda ?? DEFAULT_DRAFT.risk_lambda,
    }),
    [goal],
  )

  /** POST /run (survey -> pricing -> compose). Resolves to the new run_id. */
  const startSurvey = useCallback(async () => {
    const { run_id: rid } = await startRun(goalForRun())
    setRunId(rid)
    return rid
  }, [goalForRun, setRunId])

  /** Re-price with the survey results already on the backend (a `goal` action surveys only missing buildings). */
  const repriceExisting = useCallback(async () => {
    const rid = activeRunId || `run_${Math.random().toString(16).slice(2, 10)}`
    setRunId(rid)
    return act('goal', goalForRun(), { runIdOverride: rid })
  }, [act, activeRunId, goalForRun, setRunId])

  const value = useMemo(
    () => ({
      plan,
      loaded,
      loadError,
      actionError,
      clearActionError: () => setActionError(null),
      busy: busy || pendingTarget !== null,
      runId: activeRunId,
      setRunId,
      goal,
      displayTarget: pendingTarget ?? goal.target_pct,
      refresh,
      act,
      requestTarget,
      requestBudget,
      requestRisk,
      startSurvey,
      repriceExisting,
    }),
    [plan, loaded, loadError, actionError, busy, pendingTarget, activeRunId, setRunId, goal, refresh, act,
      requestTarget, requestBudget, requestRisk, startSurvey, repriceExisting],
  )

  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>
}

export function usePlan() {
  const ctx = useContext(PlanContext)
  if (!ctx) throw new Error('usePlan must be used within a PlanProvider')
  return ctx
}

/** True when the plan has engine numbers to show (priced, ok or infeasible). */
export const isPriced = (plan) => Boolean(plan && plan.status !== 'no_data' && plan.selected)
