// The building's Matterport tour through the Showcase SDK, with one tag per observed position of its top-3 CO2 sources.
// No tour, no SDK key, or the SDK fails -> legend only (never fake positions or data). The legend is always shown.
import { useEffect, useRef, useState } from 'react'
import { BASIS_NOTE, emissionSources, modelIdOf, sdkKey, tagDescriptors, tourUrlOf } from '../lib/emissions'

const SDK_TIMEOUT_MS = 25_000

export function EmissionsLegend({ sources, note, className = '' }) {
  return (
    <div data-testid="emissions-legend" className={`rounded-[6px] bg-white/95 shadow-sm p-3 text-[11px] leading-[16px] ${className}`}>
      <p className="font-semibold text-ink text-[12px] mb-1">Top CO₂ sources</p>
      {sources ? (
        <ol className="space-y-1">
          {sources.map((s) => (
            <li key={s.source} data-source={s.source} className="flex gap-2">
              <span className="mt-[3px] inline-block w-[10px] h-[10px] rounded-full shrink-0" style={{ background: s.color.css }} title={s.color.name} />
              <span>
                <span className="text-ink">{s.label}</span>
                <span className="block text-muted">{s.positions.length ? `${s.positions.length} observed location${s.positions.length === 1 ? '' : 's'} in the tour` : 'location not observed'}</span>
              </span>
            </li>
          ))}
        </ol>
      ) : <p className="text-muted" data-testid="emissions-na">Emission sources not available for this building.</p>}
      <p className="mt-2 text-muted">{sources ? `Shares are a ${BASIS_NOTE}.` : ''}{note ? ` ${note}` : ''}</p>
    </div>
  )
}

export default function EmissionsTour({ layout }) {
  const sources = emissionSources(layout)
  const url = tourUrlOf(layout)
  const modelId = url ? modelIdOf(url) : null
  const key = sdkKey()
  const [status, setStatus] = useState(!modelId ? 'no-tour' : !key ? 'no-key' : 'loading')
  const [tags, setTags] = useState(0)
  const box = useRef(null)
  const descriptors = tagDescriptors(sources)
  const descKey = JSON.stringify(descriptors)

  useEffect(() => {
    if (!modelId || !key) return undefined
    let cancelled = false
    // each attempt gets its own mount node: an SDK iframe that arrives after this attempt was cancelled (React StrictMode
    // runs effects twice in dev) lands in a detached node instead of next to the live tour
    const mount = document.createElement('div')
    mount.style.cssText = 'position:absolute;inset:0'
    box.current?.appendChild(mount)
    setStatus('loading'); setTags(0)
    const timer = setTimeout(() => { if (!cancelled) { cancelled = true; mount.remove(); setStatus('failed') } }, SDK_TIMEOUT_MS)
    ;(async () => {
      try {
        const { setupSdk } = await import('@matterport/sdk')
        const sdk = await setupSdk(key, { space: modelId, container: mount, iframeAttributes: { width: '100%', height: '100%', title: 'Matterport 3D tour' }, iframeQueryParams: { qs: 1 } })
        if (cancelled) return
        const ids = descriptors.length ? await sdk.Tag.add(...descriptors) : []
        if (cancelled) return
        clearTimeout(timer)
        setTags(ids.length); setStatus('ready')
      } catch (e) {
        if (cancelled) return
        clearTimeout(timer); cancelled = true
        mount.remove() // SDK failed: legend only, no half-loaded tour
        console.warn('Matterport SDK failed:', e?.message || e)
        setStatus('failed')
      }
    })()
    return () => { cancelled = true; clearTimeout(timer); mount.remove() }
  }, [modelId, descKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const note = {
    'no-tour': 'No 3D tour for this building.',
    'no-key': 'The Matterport SDK key is not configured, so the tour is not shown.',
    loading: 'Loading the 3D tour…',
    failed: 'The 3D tour could not be loaded.',
    ready: sources ? `${tags} tag${tags === 1 ? '' : 's'} placed where the sources were observed.` : 'No sources to tag.',
  }[status]
  const showTour = status === 'loading' || status === 'ready'

  return (
    <div className="absolute inset-0" data-testid="emissions-3d" data-status={status} data-tags={tags}>
      <div ref={box} className={`absolute inset-0 ${showTour ? '' : 'hidden'}`} data-testid="emissions-tour" />
      <EmissionsLegend sources={sources} note={note} className="absolute left-[16px] bottom-[16px] w-[360px] max-h-[300px] overflow-y-auto z-10" />
    </div>
  )
}
