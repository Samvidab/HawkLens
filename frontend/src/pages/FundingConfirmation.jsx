import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { usePlan } from '../lib/plan'
import { plural, usdExact } from '../lib/format'

export default function FundingConfirmation() {
  const navigate = useNavigate()
  const { plan, loaded } = usePlan()
  const fin = plan?.financing || {}
  const executed = Boolean(plan?.funding?.executed)
  const simulated = fin.simulated ?? plan?.funding?.simulated ?? true
  const reserve = fin.nessie_ids?.account
  const bills = plan?.bills || []

  return (
    <Page active="plan">
      <section className="absolute left-[300px] top-[214px] w-[840px] h-[556px] rounded-[10px] bg-[#f5f7f2] overflow-hidden">
        {executed && (
          <p className="absolute left-0 right-0 top-[31px] text-center font-semibold text-brand text-[36px]">✓</p>
        )}
        <p className="absolute left-0 right-0 top-[94px] text-center font-semibold text-ink text-[30px]">
          {!loaded ? 'Loading…' : executed ? 'Your retrofit plan is funded.' : 'This plan is not funded yet.'}
        </p>
        <p className="absolute left-0 right-0 top-[142px] text-center text-muted text-[13px]">
          {!executed
            ? 'Approve the plan on the financing screen; nothing has been sent to Nessie.'
            : simulated
              ? 'Simulated funding (Nessie stub mode) · No real account or money movement'
              : 'Recorded through the Nessie API (Capital One sandbox)'}
        </p>

        <p className="absolute left-[46px] top-[202px] text-muted text-[14px]">Retrofit Reserve</p>
        <p className="absolute left-[554px] top-[202px] font-medium text-brand text-[14px]">
          {!executed ? 'Not created' : simulated ? 'Created (simulated)' : `Created · acct …${String(reserve).slice(-4)}`}
        </p>

        <p className="absolute left-[46px] top-[247px] text-muted text-[14px]">Reserved for upgrades</p>
        <p className="absolute left-[554px] top-[242px] font-semibold text-ink text-[24px]">
          {executed ? usdExact(fin.amount) : '—'}
        </p>

        <p className="absolute left-[46px] top-[294px] text-muted text-[14px]">Contractor allocation</p>
        <p className="absolute left-[554px] top-[294px] text-ink text-[13px]">
          {executed
            ? `${plural(bills.length, 'contractor bill')} · ${plural(plan?.selected?.length || 0, 'upgrade')}`
            : '—'}
        </p>

        <div className="absolute left-[46px] top-[338px] w-[748px] h-px bg-[#dde3d8]" />
        <p className="absolute left-[46px] top-[363px] text-muted text-[14px]">
          {plan ? `Plan ${plan.plan_id}. ` : ''}Keep the memo, survey and funding record together in Documents.
        </p>

        <button
          type="button"
          onClick={() => navigate(executed ? '/documents' : '/financing-approval')}
          className="absolute left-[46px] top-[414px] w-[355px] h-[46px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
        >
          {executed ? 'View documents' : 'Go to financing'}
        </button>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="absolute left-[439px] top-[414px] w-[355px] h-[46px] rounded-[6px] bg-model text-brand text-[14px] font-medium hover:brightness-95 transition"
        >
          Back to portfolio
        </button>
        <button
          type="button"
          onClick={() => navigate('/start-survey')}
          className="absolute left-0 right-0 mx-auto w-fit top-[502px] font-medium text-brand text-[13px] hover:underline"
        >
          Run a new survey
        </button>
      </section>
    </Page>
  )
}
