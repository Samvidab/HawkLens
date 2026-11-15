// The building's Matterport tour (Showcase SDK) with one tag per verified CO2-emitting item seen in it, and beside it the
// list of those items. Clicking an item moves the tour to the panorama where it was seen (Sweep.moveTo) and opens its tag
// (docked), so the tags can be seen without walking. No tour -> list only. SDK fails -> list only (the half-loaded tour is
// removed). No items -> the tour plus "No verified CO2 sources located in this scan". Everything comes from
// GET /co2_equipment; nothing is computed here.
import { useEffect, useRef, useState } from 'react'
import { API_BASE, getCo2Equipment } from '../lib/api'
import InspectionEvidence from './InspectionEvidence'
import { KIND, NO_SOURCES, modelIdOf, sdkKey, tagPlan } from '../lib/co2Tags'

const SDK_TIMEOUT_MS = 30_000
const SWEEPS_TIMEOUT_MS = 30_000
const LIST_W = 300 // px: the list column beside the tour

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

export function Co2List({ data, placed, focus, onPick, onEvidence, note, canMove }) {
  const items = data?.items || []
  return (
    <div data-testid="co2-panel" className="h-full overflow-y-auto p-3 text-[11px] leading-[16px] bg-white">
      <p className="font-semibold text-ink text-[13px] mb-1">Verified CO₂ sources in this scan</p>
      {data === undefined && <p className="text-muted">Loading…</p>}
      {data === null && <p className="text-muted">Verified equipment not available.</p>}
      {data && !items.length && <p className="text-muted" data-testid="co2-none">{NO_SOURCES}</p>}
      {items.length > 0 && canMove && <p className="text-muted mb-2">Click an item to go to where it was seen.</p>}
      {items.length > 0 && (
        <ul className="space-y-1">
          {items.map((it, i) => {
            const movable = canMove && placed?.has(i)
            const active = focus?.index === i
            return (
              <li key={`${it.claim?.claim_id}-${i}`} data-co2-item={it.kind} data-index={i}>
                <button type="button" disabled={!movable} onClick={() => onPick(i)} data-testid={`co2-item-${i}`}
                  className={`w-full text-left flex gap-2 rounded px-1 py-1 ${movable ? 'hover:bg-[#f1f4ed] cursor-pointer' : 'cursor-default'} ${active ? 'bg-[#edf3e6]' : ''}`}>
                  <span className="mt-[3px] inline-block w-[10px] h-[10px] rounded-full shrink-0" style={{ background: KIND[it.kind]?.css }} />
                  <span>
                    <span className="text-ink">{it.equipment} seen (verified)</span>
                    <span className="block text-muted">
                      {KIND[it.kind]?.name} · {placed?.has(i) ? 'Photo taken here' : 'not located in the tour'}
                      {active && focus.state === 'moving' ? ' · moving…' : ''}
                    </span>
                  </span>
                </button>
                {it.image_url && (
                  <a className="ml-[22px] text-brand underline" href={`${API_BASE}${it.image_url}`} target="_blank" rel="noreferrer">panorama</a>
                )}
                {it.image_url && <button type="button" className="ml-[22px] text-brand underline" onClick={() => onEvidence?.(i)} data-testid={`co2-evidence-${i}`}>View evidence</button>}
              </li>
            )
          })}
        </ul>
      )}
      {note && <p className="mt-2 text-muted" data-testid="co2-note">{note}</p>}
    </div>
  )
}

