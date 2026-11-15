import { useCallback, useEffect, useRef, useState } from 'react'
import Page from '../components/Page'
import ShowcaseModal from '../components/ShowcaseModal'
import { assetUrl, fetchProperties } from '../lib/api'
import { useGo, useGoal } from '../lib/ui'
import {
  BUDGET_K,
  SLIDER_WIDTH,
  TARGET_MAX,
  TARGET_MIN,
  deriveModel,
} from '../lib/model'

export default function Portfolio() {
  const go = useGo()
  // Shared, persisted target (survives navigation + reload; drives every page).
  const { target, setTarget } = useGoal()
  const model = deriveModel(target)
  const setTargetClamped = setTarget

  // Real Matterport properties from the backend.
  const [properties, setProperties] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [tourProperty, setTourProperty] = useState(null)

  useEffect(() => {
    let alive = true
    fetchProperties({ limit: 24 })
      .then((d) => alive && setProperties(d.results || []))
      .catch((e) => alive && setLoadError(e.message))
    return () => {
      alive = false
    }
  }, [])

  return (
    <Page active="portfolio">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        Houston portfolio
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        {properties.length
          ? `${properties.length} buildings · Live Matterport scans`
          : 'Loading buildings…'}
      </p>
      <LinkArrow className="left-[1055px] top-[154px]" onClick={() => go('/start-survey')}>
        Run survey
      </LinkArrow>
      <LinkArrow className="left-[1220px] top-[154px]" onClick={() => go('/building')}>
        Building details
      </LinkArrow>

      <PortfolioModel
        properties={properties}
        loadError={loadError}
        onOpenTour={(p) => setTourProperty(p)}
      />

      {tourProperty && (
        <ShowcaseModal property={tourProperty} onClose={() => setTourProperty(null)} />
      )}

      <CarbonGoal
        target={target}
        model={model}
        onChangeTarget={setTargetClamped}
        onStep={(delta) => setTargetClamped(target + delta)}
        onEdit={() => go('/plan-preferences')}
        onReview={() => go('/plan')}
        onCheckGap={() => go('/risk-and-target')}
      />

      <h2 className="absolute left-[56px] top-[704px] whitespace-nowrap font-semibold text-ink text-[20px]">
        Recommended upgrades
      </h2>
      <p className="absolute left-[56px] top-[738px] whitespace-nowrap text-muted text-[13px]">
        18 upgrades across 8 buildings
      </p>
      <LinkArrow className="left-[1208px] top-[715px]" onClick={() => go('/plan')}>
        See costs &amp; evidence
      </LinkArrow>

      <UpgradeSummary onOpen={() => go('/plan')} />

      <p className="absolute left-[56px] top-[947px] whitespace-nowrap text-muted text-[11px]">
        Interactive demo · Illustrative calculations, not a live optimizer
      </p>
      <p className="absolute left-[1090px] top-[947px] whitespace-nowrap text-muted text-[11px]">
        Baseline sample: {model.confidence}% target confidence
      </p>
    </Page>
  )
}

function LinkArrow({ className = '', children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`absolute whitespace-nowrap font-medium text-brand text-[13px] hover:underline ${className}`}
    >
      {children}&nbsp;&nbsp;→
    </button>
  )
}

function PortfolioModel({ properties, loadError, onOpenTour }) {
  return (
    <section className="absolute left-[56px] top-[231px] w-[848px] h-[420px] overflow-hidden rounded-[8px] bg-model">
      <p className="absolute left-[23px] top-[21px] whitespace-nowrap font-medium text-ink text-[15px]">
        Your buildings
      </p>
      <p className="absolute left-[23px] top-[46px] whitespace-nowrap text-muted text-[13px]">
        Real Matterport scans — expand a building to walk through it.
      </p>

      {/* Scrollable grid of real building cards (replaces the schematic green blocks) */}
      <div className="absolute left-[23px] right-[23px] top-[74px] bottom-[42px] overflow-y-auto pr-1">
        {loadError && (
          <p className="text-[13px] text-[#b4532f]">
            Couldn&rsquo;t load buildings ({loadError}). Is the backend running on :8000?
          </p>
        )}
        {!loadError && properties.length === 0 && (
          <p className="text-muted text-[13px]">Loading buildings…</p>
        )}
        <div className="grid grid-cols-3 gap-3">
          {properties.map((p) => (
            <BuildingCard key={p.id} property={p} onOpenTour={onOpenTour} />
          ))}
        </div>
      </div>

      <p className="absolute left-[23px] bottom-[14px] whitespace-nowrap text-muted text-[11px]">
        Imagery &amp; 3D tours via Matterport (licensed from CoStar)
      </p>
    </section>
  )
}

