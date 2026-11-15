import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clampTarget } from './model'

// ---------------------------------------------------------------------------
// Goal — the carbon reduction target, shared across every page and persisted to
// localStorage so it survives navigation and reloads.
// ---------------------------------------------------------------------------
const GOAL_KEY = 'hawklens.target'
const DEFAULT_TARGET = 40

function readStoredTarget() {
  if (typeof window === 'undefined') return DEFAULT_TARGET
  const raw = window.localStorage.getItem(GOAL_KEY)
  const n = Number(raw)
  return raw !== null && Number.isFinite(n) ? clampTarget(n) : DEFAULT_TARGET
}

const GoalContext = createContext(null)

export function GoalProvider({ children }) {
  const [target, setTargetState] = useState(readStoredTarget)

  const setTarget = useCallback((next) => {
    setTargetState((prev) => {
      const value = clampTarget(typeof next === 'function' ? next(prev) : next)
      try {
        window.localStorage.setItem(GOAL_KEY, String(value))
      } catch {
        /* ignore storage errors (private mode, etc.) */
      }
      return value
    })
  }, [])

  // Keep multiple tabs/windows in sync.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === GOAL_KEY) setTargetState(readStoredTarget())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  return <GoalContext.Provider value={{ target, setTarget }}>{children}</GoalContext.Provider>
}

export function useGoal() {
  const ctx = useContext(GoalContext)
  if (!ctx) throw new Error('useGoal must be used within a GoalProvider')
  return ctx
}

// ---------------------------------------------------------------------------
// Toast — shared transient feedback used when a control has no real destination.
// ---------------------------------------------------------------------------
const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [message, setMessage] = useState(null)
  const timer = useRef(null)

  const flash = useCallback((msg) => {
    setMessage(msg)
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMessage(null), 1800)
  }, [])

  return (
    <ToastContext.Provider value={flash}>
      {children}
      <div
        className={`fixed left-1/2 -translate-x-1/2 bottom-[24px] z-50 px-4 py-2 rounded-[8px] bg-ink text-white text-[13px] shadow-lg transition-all duration-200 ${
          message ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
        }`}
      >
        {message}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

// A link/button that navigates to a route, or flashes a toast if `to` is null.
export function useGo() {
  const navigate = useNavigate()
  const flash = useToast()
  return useCallback(
    (to, toastMsg) => {
      if (to) navigate(to)
      else if (toastMsg) flash(toastMsg)
    },
    [navigate, flash],
  )
}
