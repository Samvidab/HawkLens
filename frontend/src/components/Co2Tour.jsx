// Verified CO2 highlighting for a building's Matterport tour (VITE_EMISSIONS_3D). Used by ShowcaseModal.
// Tour behaviour from the Codex 3D work (codex-3d-work 229f721), adapted to main's modal and VITE_API_URL.
//
// <Co2Highlight modelId={property.id}>{the plain iframe}</Co2Highlight>
//   - the model id is not one of the scans our agents surveyed, or it has no verified items, or the feature is off / the
//     backend has no /co2_equipment -> renders `children` unchanged: no markers, no list, nothing invented;
//   - matched -> the tour through the Showcase SDK with one observation marker ("Photo taken here") per verified item, on
//     the sweep where its evidence was recorded, and beside it the list of those items. Selecting an item (in the list or
//     its marker in the tour) flies to that sweep and turns to the evidence face (ceiling or level). "Inspection Close-Up"
//     / "View evidence" opens the original recorded image with the recorded object outlines (InspectionEvidence).
//     If the SDK cannot start (no key, error) the plain iframe is shown and the list stays, read-only.
// Everything comes from GET /co2_equipment; nothing is computed here. Fixture 3D positions are not recorded, so no marker
// claims to sit on a fixture.
import { useEffect, useRef, useState } from 'react'
import { emissions3dOn, loadCo2Models, ourApiBase } from '../lib/co2Api'
import { KIND, OBSERVATION, sdkKey, tagPlan } from '../lib/co2Tags'
import InspectionEvidence from './InspectionEvidence'
import './Co2Tour.css'

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

export function Co2List({ items, placed, focus, onPick, onEvidence, note, canMove }) {
  const base = ourApiBase()
  return (
    <div data-testid="co2-panel" className="h-full overflow-y-auto p-3 text-[11px] leading-[16px] bg-white">
      <p className="font-semibold text-ink text-[13px] mb-1">Verified CO₂ sources in this scan</p>
      {canMove && <p className="text-muted mb-2">Click an item to go to where it was seen.</p>}
      <ul className="space-y-1">
        {items.map((it, i) => {
          const movable = canMove && placed.has(i)
          const active = focus?.index === i
          return (
            <li key={`${it.claim?.claim_id}-${i}`} data-co2-item={it.kind} data-index={i}>
              <button type="button" disabled={!movable} onClick={() => onPick(i)} data-testid={`co2-item-${i}`}
                className={`co2-item w-full text-left flex gap-2 rounded px-1 py-1 ${movable ? 'co2-item-movable cursor-pointer' : 'cursor-default'} ${active ? 'co2-item-active' : ''}`}>
                <span className="mt-[3px] inline-block w-[10px] h-[10px] rounded-full shrink-0" style={{ background: KIND[it.kind]?.css }} />
                <span>
                  <span className="text-ink">{it.equipment} seen (verified)</span>
                  <span className="block text-muted">
                    {KIND[it.kind]?.name} · {placed.has(i) ? OBSERVATION : 'not located in the tour'}
                    {active && focus.state === 'moving' ? ' · moving…' : ''}
                  </span>
                </span>
              </button>
              {it.image_url && (
                <span className="ml-[22px] flex gap-3">
                  <button type="button" className="text-brand underline" onClick={() => onEvidence(i)} data-testid={`co2-evidence-${i}`}>View evidence</button>
                  <a className="text-brand underline" href={`${base}${it.image_url}`} target="_blank" rel="noreferrer">panorama</a>
                </span>
              )}
            </li>
          )
        })}
      </ul>
      {note && <p className="mt-2 text-muted" data-testid="co2-note">{note}</p>}
    </div>
  )
}

