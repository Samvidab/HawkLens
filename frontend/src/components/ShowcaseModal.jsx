import { useEffect } from 'react'
import Co2Tour from './Co2Tour'
import { emissions3dOn } from '../lib/co2Tags'

// Tours and identity come only from GET /portfolio. Equipment uses the same building ID as the investigation page.
export default function ShowcaseModal({ building, onClose }) {
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) onClose() }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
      <button className="absolute inset-0" aria-label="Close tour backdrop" onClick={onClose} />
      <section role="dialog" aria-modal="true" aria-label={`Tour of ${building.name || building.building_id}`}
        className="relative w-[90vw] max-w-[1200px] h-[80vh] bg-white rounded-lg overflow-hidden flex flex-col shadow-xl">
        <header className="flex items-center justify-between px-5 h-[65px] shrink-0 border-b border-line">
          <div><h2 className="font-medium text-ink">{building.name || 'Name not available'}</h2><p className="text-muted text-[12px]">{building.address || 'Address not available'}</p></div>
          <div className="flex gap-5 items-center">
            {building.showcase_url && <a href={building.showcase_url} target="_blank" rel="noreferrer" className="text-brand text-[13px] underline">Open in Matterport ↗</a>}
            <button aria-label="Close tour" onClick={onClose} className="text-ink text-[24px]">×</button>
          </div>
        </header>
        <div className="relative flex-1 min-h-0">
          {emissions3dOn() ? <Co2Tour key={building.building_id} buildingId={building.building_id} />
            : building.showcase_url ? <iframe title={`Matterport tour of ${building.name}`} src={building.showcase_url} className="w-full h-full" allow="fullscreen; xr-spatial-tracking" allowFullScreen />
              : <p className="p-5 text-muted">Tour not available.</p>}
        </div>
        <p className="px-5 py-2 text-muted text-[11px]">Inspection markers indicate where photos were taken; fixture coordinates are unverified.</p>
      </section>
    </div>
  )
}
