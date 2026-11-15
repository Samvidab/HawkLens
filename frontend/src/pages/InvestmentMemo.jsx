import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { isPriced, usePlan } from '../lib/plan'
import { pct, plural, signedUsd, tonnes, usd } from '../lib/format'

export default function InvestmentMemo() {
  const navigate = useNavigate()
  // Same persisted plan as every other page: GET /plan.
  const { plan, loaded } = usePlan()
  const priced = isPriced(plan)
  const items = plan?.line_items || []
  const nBuildings = new Set(items.map((r) => r.building_id)).size
  const executed = Boolean(plan?.funding?.executed)
  const METRICS = [
    ['Upfront investment', usd(plan?.total_upfront)],
    ['Expected lifetime net value', signedUsd(plan?.exp_npv)],
    ['Chance of hitting the target', pct(plan?.p_hit_target)],
  ]

  return (
    <Page nav={false}>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1207px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to documents&nbsp;&nbsp;×
      </button>

      {/* Memo preview card (scaled-up version of the Documents preview) */}
      <section className="absolute left-[412px] top-[120px] w-[614.88px] h-[762.5px] rounded-[8.54px] border-[1.22px] border-line bg-white overflow-hidden">
        <div className="absolute left-0 top-0 w-full h-[57.34px] bg-[#f5f7f2]">
          <p className="absolute left-[30.5px] top-[20.74px] font-medium text-muted text-[12.2px] tracking-[1.22px]">
            DOCUMENT PREVIEW
          </p>
          <p className="absolute left-[533.14px] top-[20.74px] text-muted text-[12.2px]">1 page</p>
        </div>
        <p className="absolute left-[35.38px] top-[93.94px] font-semibold text-brand text-[15.86px]">
          Hawk Lens
        </p>
        <p className="absolute left-[35.38px] top-[135.42px] font-semibold text-ink text-[32.94px]">
          Investment memo
        </p>
        <p className="absolute left-[35.38px] top-[185.44px] text-muted text-[14.64px]">
          {plan?.goal?.city || 'Houston'} portfolio · {plan ? `Plan ${plan.plan_id}` : 'No plan yet'}
        </p>
        <div className="absolute left-[35.38px] top-[225.7px] w-[541.68px] h-[1.22px] bg-line" />
        <p className="absolute left-[35.38px] top-[257.42px] font-semibold text-ink text-[19.52px]">
          Recommendation
        </p>
        <p className="absolute left-[35.38px] top-[296.46px] w-[541.68px] text-muted text-[13px] leading-[28.06px]">
          {!loaded ? (
            'Loading plan…'
          ) : !plan ? (
            'No plan yet. Run the survey to price one.'
          ) : !priced ? (
            `Not priced: ${plan.reason}`
          ) : (
            <>
              {plan.status === 'ok' ? 'Fund' : 'Do not fund yet:'} {plural(items.length, 'upgrade')} across{' '}
              {plural(nBuildings, 'building')} for a {plan.goal?.target_pct}% CO₂ target.
              <br />
              Expected annual cut: {tonnes(plan.tonnes_per_year, ' tonnes CO₂')}
              {plan.status === 'infeasible' ? ` (${tonnes(plan.shortfall_tonnes, ' t/yr')} short).` : '.'}
            </>
          )}
        </p>
        {METRICS.map(([label, value], i) => {
          const top = 383.08 + i * 46.36
          return (
            <div key={label}>
              <p className="absolute left-[35.38px] text-muted text-[14.64px]" style={{ top: `${top}px` }}>
                {label}
              </p>
              <p
                className="absolute left-[456.28px] font-medium text-ink text-[18.3px]"
                style={{ top: `${top - 1.22}px` }}
              >
                {value}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[35.38px] top-[529.48px] w-[541.68px] h-[1.22px] bg-line" />
        <p className="absolute left-[35.38px] top-[557.54px] font-medium text-ink text-[17.08px]">
          Before you commit
        </p>
        <p className="absolute left-[35.38px] top-[592.92px] text-muted text-[14.64px] leading-[25.62px]">
          The worst 5% of scenarios average {signedUsd(plan?.cvar5)} NPV; chance of a loss {pct(plan?.p_loss, 1)}.
          <br />
          Site checks and contractor quotes are still required.
          <br />
          Savings interactions are not yet modeled.
        </p>
        <button
          type="button"
          onClick={() => navigate('/demo-document-notice')}
          className="absolute left-[35.38px] top-[711.26px] font-medium text-brand text-[15.86px] hover:underline"
        >
          Download memo&nbsp;&nbsp;↓
        </button>
        <p className="absolute left-[425.78px] top-[713.7px] text-muted text-[13.42px]">
          {executed ? 'Approved · funded' : 'Draft · Not approved'}
        </p>
      </section>
    </Page>
  )
}
