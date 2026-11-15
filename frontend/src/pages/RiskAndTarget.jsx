import { useNavigate } from 'react-router-dom'
import { usePlan } from '../lib/plan'
import { DASH, pct, signedUsd, tonnes, usd } from '../lib/format'
import Page from '../components/Page'

// Histogram geometry inside the 848×360 card: bars from x=56 to x=607, baseline y=262, tallest bar 142px.
const HX0 = 56
const HW = 551
const HBASE = 262
const HMAX = 142

/** Place the engine's plan-level NPV histogram (hist_bins: [{x0, x1, count}]) on the card. */
function layoutHistogram(bins) {
  if (!bins?.length) return { bars: [], axis: [], zeroX: null }
  const lo = bins[0].x0
  const hi = bins[bins.length - 1].x1
  const span = hi - lo || 1
  const maxCount = Math.max(...bins.map((b) => b.count), 1)
  const xOf = (v) => HX0 + ((v - lo) / span) * HW
  const bars = bins.map((b) => {
    const h = (b.count / maxCount) * HMAX
    return { left: xOf(b.x0), width: Math.max(xOf(b.x1) - xOf(b.x0) - 2, 1), top: HBASE - h, height: h, loss: b.x1 <= 0 }
  })
  const axis = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ label: usd(lo + f * span), left: HX0 - 9 + f * HW }))
  return { bars, axis, zeroX: lo < 0 && hi > 0 ? xOf(0) : null }
}

const EXPLAINERS = [
  'A bar counts simulated futures in a range of lifetime net values. Below zero means a loss.',
  'Worst 5% average is the mean result in the least favorable scenarios—not the worst single outcome.',
  'Every change to the target, budget or risk re-runs the optimizer; these numbers always belong to the plan shown.',
]

export default function RiskAndTarget() {
  const navigate = useNavigate()
  const { plan, loaded, loadError } = usePlan()
  const hist = layoutHistogram(plan?.hist_bins)
  const ok = plan?.status === 'ok'
  const gapTitle = !plan
    ? loaded ? 'No plan yet' : 'Loading plan…'
    : ok ? 'Your target is covered' : plan.status === 'infeasible' ? 'Your target is not covered' : 'Not priced yet'
  const gapValue = ok ? plan.tonnes_margin : plan?.status === 'infeasible' ? plan.shortfall_tonnes : null

  return (
    <Page active="plan">
      <button
        type="button"
        onClick={() => navigate('/plan')}
        className="absolute left-[56px] top-[111px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
      >
        ←&nbsp;&nbsp;Your plan
      </button>
      <h1 className="absolute left-[56px] top-[149px] font-semibold text-ink text-[32px] leading-[1.45]">
        Understand the trade-offs
      </h1>
      <p className="absolute left-[56px] top-[203px] text-muted text-[14px] leading-[1.45]">
        Compare the baseline distribution with your current target and budget.
      </p>

      {/* Risk histogram */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[360px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          What could your return look like?
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          Lifetime NPV distribution · {plan ? `Plan ${plan.plan_id}` : loadError || 'No plan yet'}
        </p>
        <p className="absolute left-[637px] top-[17px] font-semibold text-brand text-[30px] leading-[1.45]">
          {signedUsd(plan?.exp_npv)}
        </p>
        <p className="absolute left-[637px] top-[62px] text-muted text-[11px] leading-[1.45]">
          Expected net value
        </p>

        {hist.bars.map((b, i) => (
          <div
            key={i}
            className={`absolute rounded-[2px] ${b.loss ? 'bg-[#7a693b]' : 'bg-brand'}`}
            style={{ left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` }}
          />
        ))}
        {hist.bars.length === 0 && (
          <p className="absolute left-[200px] top-[180px] text-muted text-[12px]">No simulated distribution for this plan</p>
        )}

        {/* break-even line */}
        {hist.zeroX !== null && (
          <>
            <div className="absolute top-[104px] w-px h-[158px] bg-[#7a693b]" style={{ left: `${hist.zeroX}px` }} />
            <p className="absolute top-[84px] text-[#7a693b] text-[11px] leading-[1.45]" style={{ left: `${hist.zeroX - 27}px` }}>
              Break even
            </p>
          </>
        )}

        {hist.axis.map(({ label, left }) => (
          <p
            key={left}
            className="absolute top-[272px] text-muted text-[11px] leading-[1.45]"
            style={{ left: `${left}px` }}
          >
            {label}
          </p>
        ))}

        <p className="absolute left-[637px] top-[125px] font-semibold text-[#7a693b] text-[20px] leading-[1.45]">
          {pct(plan?.p_loss, 1)}
        </p>
        <p className="absolute left-[637px] top-[157px] text-muted text-[11px] leading-[1.45]">
          Chance of a loss
        </p>
        <p className="absolute left-[637px] top-[204px] font-semibold text-ink text-[20px] leading-[1.45]">
          {signedUsd(plan?.cvar5)}
        </p>
        <p className="absolute left-[637px] top-[238px] text-muted text-[11px] leading-[1.45]">
          Worst 5% average
        </p>
        <p className="absolute left-[19px] top-[327px] text-muted text-[11px] leading-[1.45]">
          Monte Carlo from the quant engine · re-simulated whenever the plan changes.
        </p>
      </section>

      {/* Target gap card */}
      <button
        type="button"
        onClick={() => navigate('/plan')}
        className="absolute left-[944px] top-[265px] w-[440px] h-[320px] rounded-[8px] border border-line bg-white text-left"
      >
        <span className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          {gapTitle}
        </span>
        <span className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          {plan?.goal ? `Goal ${plan.goal.target_pct}% · needs ${tonnes(plan.tonnes_needed)}` : DASH}
        </span>
        <span className={`absolute left-[19px] top-[75px] font-semibold text-[30px] leading-[1.45] ${ok ? 'text-brand' : 'text-[#b4532f]'}`}>
          {tonnes(gapValue, '')}
        </span>
        <span className="absolute left-[19px] top-[120px] text-muted text-[11px] leading-[1.45]">
          {ok ? 'tonnes per year above your goal' : plan?.status === 'infeasible' ? 'tonnes per year short of your goal' : plan?.reason || ''}
        </span>
        <span className="absolute left-[19px] top-[139px] w-[400px] h-px bg-line" />
        <span className="absolute left-[19px] top-[165px] text-ink text-[14px] leading-[1.45]">
          Planned: {tonnes(plan?.tonnes_per_year)}
        </span>
        <span className="absolute left-[19px] top-[203px] text-muted text-[11px] leading-[1.45]">
          Chance of hitting the target: {pct(plan?.p_hit_target)}
        </span>
        <span className="absolute left-[19px] top-[277px] font-medium text-brand text-[13px] leading-[1.45]">
          Review your plan&nbsp;&nbsp;→
        </span>
      </button>

      <h2 className="absolute left-[56px] top-[682px] font-semibold text-ink text-[20px] leading-[1.45]">
        How to read this
      </h2>
      {EXPLAINERS.map((text, i) => (
        <p
          key={i}
          className="absolute left-[56px] text-muted text-[14px] leading-[1.45]"
          style={{ top: `${725 + i * 36}px` }}
        >
          {text}
        </p>
      ))}

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        {plan ? `Quant engine${plan.stub ? ' (stub: sample pricing)' : ''} · Plan ${plan.plan_id}` : DASH}
      </p>
    </Page>
  )
}
