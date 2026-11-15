import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '../lib/api'

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
  const dialog = useRef(null)
  const [nativeSize, setNativeSize] = useState(false)
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
  useEffect(() => { setLoaded(false); setFailed(false); setSize(null); setNativeSize(false) }, [item.image_id])

  return (
    <dialog ref={dialog} aria-labelledby="inspection-evidence-title" onCancel={(e) => { e.preventDefault(); onClose() }}
      style={{ width: 'calc(100vw - 32px)', maxWidth: 1600, maxHeight: 'calc(100vh - 32px)', padding: 20, border: '1px solid #ccc', borderRadius: 8 }}>
      <div className="flex justify-between gap-4 items-start">
        <div>
          <h2 id="inspection-evidence-title" className="font-semibold text-ink">{item.equipment} — recorded evidence</h2>
          <p className="text-[13px] text-muted">Photo taken here · 3D fixture position remains unverified.</p>
        </div>
        <button type="button" autoFocus onClick={onClose} className="text-brand underline">Close evidence</button>
      </div>
      <p className="my-2 text-[13px]" data-testid="evidence-location-status">
        {marks.length ? `${marks.length} recorded object mark${marks.length === 1 ? '' : 's'} outlined. Image marks do not verify a 3D fixture position.` : NO_IMAGE_LOCATION}
      </p>
      <div className="flex gap-4 mb-2 text-[13px]">
        {item.image_url && <a href={`${API_BASE}${item.image_url}`} target="_blank" rel="noreferrer" className="text-brand underline">Open original image</a>}
        <button type="button" onClick={() => setNativeSize((v) => !v)} className="text-brand underline" aria-pressed={nativeSize}>
          {nativeSize ? 'Fit image' : 'View at original size (1:1)'}
        </button>
        {size && <span>{size.width} × {size.height} recorded pixels</span>}
      </div>
      {failed && <p role="alert">Recorded evidence image could not be loaded.</p>}
      {!item.image_url && <p>Recorded evidence image is not available.</p>}
      <div data-testid="evidence-image-scroll" style={{ overflow: 'auto', maxHeight: '65vh', background: '#f3f4f6', textAlign: 'center' }}>
        {item.image_url && !failed && (
          <div data-testid="evidence-image-frame" style={{ display: 'inline-block', position: 'relative', verticalAlign: 'top', lineHeight: 0, maxWidth: nativeSize ? 'none' : '100%' }}>
            <img src={`${API_BASE}${item.image_url}`} alt={`Recorded inspection evidence: ${item.equipment}`}
              data-testid="evidence-image" onError={() => { setFailed(true); setLoaded(false) }}
              onLoad={(e) => { setSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight }); setLoaded(true) }}
              style={{ display: 'block', width: 'auto', height: 'auto', maxWidth: nativeSize ? 'none' : '100%', maxHeight: nativeSize ? 'none' : '65vh' }} />
            {loaded && marks.length > 0 && (
              <svg data-testid="evidence-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Recorded object marks"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                {marks.map((m, i) => {
                  const geometry = m.bbox
                    ? <rect vectorEffect="non-scaling-stroke" x={m.bbox[0]} y={m.bbox[1]} width={m.bbox[2] - m.bbox[0]} height={m.bbox[3] - m.bbox[1]} />
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
      {marks.length > 1 && <p className="text-[13px] mt-2">This evidence image contains multiple recorded marks; all matching marks are shown.</p>}
      <p className="text-[13px] mt-2">Claim: {item.claim?.field} = {String(item.claim?.value ?? 'unknown')} · Verifier: {item.verifier?.status}{item.verifier?.note ? ` — ${item.verifier.note}` : ''}</p>
    </dialog>
  )
}
