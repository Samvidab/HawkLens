import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo } from '../lib/ui'
import { fetchEvents } from '../lib/api'
import { isPriced, usePlan } from '../lib/plan'
import { DASH, budgetLabel, pct, plural, riskLabel, signedUsd, statusHeadline, tonnes, typeLabel, usd } from '../lib/format'

// Chart geometry (px inside the 880×290 card): x axis from 64 to 626, $0 line at y=165, ±1 tick = 47px.
const X0 = 64
const XW = 562
const Y0 = 165
const TICK_PX = 47
const MAX_BAR_PX = 60

/** Smallest 1/2/5×10^k that is >= v (axis tick for the chart; display scaling only). */
function niceCeil(v) {
  if (!(v > 0)) return 1
  const e = 10 ** Math.floor(Math.log10(v))
  return [1, 2, 5, 10].map((m) => m * e).find((t) => t >= v)
}

/** Lay out the engine's abatement bars (sorted ascending by cost per tonne) on the card. */
function layoutBars(bars, selected, tonnesNeeded) {
  const total = bars.reduce((a, b) => a + Math.max(b.tonnes_per_year || 0, 0), 0)
  const finite = bars.filter((b) => typeof b.cost_per_tonne === 'number')
  const tick = niceCeil(Math.max(...finite.map((b) => Math.abs(b.cost_per_tonne)), 0))
  let x = X0
  const out = bars.map((b) => {
    const w = total > 0 ? (Math.max(b.tonnes_per_year || 0, 0) / total) * XW : 0
    const cpt = typeof b.cost_per_tonne === 'number' ? b.cost_per_tonne : 0
    const h = Math.min(Math.max((Math.abs(cpt) / tick) * TICK_PX, 2), MAX_BAR_PX)
    const r = { ...b, left: x, width: Math.max(w - 2, 1), height: h, top: cpt < 0 ? Y0 : Y0 - h, inPlan: selected.has(b.upgrade_id) }
    x += w
    return r
  })
  const ref = total > 0 && typeof tonnesNeeded === 'number' ? X0 + Math.min(tonnesNeeded / total, 1) * XW : null
  return { bars: out, tick, total, ref }
}

function buildMetrics(plan) {
  const g = plan?.goal || {}
  return [
    {
      label: 'Annual CO₂ reduction',
      value: tonnes(plan?.tonnes_per_year),
      sub: plan?.status === 'infeasible' ? `${tonnes(plan.shortfall_tonnes, ' t/yr')} short of your goal` : statusHeadline(plan),
      left: 0,
    },
    { label: 'Lifetime net value', value: signedUsd(plan?.exp_npv), sub: 'Expected NPV after retrofit costs', left: 338 },
    {
      label: 'Upfront investment',
      value: usd(plan?.total_upfront),
      sub: `${budgetLabel(g.budget_usd)} · ${riskLabel(g.risk_lambda)} risk`,
      left: 676,
    },
    {
      label: 'Chance of hitting target',
      value: pct(plan?.p_hit_target),
      sub: `Chance of a loss ${pct(plan?.p_loss, 1)}`,
      left: 1014,
    },
  ]
}

const hhmm = (ts) => (ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '')