export function Co2Tour({ data, modelId, plain }) {
  const [status, setStatus] = useState('loading') // loading | ready | failed | no-key
  const [placed, setPlaced] = useState(new Set())
  const [tagIds, setTagIds] = useState(0) // markers the SDK confirmed (ids returned by Tag.add)
  const [focus, setFocus] = useState(null) // { index, state: 'moving'|'open'|'failed' }
  const [view, setView] = useState({ sweep: null, docked: null }) // what the tour reports: current sweep, open tag
  const [evidenceIndex, setEvidenceIndex] = useState(null)
  const [pose, setPose] = useState(null) // the camera rotation the tour reports (read-only)
  const box = useRef(null)
  const sdkRef = useRef(null)
  const targetsRef = useRef(new Map()) // item index -> { sweepId, rotation, tagId }
  const currentRef = useRef(null) // the sweep the tour reports
  const pickRef = useRef(null)
  const movingRef = useRef(false)
  const key = sdkKey()
  const base = ourApiBase()

  useEffect(() => {
    if (!key) { setStatus('no-key'); return undefined }
    let cancelled = false
    const subs = []
    // each attempt gets its own mount node: an SDK iframe arriving after this attempt was cancelled (React StrictMode
    // runs effects twice in dev) lands in a detached node instead of next to the live tour
    const mount = document.createElement('div')
    mount.style.cssText = 'position:absolute;inset:0'
    box.current?.appendChild(mount)
    setStatus('loading'); setPlaced(new Set()); setTagIds(0); setFocus(null); setView({ sweep: null, docked: null }); setEvidenceIndex(null)
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
        // markers only in the scan the evidence was recorded in (the modal shows model `modelId`; data.model_id is the scan)
        if (modelId === data.model_id && data.items?.length) {
          const sweeps = await loadSweeps(sdk)
          if (cancelled) return
          const { descriptors, placed: p, targets } = tagPlan(data.items, sweeps, base)
          if (descriptors.length) ids = (await sdk.Tag.add(...descriptors)) || []
          // opening a marker must not fly the camera to the floor marker: selection moves to the observation sweep itself
          await Promise.all(ids.map((id) => sdk.Tag.allowAction?.(id, { opening: true, navigating: false, docking: true, sharing: false })?.catch?.(() => {})))
          done = p
          if (ids.length === targets.length) targets.forEach((t, k) => targetsRef.current.set(t.index, { sweepId: t.sweepId, rotation: t.rotation, tagId: ids[k] }))
        }
        if (cancelled) return
        try { // what the tour itself reports, so the page (and tests) see the move and the open marker
          subs.push(sdk.Sweep.current.subscribe((s) => { if (s?.id || s?.sid) { currentRef.current = s.id || s.sid; setView((v) => ({ ...v, sweep: s.id || s.sid })) } }))
          let selected = null
          subs.push(sdk.Tag.openTags.subscribe((o) => {
            const id = o?.docked || [...(o?.selected || [])][0] || null
            setView((v) => ({ ...v, docked: id }))
            // a marker selected in the tour itself: go to its observation view, like a list click
            if (id && id !== selected && !movingRef.current) {
              const entry = [...targetsRef.current].find(([, t]) => t.tagId === id)
              if (entry) pickRef.current?.(entry[0])
            }
            selected = id
          }))
          const poseSub = sdk.Camera?.pose?.subscribe?.((p) => setPose(p?.rotation ? { x: Math.round(p.rotation.x), y: Math.round(p.rotation.y) } : null))
          if (poseSub) subs.push(poseSub)
        } catch { /* observables unavailable: the move still works */ }
        sdkRef.current = sdk
        setPlaced(ids.length === done.size ? done : new Set()); setTagIds(ids.length); setStatus('ready')
      } catch (e) { clearTimeout(timer); fail(e) }
    })()
    return () => {
      cancelled = true; clearTimeout(timer); sdkRef.current = null
      subs.forEach((s) => { try { s.cancel() } catch { /* ignore */ } })
      mount.remove()
    }
  }, [data, modelId, key, base])

  /** Fly to the sweep where item `i`'s evidence was recorded, turn to its evidence face, and open its marker. */
  const pick = async (i) => {
    const sdk = sdkRef.current
    const t = targetsRef.current.get(i)
    if (!sdk || !t || movingRef.current) return
    movingRef.current = true
    setFocus({ index: i, state: 'moving' })
    try {
      const go = () => sdk.Sweep.moveTo(t.sweepId, { transition: sdk.Sweep.Transition?.FLY ?? 'transition.fly', transitionTime: 1500, rotation: t.rotation })
      await go()
      // open the marker's billboard in place (docking makes the tour fly to a viewpoint of the marker, away from the sweep)
      try { await sdk.Tag.open(t.tagId, { force: true }) } catch { await sdk.Tag.dock(t.tagId, { force: true }) }
      // if the tour still moved away from where the item was seen, come back
      await new Promise((r) => setTimeout(r, 1200))
      if (currentRef.current && currentRef.current !== t.sweepId) await go()
      // opening a billboard can also change orientation without changing sweeps
      if (sdk.Camera?.setRotation) await sdk.Camera.setRotation(t.rotation)
      setFocus({ index: i, state: 'open' })
    } catch (e) {
      console.warn('Matterport move failed:', e?.message || e)
      setFocus({ index: i, state: 'failed' })
    } finally { movingRef.current = false }
  }
  pickRef.current = pick

  const note = {
    loading: 'Loading the 3D tour…',
    'no-key': 'Markers unavailable: the Matterport SDK key is not configured (the plain tour is shown instead).',
    failed: 'Markers unavailable: the tour could not be started through the SDK (the plain tour is shown instead).',
    ready: `${tagIds} marker${tagIds === 1 ? '' : 's'} in the tour: ${OBSERVATION}. Fixture positions are not recorded.`,
  }[status]
  const showSdk = status === 'loading' || status === 'ready'
  const focusTarget = focus ? targetsRef.current.get(focus.index) : null

  return (
    <div className="relative flex flex-1 min-h-0" data-testid="co2-tour" data-status={status} data-tags={tagIds}
      data-focus-index={focus?.index ?? ''} data-focus-state={focus?.state ?? ''} data-focus-sweep={focusTarget?.sweepId ?? ''}
      data-focus-tag={focusTarget?.tagId ?? ''} data-current-sweep={view.sweep ?? ''} data-docked-tag={view.docked ?? ''}
      data-camera-rotation={pose ? `${pose.x},${pose.y}` : ''} data-focus-rotation={focusTarget ? `${focusTarget.rotation.x},${Math.round(focusTarget.rotation.y)}` : ''}>
      <div className="relative flex-1 min-w-0 flex flex-col">
        {showSdk && (
          <div className="h-[38px] shrink-0 flex items-center gap-4 px-3 bg-white border-b border-line" aria-label="Inspection views">
            <span className="text-ink text-[12px] font-medium">Matterport 3D View</span>
            <button type="button" disabled={focus?.index == null || !data.items?.[focus.index]?.image_url}
              onClick={() => setEvidenceIndex(focus.index)} className="text-brand text-[12px] underline disabled:text-muted disabled:no-underline">Inspection Close-Up</button>
          </div>
        )}
        <div className="relative flex-1 min-h-0 flex">
          <div ref={box} className={`absolute inset-0 ${showSdk ? '' : 'hidden'}`} data-testid="co2-tour-frame" />
          {!showSdk && plain}
        </div>
      </div>
      <div className="shrink-0 border-l border-line" style={{ width: LIST_W }}>
        <Co2List items={data.items} placed={placed} focus={focus} onPick={pick} onEvidence={setEvidenceIndex} note={note} canMove={status === 'ready'} />
      </div>
      {data.items?.[evidenceIndex] && (
        <InspectionEvidence key={`${modelId}-${evidenceIndex}`} item={data.items[evidenceIndex]} onClose={() => setEvidenceIndex(null)} />
      )}
    </div>
  )
}

export default function Co2Highlight({ modelId, children }) {
  const on = emissions3dOn() && !!ourApiBase()
  const [state, setState] = useState(on ? { loading: true } : { data: null })
  useEffect(() => {
    if (!on) { setState({ data: null }); return undefined }
    let alive = true
    setState({ loading: true })
    loadCo2Models().then((map) => alive && setState({ data: map.get(modelId) || null }))
    return () => { alive = false }
  }, [on, modelId])

  if (!on) return children
  if (state.loading) return <div className="flex-1 bg-white" data-testid="co2-checking" />
  if (!state.data) return children
  return <Co2Tour data={state.data} modelId={modelId} plain={children} />
}
