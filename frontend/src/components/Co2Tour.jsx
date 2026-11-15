// The building's Matterport tour (Showcase SDK) with one tag per verified CO2-emitting item seen in it, and a panel that
// lists them. No tour -> panel only. SDK fails -> panel only (the half-loaded tour is removed). No items -> the tour plus
// "No verified CO2 sources located in this scan". Nothing here is computed; everything comes from GET /co2_equipment.
import { useEffect, useRef, useState } from 'react'
import { API_BASE, getCo2Equipment } from '../lib/api'
import { KIND, NO_SOURCES, modelIdOf, sdkKey, tagPlan } from '../lib/co2Tags'

const SDK_TIMEOUT_MS = 30_000
const SWEEPS_TIMEOUT_MS = 30_000

/** The sweeps of the loaded tour (empty array if they never arrive). */
function loadSweeps(sdk) {
  return new Promise((resolve) => {
    let sub = null
    const done = (list) => { clearTimeout(t); try { sub?.cancel() } catch { /* ignore */ } resolve(list) }
    const t = setTimeout(() => done([]), SWEEPS_TIMEOUT_MS)
    sub = sdk.Sweep.data.subscribe({
      onCollectionUpdated: (c) => { const list = Object.entries(c || {}).map(([id, s]) => ({ ...s, id: s.id || id })); if (list.length) done(list) },
    })
  })
}

export function Co2Panel({ data, placed, note, className = '' }) {
  const items = data?.items || []
  return (
    <div data-testid="co2-panel" className={`rounded-[6px] bg-white/95 shadow-sm p-3 text-[11px] leading-[16px] ${className}`}>
      <p className="font-semibold text-ink text-[12px] mb-1">Verified CO₂ sources in this scan</p>
      {data === undefined && <p className="text-muted">Loading…</p>}
      {data === null && <p className="text-muted">Verified equipment not available.</p>}
      {data && !items.length && <p className="text-muted" data-testid="co2-none">{NO_SOURCES}</p>}
      {items.length > 0 && (
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li key={`${it.claim?.claim_id}-${i}`} data-co2-item={it.kind} className="flex gap-2">
              <span className="mt-[3px] inline-block w-[10px] h-[10px] rounded-full shrink-0" style={{ background: KIND[it.kind]?.css }} />
              <span>
                <span className="text-ink">{it.equipment} seen (verified)</span>
                <span className="block text-muted">
                  {KIND[it.kind]?.name} · {placed?.has(i) ? 'tagged in the tour' : 'not located in the tour'}
                  {it.image_url && <> · <a className="text-brand underline" href={`${API_BASE}${it.image_url}`} target="_blank" rel="noreferrer">panorama</a></>}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {note && <p className="mt-2 text-muted" data-testid="co2-note">{note}</p>}
    </div>
  )
}

export default function Co2Tour({ buildingId }) {
  const [data, setData] = useState(undefined) // undefined loading, null failed
  const [status, setStatus] = useState('loading-data')
  const [placed, setPlaced] = useState(new Set())
  const [tagIds, setTagIds] = useState(0) // tags the SDK confirmed (ids returned by Tag.add)
  const box = useRef(null)
  const key = sdkKey()

  useEffect(() => {
    let alive = true
    setData(undefined); setStatus('loading-data'); setPlaced(new Set())
    getCo2Equipment(buildingId).then((d) => alive && setData(d)).catch(() => alive && (setData(null), setStatus('no-data')))
    return () => { alive = false }
  }, [buildingId])

  const modelId = data?.tour_url ? modelIdOf(data.tour_url) : null
  useEffect(() => {
    if (data === undefined) return undefined
    if (!modelId) { setStatus('no-tour'); return undefined }
    if (!key) { setStatus('no-key'); return undefined }
    let cancelled = false
    // each attempt gets its own mount node: an SDK iframe arriving after this attempt was cancelled (React StrictMode
    // runs effects twice in dev) lands in a detached node instead of next to the live tour
    const mount = document.createElement('div')
    mount.style.cssText = 'position:absolute;inset:0'
    box.current?.appendChild(mount)
    setStatus('loading'); setPlaced(new Set()); setTagIds(0)
    const fail = (e) => {
      if (cancelled) return
      cancelled = true; mount.remove()
      if (e) console.warn('Matterport SDK failed:', e?.message || e)
      setStatus('failed')
    }
    const timer = setTimeout(() => fail(new Error('timeout')), SDK_TIMEOUT_MS)
    ;(async () => {
      try {
        const { setupSdk } = await import('@matterport/sdk')
        const sdk = await setupSdk(key, { space: modelId, container: mount, iframeAttributes: { width: '100%', height: '100%', title: 'Matterport 3D tour' }, iframeQueryParams: { qs: 1, play: 1 } })
        if (cancelled) return
        clearTimeout(timer)
        let done = new Set()
        let ids = []
        if (data.tags_in_tour && data.items?.length) {
          const sweeps = await loadSweeps(sdk)
          if (cancelled) return
          const { descriptors, placed: p } = tagPlan(data.items, sweeps, API_BASE)
          if (descriptors.length) ids = (await sdk.Tag.add(...descriptors)) || []
          done = p
        }
        if (cancelled) return
        setPlaced(ids.length === done.size ? done : new Set()); setTagIds(ids.length); setStatus('ready')
      } catch (e) { clearTimeout(timer); fail(e) }
    })()
    return () => { cancelled = true; clearTimeout(timer); mount.remove() }
  }, [data, modelId, key])

  const note = {
    'loading-data': '',
    'no-data': '',
    'no-tour': 'No 3D tour for this building.',
    'no-key': 'The Matterport SDK key is not configured, so the tour is not shown.',
    loading: 'Loading the 3D tour…',
    failed: 'The 3D tour could not be loaded.',
    ready: data?.items?.length
      ? (data.tags_in_tour ? `${tagIds} tag${tagIds === 1 ? '' : 's'} in the tour, each at the panorama where it was seen (walk the tour to see them).` : 'This tour is a different scan from the one surveyed, so no tags are placed.')
      : '',
  }[status]
  const showTour = status === 'loading' || status === 'ready'

  return (
    <div className="absolute inset-0" data-testid="co2-tour" data-status={status} data-tags={tagIds}>
      <div ref={box} className={`absolute inset-0 ${showTour ? '' : 'hidden'}`} data-testid="co2-tour-frame" />
      <Co2Panel data={data} placed={placed} note={note} className="absolute left-[16px] bottom-[16px] w-[340px] max-h-[190px] overflow-y-auto z-10" />
    </div>
  )
}
