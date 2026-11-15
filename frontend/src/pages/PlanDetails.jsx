import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo, useGoal } from '../lib/ui'
import { BUDGET_K, deriveModel } from '../lib/model'

// Abatement-curve bars (baseline at the $0 line, y=165 within the 290px card).
const CUT_BARS = [
  { name: 'LED · offices', left: 65, width: 37.811, height: 34.679 },
  { name: 'LED · retail', left: 105.81, width: 37.811, height: 34.679 },
  { name: 'Solar · group A', left: 146.62, width: 99.027, height: 10.183 },
  { name: 'Solar · group B', left: 248.65, width: 99.027, height: 10.183 },
  { name: 'Heat pumps · A', left: 350.68, width: 73.52, height: 4.874 },
  { name: 'Heat pumps · B', left: 427.2, width: 73.52, height: 4.874 },
]
// Above-zero (net-cost) opportunity bars, drawn growing upward from their top.
const COST_BARS = [
  { name: 'Window upgrades', left: 503.72, top: 108.6, width: 60.767, height: 56.4 },
  { name: 'Insulation', left: 567.48, top: 87.45, width: 56.516, height: 77.55 },
]

const ACTIVITY = [
  {
    time: '09:42 · Verifier',
    line: 'Midtown roof verified · Confidence 0.91',
    meta: 'Vexcel · Evidence 12',
  },
  {
    time: '09:42 · Interior inspector',
    line: 'Level 2 fluorescent fixtures flagged.',
    meta: 'Matterport · Panorama 04',
  },
  {
    time: '09:43 · Pricing agent',
    line: '18 upgrades across 7 buildings',
    meta: 'Baseline sample · 10,000 scenarios',
  },
]

const ROWS = [
  { name: 'LED retrofit', coverage: '7 buildings · 7 bills', cost: '$120k', co2: '192 tCO₂', npv: '+$170k' },
  { name: 'Rooftop solar', coverage: '6 buildings · 6 bills', cost: '$760k', co2: '480 tCO₂', npv: '+$260k' },
  { name: 'Heat pump conversion', coverage: '4 buildings · 4 bills', cost: '$400k', co2: '360 tCO₂', npv: '+$56k' },
]

// Metric strip, derived from the shared/persisted target so the Plan page reflects
// whatever the owner set on the dashboard.
function buildMetrics(model) {
  return [
    {
      label: 'Annual CO₂ reduction',
      value: model.annualLabel,
      sub: model.covered ? 'Your goal is covered' : 'Over your budget',
      left: 0,
    },
    { label: 'Lifetime net value', value: model.netValueLabel, sub: 'After retrofit costs', left: 338 },
    {
      label: 'Upfront investment',
      value: model.investmentLabel,
      sub: `Budget $${BUDGET_K}k · Balanced risk`,
      left: 676,
    },
    {
      label: 'Baseline simulation confidence',
      value: `${model.confidence}%`,
      sub: 'Baseline sample · 10,000 scenarios',
      left: 1014,
    },
  ]
}