function BuildingCard({ property, onOpenTour }) {
  return (
    <button
      type="button"
      onClick={() => onOpenTour(property)}
      className="group relative block w-full overflow-hidden rounded-[6px] bg-white text-left shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="relative w-full aspect-[4/3] bg-line overflow-hidden">
        {property.thumbnail_url ? (
          <img
            src={assetUrl(property.thumbnail_url)}
            alt={property.name || property.id}
            loading="lazy"
            className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted text-[12px]">
            no image
          </div>
        )}
        {/* Expand affordance */}
        <span className="absolute right-2 top-2 rounded-[4px] bg-white/90 px-2 py-1 text-[11px] font-medium text-brand opacity-0 group-hover:opacity-100 transition-opacity">
          Expand ↗
        </span>
      </div>
      <div className="px-2.5 py-2">
        <p className="truncate text-[13px] font-medium text-ink">{property.name || property.id}</p>
        <p className="truncate text-[11px] text-muted">{property.address || 'Houston, TX'}</p>
      </div>
    </button>
  )
}

function CarbonGoal({ target, model, onChangeTarget, onStep, onEdit, onReview, onCheckGap }) {
  return (
    <section className="absolute left-[944px] top-[231px] w-[440px] h-[420px] overflow-hidden">
      <div className="absolute left-0 top-0 w-px h-[420px] bg-line" />

      <p className="absolute left-[32px] top-[8px] whitespace-nowrap font-medium text-ink text-[16px]">
        Your carbon goal
      </p>

      <p className="absolute left-[32px] top-[45px] whitespace-nowrap font-semibold text-ink text-[36px] tabular-nums">
        {target}%
      </p>
      <p className="absolute left-[114px] top-[65px] whitespace-nowrap text-muted text-[14px]">
        reduction
      </p>

      <button
        type="button"
        aria-label="Decrease target by 5 percent"
        onClick={() => onStep(-5)}
        disabled={target <= TARGET_MIN}
        className="absolute left-[252px] top-[37px] w-[40px] h-[44px] flex items-center justify-center text-brand text-[22px] font-medium rounded hover:bg-brand/5 disabled:opacity-30 disabled:hover:bg-transparent"
      >
        −
      </button>
      <button
        type="button"
        aria-label="Increase target by 5 percent"
        onClick={() => onStep(5)}
        disabled={target >= TARGET_MAX}
        className="absolute left-[374px] top-[37px] w-[40px] h-[44px] flex items-center justify-center text-brand text-[22px] font-medium rounded hover:bg-brand/5 disabled:opacity-30 disabled:hover:bg-transparent"
      >
        +
      </button>

      <TargetSlider target={target} onChange={onChangeTarget} />

      <p className="absolute left-[32px] top-[125px] whitespace-nowrap text-muted text-[11px]">0%</p>
      <p className="absolute left-[384px] top-[125px] whitespace-nowrap text-muted text-[11px]">60%</p>

      <p className="absolute left-[32px] top-[165px] whitespace-nowrap text-muted text-[13px]">
        Budget ${BUDGET_K}k · Balanced risk
      </p>
      <button
        type="button"
        onClick={onEdit}
        className="absolute left-[382px] top-[165px] whitespace-nowrap font-medium text-brand text-[13px] hover:underline"
      >
        Edit
      </button>

      <div className="absolute left-[32px] top-[203px] w-[376px] h-px bg-line" />

      <p
        className={`absolute left-[32px] top-[224px] whitespace-nowrap font-semibold text-[20px] ${
          model.covered ? 'text-ink' : 'text-[#b4532f]'
        }`}
      >
        {model.statusLabel}
      </p>
      <p className="absolute left-[32px] top-[257px] whitespace-nowrap text-muted text-[13px] tabular-nums">
        {model.annualLabel}
      </p>

      <p className="absolute left-[32px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Investment
      </p>
      <p className="absolute left-[32px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {model.investmentLabel}
      </p>

      <p className="absolute left-[226px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Lifetime net value
      </p>
      <p className="absolute left-[226px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {model.netValueLabel}
      </p>

      <button
        type="button"
        onClick={onReview}
        className="absolute left-[32px] top-[369px] w-[376px] h-[47px] rounded-[6px] bg-brand flex items-center justify-center font-medium text-white text-[14px] hover:brightness-110 active:brightness-95 transition"
      >
        Review plan
      </button>

      <button
        type="button"
        onClick={onCheckGap}
        className="absolute left-[250px] top-[440px] whitespace-nowrap font-medium text-brand text-[13px] hover:underline"
      >
        Check target gap&nbsp;&nbsp;→
      </button>
    </section>
  )
}

