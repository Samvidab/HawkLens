import { useNavigate } from 'react-router-dom'
import { useGoal } from '../lib/ui'
import { deriveModel } from '../lib/model'
import Page from '../components/Page'

// NPV histogram bins: [left, top, height, loss?] — loss bins use the warning color.
const BINS = [
  [56, 260.21, 1.794, true],
  [86.78, 257.2, 4.805, true],
  [117.55, 250.65, 11.352, true],
  [148.33, 238.34, 23.66, true],
  [179.11, 218.5, 43.503],
  [209.89, 191.43, 70.567],
  [240.67, 161.02, 100.985],
  [271.45, 134.51, 127.493],
  [302.22, 120, 142],
  [333, 122.47, 139.53],
  [363.78, 141.04, 120.956],
  [394.55, 169.5, 92.504],
  [425.33, 199.59, 62.412],
  [456.11, 224.85, 37.149],
  [486.89, 242.49, 19.507],
  [517.67, 252.96, 9.036],
  [548.45, 258.31, 3.693],
  [579.22, 260.67, 1.331],
]

const AXIS = [
  ['−$400k', 47],
  ['$0k', 170.11],
  ['$400k', 293.22],
  ['$800k', 416.33],
  ['$1200k', 539.44],
]

const EXPLAINERS = [
  'A bar counts simulated futures in a range of lifetime net values. Below zero means a loss.',
  'Worst 5% average is the mean result in the least favorable scenarios—not the worst single outcome.',
  'A changed selection needs a new simulation. The prototype never presents stale risk statistics as fresh results.',
]

export default function RiskAndTarget() {
  const navigate = useNavigate()
  const { target } = useGoal()
  const model = deriveModel(target)

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
          Lifetime NPV distribution · Baseline sample plan
        </p>
        <p className="absolute left-[637px] top-[17px] font-semibold text-brand text-[30px] leading-[1.45]">
          +$486k
        </p>
        <p className="absolute left-[637px] top-[62px] text-muted text-[11px] leading-[1.45]">
          Expected net value
        </p>

        {BINS.map(([left, top, height, loss], i) => (
          <div
            key={i}
            className={`absolute rounded-[2px] ${loss ? 'bg-[#7a693b]' : 'bg-brand'}`}
            style={{ left: `${left}px`, top: `${top}px`, width: '27.778px', height: `${height}px` }}
          />
        ))}

        {/* break-even line */}
        <div className="absolute left-[178.11px] top-[104px] w-px h-[158px] bg-[#7a693b]" />
        <p className="absolute left-[151.11px] top-[84px] text-[#7a693b] text-[11px] leading-[1.45]">
          Break even
        </p>

        {AXIS.map(([label, left]) => (
          <p
            key={label}
            className="absolute top-[272px] text-muted text-[11px] leading-[1.45]"
            style={{ left: `${left}px` }}
          >
            {label}
          </p>
        ))}

        <p className="absolute left-[637px] top-[125px] font-semibold text-[#7a693b] text-[20px] leading-[1.45]">
          4.2%
        </p>
        <p className="absolute left-[637px] top-[157px] text-muted text-[11px] leading-[1.45]">
          Chance of a loss
        </p>
        <p className="absolute left-[637px] top-[204px] font-semibold text-ink text-[20px] leading-[1.45]">
          −$94k
        </p>
        <p className="absolute left-[637px] top-[238px] text-muted text-[11px] leading-[1.45]">
          Worst 5% average
        </p>
        <p className="absolute left-[19px] top-[327px] text-muted text-[11px] leading-[1.45]">
          Illustrative baseline · 10,000 scenarios · Run again after changing the plan.
        </p>
      </section>

      {/* Target gap card */}
      <button
        type="button"
        onClick={() => navigate('/plan')}
        className="absolute left-[944px] top-[265px] w-[440px] h-[320px] rounded-[8px] border border-line bg-white text-left"
      >
        <span className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Your target is covered
        </span>
        <span className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          Current goal · Expected carbon cuts cover the target
        </span>
        <span className="absolute left-[19px] top-[75px] font-semibold text-brand text-[30px] leading-[1.45]">
          72
        </span>
        <span className="absolute left-[79px] top-[92px] text-muted text-[11px] leading-[1.45]">
          tonnes per year above your goal
        </span>
        <span className="absolute left-[19px] top-[139px] w-[400px] h-px bg-line" />
        <span className="absolute left-[19px] top-[165px] text-ink text-[14px] leading-[1.45]">
          {model.annualLabel}
        </span>
        <span className="absolute left-[19px] top-[203px] text-muted text-[11px] leading-[1.45]">
          See the risk panel for the current simulation status.
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
        Illustrative baseline · No live Monte Carlo execution
      </p>
    </Page>
  )
}