export default function PlanDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const { target } = useGoal()
  const model = deriveModel(target)
  const METRICS = buildMetrics(model)

  return (
    <Page active="plan">
      <h1 className="absolute left-[56px] top-[127px] whitespace-nowrap font-semibold text-ink text-[32px]">
        What&rsquo;s in your plan
      </h1>
      <p className="absolute left-[57px] top-[176px] whitespace-nowrap text-muted text-[14px]">
        18 upgrades · {target}% reduction goal
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
        <p className="absolute left-[16px] top-[207px] text-muted text-[9px]">−$100</p>
        <div className="absolute left-[64px] top-[165px] w-[562px] h-px bg-[#9aa68f]" />
        <p className="absolute left-[16px] top-[160px] text-muted text-[9px]">$0</p>
        <div className="absolute left-[64px] top-[118px] w-[562px] h-px bg-[#e7ebe2]" />
        <p className="absolute left-[16px] top-[113px] text-muted text-[9px]">$100</p>

        {/* profitable (below-zero) bars grow downward from the $0 line */}
        {CUT_BARS.map((b) => (
          <div
            key={b.name}
            title={b.name}
            className="absolute bg-brand rounded-[2px]"
            style={{ left: `${b.left}px`, top: '165px', width: `${b.width}px`, height: `${b.height}px` }}
          />
        ))}
        {/* net-cost opportunity bars */}
        {COST_BARS.map((b) => (
          <div
            key={b.name}
            title={b.name}
            className="absolute bg-[#dde4d5] border border-[#b9c5ae] rounded-[2px]"
            style={{ left: `${b.left}px`, top: `${b.top}px`, width: `${b.width}px`, height: `${b.height}px` }}
          />
        ))}
        <div className="absolute left-[472.11px] top-[110px] w-px h-[131px] bg-[#7a693b]" />
        <p className="absolute left-[442.11px] top-[93px] font-medium text-[#7a693b] text-[10px]">
          Reference: {target}%
        </p>
        <p className="absolute left-[59px] top-[237px] text-muted text-[9px]">0</p>
        <p className="absolute left-[229.05px] top-[237px] text-muted text-[9px]">400</p>
        <p className="absolute left-[399.09px] top-[237px] text-muted text-[9px]">800</p>
        <p className="absolute left-[569.14px] top-[237px] text-muted text-[9px]">1200</p>

        {/* legend */}
        <div className="absolute left-[21px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#416b4d]" />
        <p className="absolute left-[36px] top-[268px] text-muted text-[10px]">Available upgrades</p>
        <div className="absolute left-[144px] top-[270px] w-[9px] h-[9px] rounded-[2px] bg-[#dde4d5]" />
        <p className="absolute left-[159px] top-[268px] text-muted text-[10px]">Additional opportunities</p>

        {/* right note */}
        <div className="absolute left-[651px] top-[83px] w-px h-[182px] bg-[#e7ebe2]" />
        <p className="absolute left-[673px] top-[92px] font-medium text-muted text-[10px] tracking-[0.6px]">
          PROFITABLE CUTS
        </p>
        <p className="absolute left-[673px] top-[113px] font-semibold text-brand text-[31px]">1,032</p>
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
          <span className="ml-[12px] font-medium text-brand text-[10px]">7 / 7 ready</span>
        </div>
        <p className="absolute left-[21px] top-[44px] text-muted text-[12px]">
          Latest completed survey events
        </p>
        {ACTIVITY.map((a, i) => {
          const top = 82 + i * 57
          return (
            <div key={a.time}>
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
                {a.time}
              </p>
              <p className="absolute left-[48px] text-muted text-[11px]" style={{ top: `${top + 18}px` }}>
                {a.line}
              </p>
              <p className="absolute left-[48px] text-muted text-[9px]" style={{ top: `${top + 33}px` }}>
                {a.meta}
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
          18 upgrades across 7 buildings
        </p>
        <p className="absolute left-[919px] top-[20px] text-muted text-[11px]">
          Baseline downside: −$94k NPV
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
        {ROWS.map((r, i) => {
          const top = 90 + i * 33
          return (
            <div key={r.name}>
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
                {r.name}
              </button>
              <p className="absolute left-[417px] text-muted text-[12px]" style={{ top: `${top}px` }}>
                {r.coverage}
              </p>
              <p className="absolute left-[655px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                {r.cost}
              </p>
              <p className="absolute left-[895px] text-ink text-[12px]" style={{ top: `${top}px` }}>
                {r.co2}
              </p>
              <p className="absolute left-[1135px] font-medium text-brand text-[12px]" style={{ top: `${top}px` }}>
                {r.npv}
              </p>
            </div>
          )
        })}
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        Illustrative data · Review assumptions before approval
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
