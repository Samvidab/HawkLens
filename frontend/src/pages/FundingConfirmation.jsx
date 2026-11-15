import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA, Sources, Stub, useStub } from '../components/Truth'
import { useOverview } from '../lib/store'
import { financingModel, planSummary } from '../lib/viewModels'

// Strict: says "funded" only when the backend's financing card is executed; ids and totals come from it.
export default function FundingConfirmation() {
  const navigate = useNavigate()
  const run = useOverview()
  const { engine, nessie } = useStub()
  const fin = financingModel(run.layout, run.state)
  const ids = fin?.nessieIds || {}
  const tail = (v) => (v ? `…${String(v).slice(-6)}` : NA)
  const sum = planSummary(run.layout)
  const executed = !!fin?.executed

  return (
    <Page active="plan">
      <section className="absolute left-[300px] top-[214px] w-[840px] h-[556px] rounded-[10px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[393px] top-[31px] font-semibold text-brand text-[36px]">{executed ? '✓' : '…'}</p>
        <p className="absolute left-0 w-full text-center top-[94px] font-semibold text-ink text-[30px]">
          {executed ? 'Your retrofit plan is funded.' : 'The plan is not funded yet.'}
        </p>
        <p className="absolute left-0 w-full text-center top-[142px] text-muted text-[13px]">
          {executed
            ? (nessie
              ? <>Simulated booking (stub Nessie): nothing was sent to a bank<Stub title="Simulated booking" /></>
              : `Recorded in the Nessie sandbox (no real money) · account ${tail(ids.account)} · transfer ${tail(ids.transfer)}`)
            : 'Approve the plan on the funding screen first.'}
        </p>

        <p className="absolute left-[46px] top-[202px] text-muted text-[14px]">Retrofit Reserve</p>
        <p className="absolute left-[554px] top-[202px] font-medium text-brand text-[14px]">
          {executed ? (nessie ? 'Simulated' : `Nessie sandbox ${tail(ids.account)}`) : 'Not opened'}
        </p>

        <p className="absolute left-[46px] top-[247px] text-muted text-[14px]">Reserved for upgrades</p>
        <p className="absolute left-[554px] top-[242px] font-semibold text-ink text-[24px]">{fin ? fin.total : NA}{engine && fin && <Stub />}</p>

        <p className="absolute left-[46px] top-[294px] text-muted text-[14px]">Contractor allocation</p>
        <p className="absolute left-[454px] top-[294px] text-ink text-[13px]">
          {executed && fin?.bills ? `${fin.bills.length} bill${fin.bills.length === 1 ? '' : 's'} · ` : ''}{sum ? sum.count : `Upgrades ${NA}`}
        </p>

        <div className="absolute left-[46px] top-[338px] w-[748px] h-px bg-[#dde3d8]" />
        <p className="absolute left-[46px] top-[363px] text-muted text-[14px]">
          The memo written for this plan is in Documents.
        </p>

        <button
          type="button"
          onClick={() => navigate(executed ? '/documents' : '/financing-approval')}
          className="absolute left-[46px] top-[414px] w-[355px] h-[46px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
        >
          {executed ? 'View documents' : 'Go to approval'}
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
          className="absolute left-0 w-full text-center top-[502px] font-medium text-brand text-[13px] hover:underline"
        >
          Start a new survey
        </button>
      </section>
      <Sources banking />
    </Page>
  )
}
