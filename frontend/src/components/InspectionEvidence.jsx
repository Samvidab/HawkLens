// From the Codex 3D work (codex-3d-work 229f721), adapted to main: API base from VITE_API_URL, theme classes for mission mode.
import { useEffect, useRef, useState } from 'react'
import { ourApiBase } from '../lib/co2Api'

export const NO_IMAGE_LOCATION = 'Exact object location not verified in image.'

// Coordinates belong only to the exact recorded image and this verified claim.
// Reject malformed/out-of-range marks rather than clipping or inventing geometry.
export function evidenceMarks(item) {
  if (item?.verifier?.status !== 'verified' || !item.image_id ||
      !item.claim?.evidence_ids?.includes(item.image_id)) return []
  const unit = (n) => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1
  return (Array.isArray(item.image_marks) ? item.image_marks : []).flatMap((mark) => {
    if (!mark || mark.image_id !== item.image_id) return []
    const b = mark.bbox
    if (Array.isArray(b) && b.length === 4 && b.every(unit) && b[0] < b[2] && b[1] < b[3]) {
      return [{ label: mark.label, bbox: b }]
    }
    const p = mark.polygon
    if (Array.isArray(p) && p.length >= 3 && p.every((v) => Array.isArray(v) && v.length === 2 && v.every(unit))) {
      const area = p.reduce((a, v, i) => { const w = p[(i + 1) % p.length]; return a + v[0] * w[1] - w[0] * v[1] }, 0)
      if (Math.abs(area) > 0) return [{ label: mark.label, polygon: p }]
    }
    return []
  })
}

