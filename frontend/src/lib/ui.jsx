import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

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
