import { useCallback, useEffect, useRef, useState } from 'react'
import Page from '../components/Page'
import { NA, Sources, Stub, useStub } from '../components/Truth'
import ShowcaseModal from '../components/ShowcaseModal'
import { useGo } from '../lib/ui'
import { useOverview } from '../lib/store'
import { planRows, planSummary, riskLabel, targetModel, usdK, widget } from '../lib/viewModels'
import { assetUrl } from '../lib/api'
import { SLIDER_WIDTH, TARGET_MAX, TARGET_MIN, clampTarget } from '../lib/model'

// Cards come from GET /portfolio; plan figures come from the loaded run layout. Missing values remain unavailable.
export default function Portfolio() {
  const go = useGo()
  const run = useOverview({ requireTarget: true })
  const stub = useStub().engine
  const [tourBuilding, setTourBuilding] = useState(null)
  const inventory = run.portfolio?.buildings || []
  const layoutModel = run.layout ? targetModel(run.layout) : null
  const [target, setTarget] = useState(layoutModel?.target ?? run.prefs.target_pct)
  const model = layoutModel ? { ...layoutModel, target } : null
  const buildings = widget(run.layout, 'portfolio_3d')?.buildings ?? null
  const hero = run.portfolio?.buildings?.find((b) => b.hero) || run.portfolio?.buildings?.[0]
  const featured = hero ? { id: hero.building_id, name: hero.name }
    : buildings?.[0] ? { id: buildings[0].building_id, name: buildings[0].name } : null
  const city = run.portfolio?.city || null
  const nExcluded = buildings ? buildings.filter((b) => b.excluded).length : 0

  const setTargetClamped = useCallback((next) => setTarget(clampTarget(next)), [])

  // Sliders send one action when they settle (App Flow 3: on release, at most every 400 ms).
  useEffect(() => {
    run.setPrefs({ target_pct: target })
    if (!run.layout || layoutModel?.target === target) return undefined
    const t = setTimeout(() => run.act('set_target', { target_pct: target }).catch(() => setTarget(layoutModel.target)), 400)
    return () => clearTimeout(t)
  }, [target]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (layoutModel && layoutModel.target !== target && !run.busy) setTarget(layoutModel.target)
  }, [layoutModel?.target]) // eslint-disable-line react-hooks/exhaustive-deps

  const openBuilding = useCallback(async (id = featured?.id) => {
    try {
      if (run.layout && id) await run.act('open_building', { building_id: id })
      go('/building')
    } catch {}
  }, [run, featured, go])

  return (
    <Page active="portfolio">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        {city ? `${city} portfolio` : 'Portfolio'}
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        {`${inventory.length} buildings from the recorded portfolio${nExcluded ? ` · ${nExcluded} excluded` : ''}`}
      </p>
      <LinkArrow className="left-[1055px] top-[154px]" onClick={() => go('/start-survey')}>
        Run survey
      </LinkArrow>
      <LinkArrow className="left-[1220px] top-[154px]" onClick={() => openBuilding()}>
        Building details
      </LinkArrow>

      <button className="absolute left-[56px] top-[205px] text-brand text-[12px] underline" onClick={() => go('/expanded-portfolio-model')}>Explore footprint map ↗</button>
      <button className="absolute left-[270px] top-[205px] text-brand text-[12px] underline" onClick={() => go('/history')}>Saved plans & survey history →</button>
      <button className="absolute left-[560px] top-[205px] text-brand text-[12px] underline" onClick={() => go('/research')}>Energy & source research →</button>
      <PortfolioModel buildings={inventory} onTour={setTourBuilding} onDetails={openBuilding} hasRun={!!run.layout} />
      {tourBuilding && <ShowcaseModal building={tourBuilding} onClose={() => setTourBuilding(null)} />}

      {run.layout ? (
      <CarbonGoal
        target={target}
        model={model}
        stub={stub}
        onChangeTarget={setTargetClamped}
        onStep={(delta) => setTargetClamped(target + delta)}
        onEdit={() => go('/plan-preferences')}
        onReview={() => go('/plan')}
        onCheckGap={() => go('/risk-and-target')}
        budgetText={model
          ? `Budget ${model.budgetUsd == null ? 'not set' : usdK(model.budgetUsd)} · ${model.riskLambda == null ? `risk ${NA}` : `${riskLabel(model.riskLambda)} risk`}`
          : `Budget and risk ${NA}`}
        busy={run.busy > 0}
      />

      ) : (
        <section className="absolute left-[944px] top-[231px] w-[410px] p-6" data-testid="no-data">
          <h2 className="font-semibold text-ink text-[20px]">No plan loaded</h2>
          <p className="mt-3 text-muted text-[14px]">Costs, emissions and optimization results are not available until a survey is loaded.</p>
          <button className="mt-5 text-brand underline" onClick={() => go('/start-survey')}>Start a survey →</button>
          {run.demoRunId && <button className="block mt-4 text-brand underline" disabled={run.phase === 'surveying'}
            onClick={() => run.start({}, { replay: true })}>{run.phase === 'surveying' ? 'Loading recorded survey…' : 'Load recorded survey'}</button>}
        </section>
      )}

      <h2 className="absolute left-[56px] top-[704px] whitespace-nowrap font-semibold text-ink text-[20px]">
        Recommended upgrades
      </h2>
      <p className="absolute left-[56px] top-[738px] whitespace-nowrap text-muted text-[13px]">
        {planSummary(run.layout)?.count ?? `Upgrades ${NA}`}
      </p>
      <LinkArrow className="left-[1208px] top-[715px]" onClick={() => go('/plan')}>
        See costs &amp; evidence
      </LinkArrow>

      <UpgradeSummary onOpen={() => go('/plan')} rows={planRows(run.layout) || []} stub={stub} />

      <Sources />
      <p className="absolute left-[1090px] top-[947px] whitespace-nowrap text-muted text-[11px]">
        Chance of hitting the target: {model?.confidence == null ? NA : `${model.confidence}%`}{stub && model?.confidence != null && <Stub />}
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

export function PortfolioModel({ buildings, onTour, onDetails, hasRun }) {
  return (
    <section className="absolute left-[56px] top-[231px] w-[848px] h-[420px] rounded-[8px] bg-model p-5">
      <h2 className="font-medium text-ink text-[15px]">Your buildings</h2>
      <p className="mt-1 text-muted text-[12px]">Recorded CoStar properties · Matterport tours of the surveyed spaces</p>
      <div className="grid grid-cols-4 gap-3 mt-4" data-testid="portfolio-cards">
        {buildings.map((b) => (
          <article key={b.building_id} data-building-id={b.building_id} className="rounded-md bg-white p-3 shadow-sm min-w-0 h-[149px] relative overflow-hidden">
            {b.thumbnail_url && <img src={assetUrl(b.thumbnail_url)} alt={`Recorded Matterport thumbnail of ${b.name}`} className="absolute right-0 top-0 w-[70px] h-[40px] object-cover" loading="lazy" onError={e => {e.currentTarget.style.display='none'}} />}
            <h3 className="font-medium text-ink text-[12px] truncate" title={b.name || ''} style={{maxWidth:b.thumbnail_url?'100px':undefined}}>{b.name || 'Name not available'}</h3>
            <p className="text-muted text-[10px] truncate mt-1" title={b.address || ''}>{b.address || 'Address not available'}</p>
            <p className="text-muted text-[10px] mt-2">{b.sqft == null ? 'Area not available' : `${Number(b.sqft).toLocaleString()} sq ft`}</p>
            <p className="text-muted text-[10px]">Built {b.year_built ?? 'not available'} · {b.stories == null ? 'Floors not available' : `${b.stories} floors`}</p>
            <p className="text-muted text-[9px] mt-1">{b.thumbnail_url ? 'Recorded Matterport image' : 'Thumbnail not available'}</p>
            <div className="flex justify-between gap-1 mt-2 text-[11px] text-brand">
              <button disabled={!b.showcase_url} onClick={() => onTour(b)} className="underline disabled:text-muted disabled:no-underline"
                aria-label={`Open tour of ${b.name || b.building_id}`}>{b.showcase_url ? 'Open tour ↗' : 'Tour unavailable'}</button>
              {hasRun && <button onClick={() => onDetails(b.building_id)} className="underline" aria-label={`Details for ${b.name || b.building_id}`}>Details →</button>}
            </div>
          </article>
        ))}
      </div>
      <p className="text-muted text-[10px] mt-3">Tours show recorded scans, which may cover a tenant suite rather than the whole building.</p>
    </section>
  )
}

function CarbonGoal({ target, model: m, stub, onChangeTarget, onStep, onEdit, onReview, onCheckGap, budgetText, busy }) {
  const model = m || { covered: null, tonnes: null, statusLabel: `Plan ${NA}`, annualLabel: '', investmentLabel: NA, netValueLabel: NA }
  return (
    <section className="absolute left-[944px] top-[231px] w-[440px] h-[440px] overflow-visible">
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

      <p className="absolute left-[32px] top-[125px] whitespace-nowrap text-muted text-[11px]">{TARGET_MIN}%</p>
      <p className="absolute left-[384px] top-[125px] whitespace-nowrap text-muted text-[11px]">{TARGET_MAX}%</p>

      <p className="absolute left-[32px] top-[165px] whitespace-nowrap text-muted text-[13px]">
        {budgetText}
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
          model.covered === false ? 'text-[#b4532f]' : 'text-ink'
        }`}
      >
        {model.statusLabel}
      </p>
      <p className="absolute left-[32px] top-[257px] whitespace-nowrap text-muted text-[13px] tabular-nums">
        {model.annualLabel}{stub && model.tonnes != null && <Stub />}{busy ? ' · updating…' : ''}
      </p>

      <p className="absolute left-[32px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Investment
      </p>
      <p className="absolute left-[32px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {model.investmentLabel}{stub && model.investmentLabel !== NA && <Stub />}
      </p>

      <p className="absolute left-[226px] top-[297px] whitespace-nowrap text-muted text-[12px]">
        Lifetime net value
      </p>
      <p className="absolute left-[226px] top-[318px] whitespace-nowrap font-medium text-ink text-[22px] tabular-nums">
        {model.netValueLabel}{stub && model.netValueLabel !== NA && <Stub />}
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
        className="absolute left-[250px] top-[425px] whitespace-nowrap font-medium text-brand text-[13px] hover:underline"
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

function UpgradeSummary({ onOpen, rows, stub }) {
  const list = rows.map((r) => ({ name: r.name, detail: r.coverage, cost: r.cost }))
  if (!list.length) return <p className="absolute left-[56px] top-[790px] text-muted text-[13px]">Upgrade results not available.</p>
  return (
    <section className="absolute left-[56px] top-[783px] w-[1328px] h-[133px] overflow-hidden">
      {list.map((u, i) => {
        const top = i * (list.length > 3 ? 30 : 44)
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
              <span className="absolute left-[1130px] top-[13px] whitespace-nowrap font-medium text-ink text-[14px] tabular-nums">
                {u.cost}{stub && u.cost !== NA && <Stub />}
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