export default function InspectionEvidence({ item, onClose }) {
  const API_BASE = ourApiBase() // main: the same VITE_API_URL backend serves /media
  const dialog = useRef(null)
  const [zoom, setZoom] = useState(null) // null fits the image; 1 = one recorded pixel per CSS pixel
  const nativeSize = zoom !== null
  const scroll = useRef(null)
  const drag = useRef(null)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const [size, setSize] = useState(null)
  const marks = evidenceMarks(item)
  useEffect(() => {
    const previous = document.activeElement
    const node = dialog.current
    if (node?.showModal) node.showModal()
    else node?.setAttribute('open', '')
    return () => { node?.close?.(); previous?.focus?.() }
  }, [])
  useEffect(() => { setLoaded(false); setFailed(false); setSize(null); setZoom(null) }, [item.image_id])

  const changeZoom = (factor, point) => {
    const viewport = scroll.current
    const image = viewport?.querySelector('img')
    if (!size || !image || !viewport) return
    const rect = image.getBoundingClientRect()
    const bounds = viewport.getBoundingClientRect()
    const x = point?.x ?? bounds.left + viewport.clientWidth / 2
    const y = point?.y ?? bounds.top + viewport.clientHeight / 2
    const u = Math.max(0, Math.min(1, (x - rect.left) / rect.width))
    const v = Math.max(0, Math.min(1, (y - rect.top) / rect.height))
    const next = Math.min(4, Math.max(0.1, rect.width / size.width * factor))
    setZoom(next)
    requestAnimationFrame(() => {
      viewport.scrollLeft = u * size.width * next - (x - bounds.left)
      viewport.scrollTop = v * size.height * next - (y - bounds.top)
    })
  }

  useEffect(() => {
    const node = scroll.current
    const wheel = (e) => { e.preventDefault(); changeZoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, { x: e.clientX, y: e.clientY }) }
    node?.addEventListener('wheel', wheel, { passive: false })
    return () => node?.removeEventListener('wheel', wheel)
  }, [size])

  return (
    <dialog ref={dialog} className="co2-evidence" aria-labelledby="inspection-evidence-title" onCancel={(e) => { e.preventDefault(); onClose() }}
      style={{ width: 'calc(100vw - 32px)', maxWidth: 1600, maxHeight: 'calc(100vh - 32px)', padding: 20, border: '1px solid #ccc', borderRadius: 8 }}>
      <div className="flex justify-between gap-4 items-start">
        <div>
          <h2 id="inspection-evidence-title" className="font-semibold text-ink">Inspection Close-Up · {item.equipment} — recorded evidence</h2>
          <p className="text-[13px] text-muted">Photo taken here · 3D fixture position remains unverified.</p>
        </div>
        <button type="button" autoFocus onClick={onClose} className="text-brand underline">Close evidence</button>
      </div>
      <p className="my-2 text-[13px]" data-testid="evidence-location-status">
        {marks.length ? `${marks.length} recorded object mark${marks.length === 1 ? '' : 's'} outlined. Ellipses follow the recorded box bounds; they do not verify a 3D fixture position.` : NO_IMAGE_LOCATION}
      </p>
      <div className="flex flex-wrap gap-4 mb-2 text-[13px]">
        <button type="button" data-testid="return-to-tour" onClick={onClose} className="text-brand underline">← Matterport 3D View</button>
        {item.image_url && <a href={`${API_BASE}${item.image_url}`} target="_blank" rel="noreferrer" className="text-brand underline">Open original image</a>}
        <button type="button" onClick={() => setZoom((v) => v === null ? 1 : null)} className="text-brand underline" aria-pressed={nativeSize}>
          {nativeSize ? 'Fit image' : 'View at original size (1:1)'}
        </button>
        <button type="button" disabled={!loaded} onClick={() => changeZoom(1.25)} className="text-brand underline">Zoom in</button>
        <button type="button" disabled={!loaded} onClick={() => changeZoom(0.8)} className="text-brand underline">Zoom out</button>
        {zoom !== null && zoom !== 1 && <button type="button" onClick={() => setZoom(1)} className="text-brand underline">1:1 pixels</button>}
        <span data-testid="evidence-zoom">{zoom === null ? 'Fit' : `${Math.round(zoom * 100)}%`}</span>
        {size && <span>{size.width} × {size.height} recorded pixels</span>}
      </div>
      {failed && <p role="alert">Recorded evidence image could not be loaded.</p>}
      {!item.image_url && <p>Recorded evidence image is not available.</p>}
      <p className="text-[12px] text-muted mb-2">Scroll to zoom · drag to pan · above 100% magnifies existing pixels without adding detail.</p>
      <div ref={scroll} data-testid="evidence-image-scroll"
        onPointerDown={(e) => {
          if (e.button !== 0) return
          const node = e.currentTarget
          drag.current = { x: e.clientX, y: e.clientY, left: node.scrollLeft, top: node.scrollTop }
          node.setPointerCapture?.(e.pointerId)
        }}
        onPointerMove={(e) => {
          if (!drag.current) return
          e.currentTarget.scrollLeft = drag.current.left - (e.clientX - drag.current.x)
          e.currentTarget.scrollTop = drag.current.top - (e.clientY - drag.current.y)
        }}
        onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}
        className="co2-evidence-scroll" style={{ overflow: 'auto', maxHeight: '65vh', textAlign: nativeSize ? 'left' : 'center', cursor: nativeSize ? 'grab' : 'zoom-in', touchAction: 'none' }}>
        {item.image_url && !failed && (
          <div data-testid="evidence-image-frame" style={{ display: 'inline-block', position: 'relative', verticalAlign: 'top', lineHeight: 0, maxWidth: nativeSize ? 'none' : '100%' }}>
            <img src={`${API_BASE}${item.image_url}`} alt={`Recorded inspection evidence: ${item.equipment}`}
              data-testid="evidence-image" draggable={false} onError={() => { setFailed(true); setLoaded(false) }}
              onLoad={(e) => { setSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight }); setLoaded(true) }}
              style={{ display: 'block', width: nativeSize && size ? size.width * zoom : 'auto', height: nativeSize && size ? size.height * zoom : 'auto', maxWidth: nativeSize ? 'none' : '100%', maxHeight: nativeSize ? 'none' : '65vh' }} />
            {loaded && marks.length > 0 && (
              <svg data-testid="evidence-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Recorded object marks"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                {marks.map((m, i) => {
                  const geometry = m.bbox
                    ? <ellipse vectorEffect="non-scaling-stroke" cx={(m.bbox[0] + m.bbox[2]) / 2} cy={(m.bbox[1] + m.bbox[3]) / 2} rx={(m.bbox[2] - m.bbox[0]) / 2} ry={(m.bbox[3] - m.bbox[1]) / 2} />
                    : <polygon vectorEffect="non-scaling-stroke" points={m.polygon.map((v) => v.join(',')).join(' ')} />
                  return <g key={i} data-testid="evidence-mark"><title>{m.label || 'Recorded object mark'}</title>
                    <g fill="none" stroke="#111" strokeWidth="6" vectorEffect="non-scaling-stroke">{geometry}</g>
                    <g fill="none" stroke="#ffdd00" strokeWidth="3" vectorEffect="non-scaling-stroke">{geometry}</g>
                  </g>
                })}
              </svg>
            )}
          </div>
        )}
      </div>
      <p className="text-[12px] text-muted mt-2">Original recorded image, without sharpening or generated detail. Any source blur or privacy masking remains. Outlines reproduce saved annotations and may be inaccurate; the verifier status below is from the recorded survey.</p>
      {marks.length > 1 && <p className="text-[13px] mt-2">This evidence image contains multiple recorded marks; all matching marks are shown.</p>}
      <p className="text-[13px] mt-2">Claim: {item.claim?.field} = {String(item.claim?.value ?? 'unknown')} · Verifier: {item.verifier?.status}{item.verifier?.note ? ` — ${item.verifier.note}` : ''}</p>
    </dialog>
  )
}