function TargetSlider({ target, onChange }) {
  const trackRef = useRef(null)
  const draggingRef = useRef(false)
  const fillPct = (target - TARGET_MIN) / (TARGET_MAX - TARGET_MIN)
  const handleLeft = fillPct * SLIDER_WIDTH

  const pctFromEvent = useCallback((clientX) => {
    const el = trackRef.current
    if (!el) return TARGET_MIN
    const rect = el.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    return TARGET_MIN + ratio * (TARGET_MAX - TARGET_MIN)
  }, [])

  return (
    <div
      ref={trackRef}
      role="slider"
      aria-label="Carbon reduction target"
      aria-valuemin={TARGET_MIN}
      aria-valuemax={TARGET_MAX}
      aria-valuenow={target}
      tabIndex={0}
      onPointerDown={(e) => {
        draggingRef.current = true
        e.currentTarget.setPointerCapture?.(e.pointerId)
        onChange(pctFromEvent(e.clientX))
      }}
      onPointerMove={(e) => draggingRef.current && onChange(pctFromEvent(e.clientX))}
      onPointerUp={() => (draggingRef.current = false)}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') onChange(target + 5)
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') onChange(target - 5)
      }}
      className="absolute left-[32px] top-[102px] w-[376px] h-[18px] cursor-pointer touch-none select-none outline-none"
    >
      <div className="absolute left-0 top-[7px] w-full h-[4px] rounded-[2px] bg-track" />
      <div
        className="absolute left-0 top-[7px] h-[4px] rounded-[2px] bg-brand"
        style={{ width: `${handleLeft}px` }}
      />
      <div
        className="absolute top-[1px] w-[16px] h-[16px] rounded-full bg-white border-2 border-brand shadow-sm -translate-x-1/2"
        style={{ left: `${handleLeft}px` }}
      />
    </div>
  )
}

const UPGRADES = [
  { name: 'LED retrofit', detail: '8 buildings · 8 bills', cost: '$120k' },
  { name: 'Rooftop solar', detail: '6 buildings · 6 bills', cost: '$760k' },
  { name: 'Heat pump conversion', detail: '4 buildings · 4 bills', cost: '$400k' },
]

function UpgradeSummary({ onOpen }) {
  return (
    <section className="absolute left-[56px] top-[783px] w-[1328px] h-[133px] overflow-hidden">
      {UPGRADES.map((u, i) => {
        const top = i * 44
        return (
          <div key={u.name}>
            <div className="absolute left-0 w-[1328px] h-px bg-line" style={{ top: `${top}px` }} />
            <button
              type="button"
              onClick={() => onOpen(u.name)}
              className="group absolute left-0 w-[1328px] h-[43px] text-left"
              style={{ top: `${top + 1}px` }}
            >
              <span className="absolute left-0 top-[14px] whitespace-nowrap font-medium text-ink text-[14px] group-hover:text-brand">
                {u.name}
              </span>
              <span className="absolute left-[608px] top-[14px] whitespace-nowrap text-muted text-[13px]">
                {u.detail}
              </span>
              <span className="absolute left-[1170px] top-[13px] whitespace-nowrap font-medium text-ink text-[14px] tabular-nums">
                {u.cost}
              </span>
              <span className="absolute left-[1312px] top-[10px] whitespace-nowrap text-muted text-[21px] leading-none group-hover:text-brand group-hover:translate-x-1 transition-transform">
                ›
              </span>
            </button>
          </div>
        )
      })}
    </section>
  )
}
