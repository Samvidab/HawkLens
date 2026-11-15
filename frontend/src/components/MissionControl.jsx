
import { useEffect, useState } from 'react'
import './MissionControl.css'

export default function MissionControl() {
  const [active, setActive] = useState(false)

  useEffect(() => {
    document.body.classList.toggle('mission-mode', active)

    return () => {
      document.body.classList.remove('mission-mode')
    }
  }, [active])

  return (
    <button
      type="button"
      className={`mission-toggle ${active ? 'is-active' : ''}`}
      onClick={() => setActive(!active)}
      aria-pressed={active}
    >
      <span className="mission-status-dot" />
      {active ? '☀️' : '🌙'}
    </button>
  )
}
