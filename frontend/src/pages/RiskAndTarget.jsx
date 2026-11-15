import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA, Sources, Stub, useStub } from '../components/Truth'
import { useOverview } from '../lib/store'
import { riskModel, targetModel, upgradeLabel, widget } from '../lib/viewModels'

const EXPLAINERS = [
  'A bar counts simulated futures in a range of lifetime net values. Below zero means a loss.',
  'Worst 5% average is the mean result in the least favorable 5% of simulated futures, not the worst single outcome.',
  'Every change to the plan is re-simulated; the numbers here belong to the plan currently shown.',
]

// Strict: histogram and target figures come only from the run's widgets; missing ones read "not available".
export default function RiskAndTarget() {
  const navigate = useNavigate()
  const run = useOverview()
  const stub = useStub().engine
  const rm = riskModel(run.layout)
  const tm = targetModel(run.layout)
  const gap = widget(run.layout, 'target_gap_card')
  const cheapest = gap?.cheapest_extra?.[0]
  const S = () => (stub ? <Stub /> : null)

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
        The simulated spread of outcomes for the current plan, and how it meets your target.
      </p>

      {/* Risk histogram */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[360px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          What could your return look like?
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          Lifetime NPV distribution · {rm ? (rm.scope === 'building' ? 'this building' : 'the whole plan') : NA}
        </p>
        <p className="absolute left-[637px] top-[17px] font-semibold text-brand text-[30px] leading-[1.45]">
          {rm ? rm.expNpv : NA}{rm && <S />}
        </p>
        <p className="absolute left-[637px] top-[62px] text-muted text-[11px] leading-[1.45]">
          Expected net value
        </p>

        {!rm && <p className="absolute left-[56px] top-[160px] text-muted text-[13px]">Distribution not available.</p>}
        {rm && rm.bars.map((b, i) => (
          <div
            key={i}
            className={`absolute rounded-[2px] ${b.loss ? 'bg-[#7a693b]' : 'bg-brand'}`}
            style={{ left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` }}
          />
        ))}

        {rm && rm.breakEven !== null && (
          <>
            <div className="absolute top-[104px] w-px h-[158px] bg-[#7a693b]" style={{ left: `${rm.breakEven}px` }} />
            <p className="absolute top-[84px] text-[#7a693b] text-[11px] leading-[1.45]" style={{ left: `${rm.breakEven - 27}px` }}>
              Break even
            </p>
          </>
        )}

        {rm && rm.axis.map((a) => (
          <p key={`${a.label}${a.left}`} className="absolute top-[272px] text-muted text-[11px] leading-[1.45]" style={{ left: `${a.left}px` }}>
            {a.label}
          </p>
        ))}

        <p className="absolute left-[637px] top-[125px] font-semibold text-[#7a693b] text-[20px] leading-[1.45]">
          {rm ? rm.pLoss : NA}{rm && <S />}
        </p>
        <p className="absolute left-[637px] top-[157px] text-muted text-[11px] leading-[1.45]">
          Chance of a loss
        </p>
        <p className="absolute left-[637px] top-[204px] font-semibold text-ink text-[20px] leading-[1.45]">
          {rm ? rm.worst5 : NA}{rm && <S />}
        </p>
        <p className="absolute left-[637px] top-[238px] text-muted text-[11px] leading-[1.45]">
          Worst 5% average
        </p>
        <p className="absolute left-[19px] top-[327px] text-muted text-[11px] leading-[1.45]">
          {rm ? `${rm.scenarios.toLocaleString('en-US')} scenarios shown in histogram` : `Scenarios ${NA}`} · {stub ? 'sample prices (stub engine)' : 'quant engine'}
        </p>
      </section>

      {/* Target gap card */}
      <button
        type="button"
        onClick={() => navigate('/plan')}
        className="absolute left-[944px] top-[265px] w-[440px] h-[320px] rounded-[8px] border border-line bg-white text-left"
      >
        <span className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          {!tm || tm.covered === null ? 'Target coverage not available' : tm.covered ? 'Your target is covered' : 'Your target is out of reach'}
        </span>
        <span className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          {tm ? `Current goal · ${tm.target}% needs ${tm.tonnesNeeded == null ? NA : `${tm.tonnesNeeded.toLocaleString('en-US')} tonnes a year`}` : `Goal ${NA}`}
        </span>
        <span className="absolute left-[19px] top-[75px] font-semibold text-brand text-[30px] leading-[1.45]">
          {tm && tm.covered !== null ? (tm.covered ? tm.surplus : tm.shortfall).toLocaleString('en-US') : NA}{tm && tm.covered !== null && <S />}
        </span>
        {tm && tm.covered !== null && (
          <span className="absolute left-[19px] top-[118px] text-muted text-[11px] leading-[1.45]">
            {tm.covered ? 'tonnes per year above your goal' : 'tonnes per year short of your goal'}
          </span>
        )}
        <span className="absolute left-[19px] top-[139px] w-[400px] h-px bg-line" />
        <span className="absolute left-[19px] top-[165px] text-ink text-[14px] leading-[1.45]">
          {tm ? tm.annualLabel : `Planned tonnes ${NA}`}
        </span>
        <span className="absolute left-[19px] top-[203px] text-muted text-[11px] leading-[1.45]">
          {cheapest
            ? `Cheapest extra cut: ${upgradeLabel(String(cheapest.upgrade_id).split(':')[1])} · ${Math.round(cheapest.tonnes_per_year)} t/yr`
            : tm && tm.covered === false ? 'No single extra upgrade can close the gap.' : ''}
        </span>
        <span className="absolute left-[19px] top-[277px] font-medium text-brand text-[13px] leading-[1.45]">
          Review your plan&nbsp;&nbsp;→
        </span>
      </button>

      <h2 className="absolute left-[56px] top-[682px] font-semibold text-ink text-[20px] leading-[1.45]">
        How to read this
      </h2>
      {EXPLAINERS.map((text, i) => (
        <p key={i} className="absolute left-[56px] text-muted text-[14px] leading-[1.45]" style={{ top: `${725 + i * 36}px` }}>
          {text}
        </p>
      ))}

      <button
        type="button"
        onClick={() => navigate('/assumptions')}
        className="absolute left-[56px] top-[840px] font-medium text-brand text-[13px] hover:underline"
      >
        Assumptions &amp; sources&nbsp;&nbsp;→
      </button>
      <Sources />
    </Page>
  )
}
