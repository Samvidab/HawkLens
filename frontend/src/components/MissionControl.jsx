
import { useEffect, useState } from 'react'
import './MissionControl.css'

export default function MissionControl() {
  const [active, setActive] = useState(() => { try { return localStorage.getItem('hawklens.theme') === 'dark' } catch { return false } })

  useEffect(() => {
    document.body.classList.toggle('mission-mode', active)
    try { localStorage.setItem('hawklens.theme', active ? 'dark' : 'light') } catch {}

    return () => {
      document.body.classList.remove('mission-mode')
    }
  }, [active])

  return (
    <button
      type="button"
      className={`mission-toggle ${active ? 'is-active' : ''}`}
      onClick={() => setActive(!active)}
      aria-label="Toggle Mission Control theme"
      aria-pressed={active}
    >
      <span className="mission-status-dot" />
      {active ? '☀️' : '🌙'}
    </button>
  )
}