export default function Co2Tour({ buildingId }) {
  const [evidenceIndex, setEvidenceIndex] = useState(null)
  const [camera, setCamera] = useState({ rotation: null, zoom: null })
  const [data, setData] = useState(undefined) // undefined loading, null failed
  const [status, setStatus] = useState('loading-data')
  const [placed, setPlaced] = useState(new Set())
  const [tagIds, setTagIds] = useState(0) // tags the SDK confirmed (ids returned by Tag.add)
  const [focus, setFocus] = useState(null) // { index, state: 'moving'|'open'|'failed' }
  const [view, setView] = useState({ sweep: null, docked: null }) // what the tour reports: current sweep, docked tag
  const box = useRef(null)
  const sdkRef = useRef(null)
  const targetsRef = useRef(new Map()) // item index -> { sweepId, tagId }
  const currentRef = useRef(null) // the sweep the tour reports
  const pickRef = useRef(null)
  const movingRef = useRef(false)
  const key = sdkKey()

  useEffect(() => {
    let alive = true
    setEvidenceIndex(null); setData(undefined); setStatus('loading-data'); setPlaced(new Set()); setFocus(null)
    getCo2Equipment(buildingId).then((d) => alive && setData(d)).catch(() => alive && (setData(null), setStatus('no-data')))
    return () => { alive = false }
  }, [buildingId])

  const modelId = data?.tour_url ? modelIdOf(data.tour_url) : null
  useEffect(() => {
    if (data === undefined) return undefined
    if (!modelId) { setStatus('no-tour'); return undefined }
    if (!key) { setStatus('no-key'); return undefined }
    let cancelled = false
    const subs = []
    // each attempt gets its own mount node: an SDK iframe arriving after this attempt was cancelled (React StrictMode
    // runs effects twice in dev) lands in a detached node instead of next to the live tour
    const mount = document.createElement('div')
    mount.style.cssText = 'position:absolute;inset:0'
    box.current?.appendChild(mount)
    setStatus('loading'); setPlaced(new Set()); setTagIds(0); setFocus(null); setView({ sweep: null, docked: null })
    sdkRef.current = null; targetsRef.current = new Map()
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
          const { descriptors, placed: p, targets } = tagPlan(data.items, sweeps, API_BASE)
          if (descriptors.length) ids = (await sdk.Tag.add(...descriptors)) || []
          // opening a tag must not fly the camera elsewhere: the list click has already moved to where it was seen
          await Promise.all(ids.map((id) => sdk.Tag.allowAction?.(id, { opening: true, navigating: false, docking: true, sharing: false })?.catch?.(() => {})))
          done = p
          if (ids.length === targets.length) targets.forEach((t, k) => targetsRef.current.set(t.index, { sweepId: t.sweepId, rotation: t.rotation, tagId: ids[k] }))
        }
        if (cancelled) return
        try { // what the tour itself reports, so the page (and tests) see the move and the open tag
          subs.push(sdk.Sweep.current.subscribe((s) => { if (s?.id || s?.sid) { currentRef.current = s.id || s.sid; setView((v) => ({ ...v, sweep: s.id || s.sid })) } }))
          let selected = null
          subs.push(sdk.Tag.openTags.subscribe((o) => {
            const id = o?.docked || [...(o?.selected || [])][0] || null
            setView((v) => ({ ...v, docked: id }))
            if (id && id !== selected && !movingRef.current) {
              const entry = [...targetsRef.current].find(([, t]) => t.tagId === id)
              if (entry) pickRef.current?.(entry[0])
            }
            selected = id
          }))
        } catch { /* observables unavailable: the move still works */ }
        // Read-only observability: confirms native Showcase controls and state survive close-up switching.
        const poseSub = sdk.Camera?.pose?.subscribe((pose) => setCamera((c) => ({ ...c, rotation: pose.rotation })))
        const zoomSub = sdk.Camera?.zoom?.subscribe((z) => setCamera((c) => ({ ...c, zoom: z.level })))
        if (poseSub) subs.push(poseSub)
        if (zoomSub) subs.push(zoomSub)
        sdkRef.current = sdk
        setPlaced(ids.length === done.size ? done : new Set()); setTagIds(ids.length); setStatus('ready')
      } catch (e) { clearTimeout(timer); fail(e) }
    })()
    return () => {
      cancelled = true; clearTimeout(timer); sdkRef.current = null
      subs.forEach((s) => { try { s.cancel() } catch { /* ignore */ } })
      mount.remove()
    }
  }, [data, modelId, key])

  /** Go to the panorama where item `i` was seen and open its tag. */
  const pick = async (i) => {
    const sdk = sdkRef.current
    const t = targetsRef.current.get(i)
    if (!sdk || !t || movingRef.current) return
    movingRef.current = true
    setFocus({ index: i, state: 'moving' })
    try {
      // Return to the observation panorama; never aim at its floor marker.
      const go = () => sdk.Sweep.moveTo(t.sweepId, { transition: sdk.Sweep.Transition?.FLY ?? 'transition.fly', transitionTime: 1500,
        rotation: t.rotation })
      await go()
      // open the tag's billboard in place (docking it makes the tour fly to a viewpoint of the tag, away from the panorama)
      try { await sdk.Tag.open(t.tagId, { force: true }) } catch { await sdk.Tag.dock(t.tagId, { force: true }) }
      // if the tour still moved away from where the item was seen, come back
      await new Promise((r) => setTimeout(r, 1200))
      if (currentRef.current && currentRef.current !== t.sweepId) await go()
      // Opening a billboard can also change orientation without changing sweeps.
      if (sdk.Camera?.setRotation) await sdk.Camera.setRotation(t.rotation)
      setFocus({ index: i, state: 'open' })
    } catch (e) {
      console.warn('Matterport move failed:', e?.message || e)
      setFocus({ index: i, state: 'failed' })
    } finally { movingRef.current = false }
  }
  pickRef.current = pick

  const note = {
    'loading-data': '',
    'no-data': '',
    'no-tour': 'No 3D tour for this building.',
    'no-key': 'The Matterport SDK key is not configured, so the tour is not shown.',
    loading: 'Loading the 3D tour…',
    failed: 'The 3D tour could not be loaded.',
    ready: data?.items?.length
      ? (data.tags_in_tour ? `${tagIds} tag${tagIds === 1 ? '' : 's'} in the tour, Photo taken here markers; fixture positions are unverified.` : 'This tour is a different scan from the one surveyed, so no tags are placed.')
      : '',
  }[status]
  const showTour = status === 'loading' || status === 'ready'
  const focusTarget = focus ? targetsRef.current.get(focus.index) : null

  return (
    <div className="absolute inset-0" data-testid="co2-tour" data-status={status} data-tags={tagIds}
      data-camera-rotation={JSON.stringify(camera.rotation)} data-camera-zoom={camera.zoom ?? ''}
      data-focus-index={focus?.index ?? ''} data-focus-state={focus?.state ?? ''} data-focus-sweep={focusTarget?.sweepId ?? ''}
      data-focus-tag={focusTarget?.tagId ?? ''} data-current-sweep={view.sweep ?? ''} data-docked-tag={view.docked ?? ''}>
      <div className="absolute top-0 left-0 right-0 h-[42px] flex items-center gap-4 px-3 bg-white border-b border-line z-10" aria-label="Inspection views">
        <button type="button" aria-pressed={evidenceIndex === null} onClick={() => setEvidenceIndex(null)} className="text-brand text-[12px] underline">Matterport 3D View</button>
        <button type="button" disabled={focus?.index == null || !data?.items?.[focus.index]?.image_url}
          onClick={() => setEvidenceIndex(focus.index)} className="text-brand text-[12px] underline disabled:text-muted disabled:no-underline">Inspection Close-Up</button>
      </div>
      <div ref={box} className={`absolute left-0 top-[42px] bottom-0 ${showTour ? '' : 'hidden'}`} style={{ right: LIST_W }} data-testid="co2-tour-frame" />
      {!showTour && note && <p className="absolute left-[22px] top-[60px] text-muted text-[13px]" style={{ right: LIST_W + 20 }} data-testid="co2-note">{note}</p>}
      <div className="absolute right-0 top-[42px] bottom-0 border-l border-line" style={{ width: LIST_W }}>
        <Co2List data={data} placed={placed} focus={focus} onPick={pick} onEvidence={setEvidenceIndex} note={showTour ? note : ''} canMove={status === 'ready'} />
      </div>
      {data?.items?.[evidenceIndex] && <InspectionEvidence key={`${buildingId}-${evidenceIndex}`} item={data.items[evidenceIndex]} onClose={() => setEvidenceIndex(null)} />}
    </div>
  )
}
