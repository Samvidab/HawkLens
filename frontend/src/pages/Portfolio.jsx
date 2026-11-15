import { useCallback, useEffect, useRef, useState } from 'react'
import Page from '../components/Page'
import ShowcaseModal from '../components/ShowcaseModal'
import { assetUrl, fetchPortfolio, showcaseSrc } from '../lib/api'
import { useGo } from '../lib/ui'
import { isPriced, usePlan } from '../lib/plan'
import { SLIDER_WIDTH, TARGET_MAX, TARGET_MIN } from '../lib/model'
import { DASH, budgetLabel, pct, plural, riskLabel, signedUsd, statusHeadline, tonnes, typeLabel, usd } from '../lib/format'

export default function Portfolio() {
  const go = useGo()
  // The persisted plan (GET /plan). The slider re-plans on the backend; nothing is computed here.
  const { plan, loaded, loadError: planError, actionError, busy, displayTarget, requestTarget } = usePlan()

  // The portfolio's buildings from the backend (data/portfolio.json via GET /portfolio).
  const [buildings, setBuildings] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tourProperty, setTourProperty] = useState(null)

  useEffect(() => {
    let alive = true
    fetchPortfolio()
      .then((d) => alive && setBuildings(d.buildings || []))
      .catch((e) => alive && setLoadError(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  const items = plan?.line_items || []
  const nBuildings = new Set(items.map((r) => r.building_id)).size
  const city = plan?.goal?.city || 'Houston'

  return (
    <Page active="portfolio">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        {city} portfolio
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        {loading
          ? 'Loading buildings…'
          : loadError
            ? 'Buildings unavailable'
            : `${plural(buildings.length, 'building')} · Matterport scans where available`}
      </p>
      <LinkArrow className="left-[1055px] top-[154px]" onClick={() => go('/start-survey')}>
        Run survey
      </LinkArrow>
      <LinkArrow className="left-[1220px] top-[154px]" onClick={() => go('/building')}>
        Building details
      </LinkArrow>

      <PortfolioModel
        buildings={buildings}
        loading={loading}
        loadError={loadError}
        onOpenTour={(p) => setTourProperty(p)}
      />

      {tourProperty && (
        <ShowcaseModal property={tourProperty} onClose={() => setTourProperty(null)} />
      )}

      <CarbonGoal
        plan={plan}
        loaded={loaded}
        planError={planError}
        actionError={actionError}
        busy={busy}
        target={displayTarget}
        onChangeTarget={requestTarget}
        onStep={(delta) => requestTarget(displayTarget + delta)}
        onEdit={() => go('/plan-preferences')}
        onReview={() => go(plan ? '/plan' : '/start-survey')}
        onCheckGap={() => go('/risk-and-target')}
      />

      <h2 className="absolute left-[56px] top-[704px] whitespace-nowrap font-semibold text-ink text-[20px]">
        Recommended upgrades
      </h2>
      <p className="absolute left-[56px] top-[738px] whitespace-nowrap text-muted text-[13px]">
        {isPriced(plan)
          ? `${plural(items.length, 'upgrade')} across ${plural(nBuildings, 'building')} · ${plural(plan.bundles.length, 'upgrade type')}${plan.bundles.length > 3 ? ' (scroll for more)' : ''}`
          : plan?.status === 'no_data'
            ? `Not priced: ${plan.reason}`
            : 'Run the survey to get recommendations from the quant engine'}
      </p>
      <LinkArrow className="left-[1208px] top-[715px]" onClick={() => go('/plan')}>
        See costs &amp; evidence
      </LinkArrow>

      <UpgradeSummary bundles={plan?.bundles || []} onOpen={() => go('/plan')} />

      <p className="absolute left-[56px] top-[947px] whitespace-nowrap text-muted text-[11px]">
        {plan
          ? `Quant engine${plan.stub ? ' (stub: sample pricing)' : ''} · Plan ${plan.plan_id}${busy ? ' · re-planning…' : ''}`
          : 'No plan yet · every number here comes from the backend optimizer'}
      </p>
      <p className="absolute left-[1090px] top-[947px] whitespace-nowrap text-muted text-[11px]">
        {plan?.p_hit_target != null ? `${pct(plan.p_hit_target)} chance of hitting the target` : ''}
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

function PortfolioModel({ buildings, loading, loadError, onOpenTour }) {
  return (
    <section className="absolute left-[56px] top-[231px] w-[848px] h-[420px] overflow-hidden rounded-[8px] bg-model">
      <p className="absolute left-[23px] top-[21px] whitespace-nowrap font-medium text-ink text-[15px]">
        Your buildings
      </p>
      <p className="absolute left-[23px] top-[46px] whitespace-nowrap text-muted text-[13px]">
        Real Matterport scans — expand a building to walk through it.
      </p>

      <div className="absolute left-[23px] right-[23px] top-[74px] bottom-[42px] overflow-y-auto pr-1">
        {loadError && (
          <p className="text-[13px] text-[#b4532f]">
            Couldn&rsquo;t load the portfolio ({loadError}).
          </p>
        )}
        {!loadError && loading && <p className="text-muted text-[13px]">Loading buildings…</p>}
        {!loadError && !loading && buildings.length === 0 && (
          <p className="text-muted text-[13px]">The portfolio has no buildings.</p>
        )}
        <div className="grid grid-cols-3 gap-3">
          {buildings.map((b) => (
            <BuildingCard key={b.building_id} building={b} onOpenTour={onOpenTour} />
          ))}
        </div>
      </div>

      <p className="absolute left-[23px] bottom-[14px] whitespace-nowrap text-muted text-[11px]">
        Imagery &amp; 3D tours via Matterport (licensed from CoStar)
      </p>
    </section>
  )
}

function BuildingCard({ building, onOpenTour }) {
  const modelId = building.matterport_model_id
  const [imgOk, setImgOk] = useState(Boolean(modelId))
  const tour = modelId
    ? { id: modelId, name: building.name, address: building.address, show_url: showcaseSrc(modelId) }
    : null
  return (
    <button
      type="button"
      disabled={!tour}
      onClick={() => tour && onOpenTour(tour)}
      className="group relative block w-full overflow-hidden rounded-[6px] bg-white text-left shadow-sm hover:shadow-md transition-shadow disabled:cursor-default"
    >
      <div className="relative w-full aspect-[4/3] bg-line overflow-hidden">
        {imgOk ? (
          <img
            src={assetUrl(`/properties/${modelId}/thumbnail`)}
            alt={building.name || building.building_id}
            loading="lazy"
            onError={() => setImgOk(false)}
            className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted text-[12px]">
            no image
          </div>
        )}
        {tour && (
          <span className="absolute right-2 top-2 rounded-[4px] bg-white/90 px-2 py-1 text-[11px] font-medium text-brand opacity-0 group-hover:opacity-100 transition-opacity">
            Expand ↗
          </span>
        )}
      </div>
      <div className="px-2.5 py-2">
        <p className="truncate text-[13px] font-medium text-ink">{building.name || building.building_id}</p>
        <p className="truncate text-[11px] text-muted">{building.address || building.city || DASH}</p>
      </div>
    </button>
  )
}

function CarbonGoal({ plan, loaded, planError, actionError, busy, target, onChangeTarget, onStep, onEdit, onReview, onCheckGap }) {
  const covered = plan?.status === 'ok'
  const headline = !loaded ? 'Loading plan…' : planError ? 'Plan unavailable' : statusHeadline(plan)
  const sub = planError
    ? planError
    : actionError
      ? actionError
      : plan?.status === 'infeasible'
        ? `${tonnes(plan.shortfall_tonnes, ' t/yr')} short · ${tonnes(plan.tonnes_per_year)}`
        : plan?.status === 'no_data'
          ? plan.reason
          : plan
            ? tonnes(plan.tonnes_per_year)
            : 'Run the survey to price a plan'
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
      <p className="absolute left-[384px] top-[125px] whitespace-nowrap text-muted text-[11px]">{TARGET_MAX}%</p>

      <p className="absolute left-[32px] top-[165px] whitespace-nowrap text-muted text-[13px]">
        {budgetLabel(plan?.goal?.budget_usd)} · {riskLabel(plan?.goal?.risk_lambda ?? 0.5)} risk
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
          covered || !plan ? 'text-ink' : 'text-[#b4532f]'
        }`}
      >
        {busy ? 'Re-planning…' : headline}
      </p>
      <p
        title={sub}
        className={`absolute left-[32px] top-[257px] w-[376px] truncate text-[13px] tabular-nums ${
          actionError || planError ? 'text-[#b4532f]' : 'text-muted'
        }`}
      >
        {sub}
      </p>

      <p className="absolute left-[32px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Investment
      </p>
      <p className="absolute left-[32px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {usd(plan?.total_upfront)}
      </p>

      <p className="absolute left-[226px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Lifetime net value
      </p>
      <p className="absolute left-[226px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {signedUsd(plan?.exp_npv)}
      </p>

      <button
        type="button"
        onClick={onReview}
        className="absolute left-[32px] top-[369px] w-[376px] h-[47px] rounded-[6px] bg-brand flex items-center justify-center font-medium text-white text-[14px] hover:brightness-110 active:brightness-95 transition"
      >
        {plan ? 'Review plan' : 'Run survey'}
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

function UpgradeSummary({ bundles, onOpen }) {
  // One row per upgrade type in the optimizer's selection (backend sums; shown as-is).
  return (
    <section className="absolute left-[56px] top-[783px] w-[1328px] h-[133px] overflow-y-auto overflow-x-hidden">
      {bundles.map((b, i) => {
        const top = i * 44
        return (
          <div key={b.type}>
            <div className="absolute left-0 w-[1328px] h-px bg-line" style={{ top: `${top}px` }} />
            <button
              type="button"
              onClick={() => onOpen(b.type)}
              className="group absolute left-0 w-[1328px] h-[43px] text-left"
              style={{ top: `${top + 1}px` }}
            >
              <span className="absolute left-0 top-[14px] whitespace-nowrap font-medium text-ink text-[14px] group-hover:text-brand">
                {typeLabel(b.type)}
              </span>
              <span className="absolute left-[608px] top-[14px] whitespace-nowrap text-muted text-[13px]">
                {plural(b.n_buildings, 'building')} · {plural(b.n_upgrades, 'upgrade')}
              </span>
              <span className="absolute left-[1170px] top-[13px] whitespace-nowrap font-medium text-ink text-[14px] tabular-nums">
                {usd(b.upfront_usd)}
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