export default function PlanDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const { plan, loaded, loadError, busy, runId, displayTarget } = usePlan()
  const METRICS = buildMetrics(plan)
  const priced = isPriced(plan)
  const items = plan?.line_items || []
  const nBuildings = new Set(items.map((r) => r.building_id)).size
  const cov = plan?.coverage
  const chart = layoutBars(plan?.macc?.bars || [], new Set(plan?.selected || []), plan?.tonnes_needed)

  const [activity, setActivity] = useState([])
  useEffect(() => {
    if (!runId) return undefined
    let alive = true
    fetchEvents(runId)
      .then((ev) => alive && setActivity(ev.filter((e) => e.kind !== 'error').slice(-3).reverse()))
      .catch(() => alive && setActivity([]))
    return () => {
      alive = false
    }
  }, [runId, plan?.plan_id])

  return (
    <Page active="plan">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        What&rsquo;s in your plan
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        {!loaded
          ? 'Loading plan…'
          : loadError
            ? `Plan unavailable: ${loadError}`
            : plan
              ? `${plural(items.length, 'upgrade')} · ${displayTarget}% reduction goal${busy ? ' · re-planning…' : ''}`
              : 'No plan yet · run the survey to price one'}
      </p>
      <button
        type="button"
        onClick={() => go('/financing-approval')}
        className="absolute left-[1206px] top-[139px] w-[178px] h-[47px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
      >
        Review &amp; approve
      </button>

      {/* Plan outcomes metric strip */}
      <div className="absolute left-[56px] top-[230px] w-[1328px] h-[94px]">
        {METRICS.map((m, i) => (
          <div key={m.label}>
            {i > 0 && (
              <div
                className="absolute top-0 w-px h-[86px] bg-line"
                style={{ left: `${m.left - 20}px` }}
              />
            )}
            <p className="absolute top-0 text-muted text-[12px]" style={{ left: `${m.left}px` }}>
              {m.label}
            </p>
            <p
              className="absolute top-[24px] font-semibold text-ink text-[27px] whitespace-nowrap"
              style={{ left: `${m.left}px` }}
            >
              {m.value}
            </p>
            <p className="absolute top-[65px] text-muted text-[12px]" style={{ left: `${m.left}px` }}>
              {m.sub}
            </p>
          </div>
        ))}
      </div>

      {/* Abatement curve card */}
      <section className="absolute left-[56px] top-[365px] w-[880px] h-[290px] rounded-[6px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[21px] top-[18px] font-semibold text-ink text-[16px]">
          Available carbon cuts
        </p>
        <p className="absolute left-[21px] top-[44px] text-muted text-[12px]">
          Start below zero: these upgrades cut emissions and earn a return.
        </p>
        <p className="absolute left-[21px] top-[79px] text-muted text-[10px]">Lifetime net cost / tCO₂</p>
        <p className="absolute left-[475px] top-[253px] text-muted text-[10px]">Annual CO₂ avoided →</p>

        {/* grid lines + axis labels */}
        <div className="absolute left-[64px] top-[212px] w-[562px] h-px bg-[#e7ebe2]" />
        <p className="absolute left-[16px] top-[207px] text-muted text-[9px]">{usd(-chart.tick)}</p>
        <div className="absolute left-[64px] top-[165px] w-[562px] h-px bg-[#9aa68f]" />
        <p className="absolute left-[16px] top-[160px] text-muted text-[9px]">$0</p>
        <div className="absolute left-[64px] top-[118px] w-[562px] h-px bg-[#e7ebe2]" />
        <p className="absolute left-[16px] top-[113px] text-muted text-[9px]">{usd(chart.tick)}</p>

        {/* the engine's abatement bars: width = CO₂ avoided, height = cost per tonne (below zero earns money) */}
        {chart.bars.map((b) => (
          <div
            key={b.upgrade_id}
            title={`${typeLabel(b.type)} · ${plan?.building_names?.[b.building_id] || b.building_id} · ${usd(b.cost_per_tonne)}/t`}
            className={`absolute rounded-[2px] ${b.inPlan ? 'bg-brand' : 'bg-[#dde4d5] border border-[#b9c5ae]'}`}
            style={{ left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` }}
          />
        ))}
        {chart.bars.length === 0 && (
          <p className="absolute left-[200px] top-[150px] text-muted text-[12px]">
            {priced ? 'No eligible upgrades on the curve' : 'No priced upgrades yet'}
          </p>
        )}
        {chart.ref !== null && (
          <>
            <div className="absolute top-[110px] w-px h-[131px] bg-[#7a693b]" style={{ left: `${chart.ref}px` }} />
            <p className="absolute top-[93px] font-medium text-[#7a693b] text-[10px] whitespace-nowrap" style={{ left: `${chart.ref - 30}px` }}>
              Target: {plan?.goal?.target_pct}%
            </p>
          </>
        )}
        {[0, 1 / 3, 2 / 3, 1].map((f) => (
          <p key={f} className="absolute top-[237px] text-muted text-[9px]" style={{ left: `${X0 - 5 + f * XW}px` }}>
            {chart.total ? Math.round(f * chart.total).toLocaleString('en-US') : ''}
          </p>
        ))}

        {/* legend */}
        <div className="absolute left-[21px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#416b4d]" />
        <p className="absolute left-[36px] top-[268px] text-muted text-[10px]">In your plan</p>
        <div className="absolute left-[144px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#dde4d5]" />
        <p className="absolute left-[159px] top-[268px] text-muted text-[10px]">Not selected</p>

        {/* right note */}
        <div className="absolute left-[651px] top-[83px] w-px h-[182px] bg-[#e7ebe2]" />
        <p className="absolute left-[673px] top-[92px] font-medium text-muted text-[10px] tracking-[0.6px]">
          PROFITABLE CUTS
        </p>
        <p className="absolute left-[673px] top-[113px] font-semibold text-brand text-[31px]">
          {tonnes(plan?.profitable_tonnes_per_year, '')}
        </p>
        <p className="absolute left-[673px] top-[153px] text-muted text-[10px]">tCO₂ / year</p>
        <div className="absolute left-[673px] top-[178px] font-medium text-ink text-[12px] leading-[20px]">
          Below-zero upgrades
          <br />
          create net financial value.
        </div>
        <div className="absolute left-[673px] top-[240px] text-muted text-[10px] leading-[17px]">
          Bar width = carbon avoided
          <br />
          Bar height = cost per tonne
        </div>
      </section>

      {/* Survey activity card */}
      <section className="absolute left-[960px] top-[365px] w-[424px] h-[290px] rounded-[6px] border border-line bg-white overflow-hidden">
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[21px] top-[18px] font-semibold text-ink text-[16px] hover:text-brand"
        >
          Survey activity
        </button>
        <div className="absolute left-[314px] top-[19px] w-[86px] h-[23px] rounded-[5px] bg-[#edf3e6] flex items-center">
          <span className="ml-[12px] font-medium text-brand text-[10px]">
            {cov ? `${cov.surveyed.length} / ${cov.requested.length} ready` : DASH}
          </span>
        </div>
        <p className="absolute left-[21px] top-[44px] text-muted text-[12px]">
          Latest completed survey events
        </p>
        {activity.length === 0 && (
          <p className="absolute left-[21px] top-[82px] text-muted text-[11px]">No survey events recorded for this run.</p>
        )}
        {activity.map((a, i) => {
          const top = 82 + i * 57
          return (
            <div key={a.seq}>
              <span
                className="absolute left-[21px] w-[18px] h-[18px] rounded-full bg-brand text-white text-[11px] flex items-center justify-center"
                style={{ top: `${top}px` }}
              >
                ✓
              </span>
              <p
                className="absolute left-[48px] font-medium text-ink text-[12px]"
                style={{ top: `${top}px` }}
              >
                {hhmm(a.ts)} · {a.agent}
              </p>
              <p className="absolute left-[48px] w-[350px] truncate text-muted text-[11px]" style={{ top: `${top + 18}px` }}>
                {a.message}
              </p>
              <p className="absolute left-[48px] text-muted text-[9px]" style={{ top: `${top + 33}px` }}>
                {a.building_name || a.kind}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[21px] top-[257px] w-[380px] h-px bg-[#e7ebe2]" />
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[21px] top-[269px] font-medium text-brand text-[11px] hover:underline"
        >
          View survey evidence
        </button>
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[388px] top-[266px] text-brand text-[15px]"
        >
          ↗
        </button>
      </section>

      {/* Upgrade breakdown table */}
      <section className="absolute left-[56px] top-[709px] w-[1328px] h-[193px] rounded-[6px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[21px] top-[16px] font-semibold text-ink text-[16px]">
          Upgrade breakdown
        </p>
        <p className="absolute left-[237px] top-[21px] text-muted text-[11px]">
          {priced
            ? `${plural(items.length, 'upgrade')} across ${plural(nBuildings, 'building')}${(plan.bundles?.length || 0) > 3 ? ` · ${plan.bundles.length} types, scroll for more` : ''}`
            : DASH}
        </p>
        <p className="absolute left-[919px] top-[20px] text-muted text-[11px]">
          Worst 5% average: {signedUsd(plan?.cvar5)} NPV
        </p>
        <button
          type="button"
          onClick={() => go('/investment-memo')}
          className="absolute left-[1149px] top-[11px] w-[156px] h-[31px] rounded-[5px] bg-[#f1f4ed] text-left"
        >
          <span className="ml-[12px] font-medium text-brand text-[11px]">Investment memo&nbsp;&nbsp;↗</span>
        </button>

        <div className="absolute left-0 top-[54px] w-[1326px] h-[29px] bg-[#f6f7f3]" />
        {['UPGRADE BUNDLE', 'COVERAGE', 'UPFRONT COST', 'ANNUAL CO₂ CUT', 'EXPECTED NPV'].map(
          (h, i) => (
            <p
              key={h}
              className="absolute top-[63px] font-medium text-muted text-[9px] tracking-[0.6px]"
              style={{ left: `${[21, 417, 655, 895, 1135][i]}px` }}
            >
              {h}
            </p>
          ),
        )}
        <div className="absolute left-0 top-[83px] w-[1326px] h-[108px] overflow-y-auto">
          {(plan?.bundles || []).map((r, i) => {
            const top = 7 + i * 33
            return (
              <div key={r.type}>
                {i > 0 && (
                  <div
                    className="absolute left-[21px] w-[1284px] h-px bg-[#e7ebe2]"
                    style={{ top: `${top - 7}px` }}
                  />
                )}
                <button
                  type="button"
                  onClick={() => navigate('/building')}
                  className="absolute left-[21px] font-medium text-ink text-[12px] hover:text-brand"
                  style={{ top: `${top}px` }}
                >
                  {typeLabel(r.type)}
                </button>
                <p className="absolute left-[417px] text-muted text-[12px]" style={{ top: `${top}px` }}>
                  {plural(r.n_buildings, 'building')} · {plural(r.n_upgrades, 'upgrade')}
                </p>
                <p className="absolute left-[655px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                  {usd(r.upfront_usd)}
                </p>
                <p className="absolute left-[895px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                  {tonnes(r.tonnes_per_year, ' tCO₂')}
                </p>
                <p className="absolute left-[1135px] font-medium text-brand text-[12px]" style={{ top: `${top}px` }}>
                  {signedUsd(r.exp_npv)}
                </p>
              </div>
            )
          })}
          {!priced && (
            <p className="absolute left-[21px] top-[7px] text-muted text-[12px]">
              {plan?.status === 'no_data' ? `Not priced: ${plan.reason}` : 'No plan yet'}
            </p>
          )}
          <div style={{ height: `${7 + (plan?.bundles?.length || 1) * 33}px` }} />
        </div>
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        {plan ? `Quant engine${plan.stub ? ' (stub: sample pricing)' : ''} · Plan ${plan.plan_id} · Review assumptions before approval` : DASH}
      </p>
      <button
        type="button"
        onClick={() => go('/risk-and-target')}
        className="absolute left-[1174px] top-[947px] font-medium text-brand text-[13px] hover:underline"
      >
        Risk &amp; target details&nbsp;&nbsp;→
      </button>
    </Page>
  )
}
