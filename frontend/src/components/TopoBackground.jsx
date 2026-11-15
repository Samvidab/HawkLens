
import { useEffect, useRef } from 'react'
import './TopoBackground.css'

export default function TopoBackground() {
  const ref = useRef(null)

  useEffect(() => {
    function move(e) {
      if (!ref.current) return

      const x = (e.clientX / window.innerWidth - 0.5) * 18
      const y = (e.clientY / window.innerHeight - 0.5) * 18

      ref.current.style.transform =
        `translate(${x}px, ${y}px) scale(1.08)`
    }

    window.addEventListener('pointermove', move)

    return () => {
      window.removeEventListener('pointermove', move)
    }
  }, [])

  return (
    <div className="topo-background" aria-hidden="true">
      <svg
        ref={ref}
        viewBox="0 0 1200 900"
        preserveAspectRatio="xMidYMid slice"
      >
        {Array.from({ length: 22 }, (_, i) => (
          <ellipse
            key={i}
            cx="850"
            cy="400"
            rx={140 + i * 33}
            ry={75 + i * 25}
            fill="none"
            stroke="#687D6D"
            strokeWidth="1"
            opacity="0.25"
            transform={`rotate(-22 850 400)`}
          />
        ))}
      </svg>
    </div>
  )
}
