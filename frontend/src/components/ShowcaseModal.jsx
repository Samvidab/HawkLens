import { showcaseSrc } from '../lib/api'

// Full-frame overlay that embeds the interactive Matterport Showcase tour for one
// model. Click the backdrop or the close button to dismiss.
export default function ShowcaseModal({ property, onClose }) {
  if (!property) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(34,42,49,0.6)] p-6">
      <button
        type="button"
        aria-label="Close tour"
        onClick={onClose}
        className="absolute inset-0 w-full h-full cursor-default"
      />
      <div className="relative w-[90vw] max-w-[1200px] h-[80vh] bg-white rounded-[10px] overflow-hidden shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-5 h-[56px] border-b border-line shrink-0">
          <div className="min-w-0">
            <p className="font-medium text-ink text-[15px] truncate">{property.name || property.id}</p>
            {property.address && (
              <p className="text-muted text-[12px] truncate">{property.address}</p>
            )}
          </div>
          <div className="flex items-center gap-4">
            <a
              href={property.show_url}
              target="_blank"
              rel="noreferrer"
              className="text-brand text-[13px] font-medium hover:underline"
            >
              Open in Matterport ↗
            </a>
            <button
              type="button"
              onClick={onClose}
              className="text-muted text-[20px] leading-none hover:text-ink"
            >
              ×
            </button>
          </div>
        </div>
        <iframe
          title={`Matterport tour of ${property.name || property.id}`}
          src={showcaseSrc(property.id)}
          className="flex-1 w-full"
          frameBorder="0"
          allow="xr-spatial-tracking; fullscreen"
          allowFullScreen
        />
      </div>
    </div>
  )
}
