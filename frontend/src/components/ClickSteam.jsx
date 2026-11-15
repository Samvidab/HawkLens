
import { useEffect, useRef } from 'react'
import './ClickSteam.css'

export default function ClickSteam() {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const clouds = []

    let animationId
    let lastSpawn = 0
    let lastX = null
    let lastY = null

    function resize() {
      const dpr = window.devicePixelRatio || 1
      canvas.width = window.innerWidth * dpr
      canvas.height = window.innerHeight * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function move(e) {
      const now = performance.now()

      if (lastX === null) {
        lastX = e.clientX
        lastY = e.clientY
        return
      }

      const dx = e.clientX - lastX
      const dy = e.clientY - lastY

      if (Math.hypot(dx, dy) > 5 && now - lastSpawn > 45) {
        clouds.push({
          x: e.clientX - dx * 0.7,
          y: e.clientY - dy * 0.7,
          size: 10 + Math.random() * 5,
          life: 1,
          vx: (Math.random() - 0.5) * 0.3
        })

        // Only keep four clouds
        if (clouds.length > 4) {
          clouds.shift()
        }

        lastSpawn = now
      }

      lastX = e.clientX
      lastY = e.clientY
    }

    function animate() {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)

      for (let i = clouds.length - 1; i >= 0; i--) {
        const c = clouds[i]

        c.y -= 0.35
        c.x += c.vx + Math.sin(c.life * 12) * 0.15
        c.size += 0.18
        c.life -= 0.013

        if (c.life <= 0) {
          clouds.splice(i, 1)
          continue
        }

        const gradient = ctx.createRadialGradient(
          c.x, c.y, 0,
          c.x, c.y, c.size
        )

        gradient.addColorStop(
        0,
        `rgba(75, 80, 80, ${c.life * 0.5})`
        )

        gradient.addColorStop(
        0.4,
        `rgba(110, 115, 115, ${c.life * 0.3})`
        )

        gradient.addColorStop(
        1,
        'rgba(160, 160, 160, 0)'
        )
        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.arc(c.x, c.y, c.size, 0, Math.PI * 2)
        ctx.fill()
      }

      animationId = requestAnimationFrame(animate)
    }

    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', move)

    animationId = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', move)
    }
  }, [])

  return <canvas ref={canvasRef} className="smoke-canvas" aria-hidden="true" />
}
