import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA, Sources, Stub, useStub } from '../components/Truth'
import { useGo, useToast } from '../lib/ui'
import { useOverview } from '../lib/store'
import { financingModel, planRows, planSummary } from '../lib/viewModels'

// Strict: totals and allocation from the plan; accounts named as the backend names them; Nessie stub marked STUB.
export default function FinancingApproval() {
  const navigate = useNavigate()
  const go = useGo()
  const [consent, setConsent] = useState(false)
  const run = useOverview()
  const toast = useToast()
  const { engine, nessie } = useStub()
  const [approving, setApproving] = useState(false)
  const fin = financingModel(run.layout, run.state)
  const allocations = (planRows(run.layout) || []).map((r) => ({ name: r.name, bills: r.coverage, amount: r.cost }))
  const summary = planSummary(run.layout)
  const nBills = fin?.bills?.length || allocations.length
  const nUpgrades = summary?.upgrades
  const steps = [
    { n: '01', title: 'Open your Retrofit Reserve', desc: 'Keep retrofit funds separate from day-to-day spending.' },
    { n: '02', title: 'Transfer the approved investment', desc: 'Move the exact approved investment into the reserve.' },
    { n: '03', title: 'Create contractor bills', desc: nUpgrades ? `Allocate the funds to the ${nUpgrades} upgrades in your plan.` : 'Allocate the funds to the upgrades in your plan.' },
  ]
  const approve = async () => {
    if (!fin?.planId) return
    setApproving(true)
    try {
      await run.act('approve', { plan_id: fin.planId })
      navigate('/funding-confirmation')
    } catch (e) {
      toast(e.status === 409 ? 'The plan changed; review it again before approving.' : `Approval failed: ${e.message}`.slice(0, 90))
    } finally { setApproving(false) }
  }

  return (
    <Page active="plan">
      <button
        type="button"
        onClick={() => navigate('/plan')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;Your plan
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        Ready when you are.
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        Review the funding. Nothing moves until you approve.
      </p>
      <p className="absolute left-[1211px] top-[159px] font-medium text-brand text-[14px]">
        {fin?.executed ? 'Approved' : 'Awaiting your approval'}
      </p>

      {/* Funding breakdown */}
      <section className="absolute left-[56px] top-[265px] w-[816px] h-[350px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[20px]">
          Where your investment goes
        </p>
        <p className="absolute left-0 top-[34px] text-muted text-[13px]">
          {summary ? summary.count : `Upgrades ${NA}`}
        </p>
        <p className="absolute left-0 top-[91px] text-muted text-[12px]">Upgrade bundle</p>
        <p className="absolute left-[394px] top-[91px] text-muted text-[12px]">Coverage</p>
        <p className="absolute left-[670px] top-[91px] text-muted text-[12px]">Allocation</p>
        {!allocations.length && <p className="absolute left-0 top-[136px] text-muted text-[13px]">No upgrades to fund.</p>}
        <div className="absolute left-0 top-[118px] w-[816px] h-[170px] overflow-y-auto">
          {allocations.map((a) => (
            <div key={a.name} className="relative h-[40px] border-t border-line">
              <p className="absolute left-0 top-[10px] font-medium text-ink text-[15px]">{a.name}</p>
              <p className="absolute left-[394px] top-[11px] text-muted text-[13px]">{a.bills}</p>
              <p className="absolute left-[670px] top-[10px] text-ink text-[15px]">{a.amount}{engine && a.amount !== NA && <Stub />}</p>
            </div>
          ))}
        </div>
        <div className="absolute left-0 top-[297px] w-[816px] h-px bg-line" />
        <p className="absolute left-0 top-[318px] font-medium text-ink text-[15px]">Total to fund</p>
        <p className="absolute left-[650px] top-[313px] font-semibold text-ink text-[22px]">{fin ? fin.total : NA}{engine && fin && <Stub />}</p>
      </section>

      {/* Approval summary card */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[548px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[28px] top-[25px] font-semibold text-ink text-[20px]">
          Fund your retrofit plan
        </p>
        <p className="absolute left-[28px] top-[74px] text-muted text-[13px]">Amount to transfer</p>
        <p className="absolute left-[28px] top-[99px] font-semibold text-ink text-[34px]">{fin ? fin.total : NA}{engine && fin && <Stub />}</p>

        <p className="absolute left-[28px] top-[166px] text-muted text-[12px]">From</p>
        <button
          type="button"
          onClick={() => go('/funding-account')}
          className="absolute left-[28px] top-[190px] w-[384px] h-[56px] rounded-[5px] bg-white border border-line text-left overflow-hidden"
        >
          <span className="absolute left-[13px] top-[11px] font-medium text-ink text-[14px]">
            Operating account{nessie && <Stub title="Simulated account (stub Nessie)" />}
          </span>
          <span className="absolute left-[13px] top-[33px] text-muted text-[11px]">
            {nessie ? 'Simulated (stub Nessie)' : 'Nessie sandbox'} · balance {NA}
          </span>
          <span className="absolute left-[331px] top-[19px] text-muted text-[11px]">Details</span>
        </button>

        <p className="absolute left-[28px] top-[269px] text-muted text-[12px]">To</p>
        <p className="absolute left-[28px] top-[292px] font-medium text-ink text-[16px]">Hawk Lens Retrofit Reserve</p>
        <p className="absolute left-[28px] top-[320px] text-muted text-[12px]">
          A dedicated account, opened (or reused) on approval.
        </p>

        <div className="absolute left-[28px] top-[357px] w-[384px] h-px bg-line" />

        <button
          type="button"
          role="checkbox"
          aria-checked={consent}
          onClick={() => setConsent((v) => !v)}
          className="absolute left-[22px] top-[370px] w-[396px] h-[62px] text-left"
        >
          <span
            className={`absolute left-[6px] top-[12px] w-[18px] h-[18px] rounded-[3px] border flex items-center justify-center text-white text-[12px] ${
              consent ? 'bg-brand border-brand' : 'bg-white border-[#9ca89a]'
            }`}
          >
            {consent ? '✓' : ''}
          </span>
          <span className="absolute left-[37px] top-[10px] text-ink text-[13px] leading-[21px]">
            I approve this transfer and the creation
            <br />
            of {nBills} contractor bill{nBills === 1 ? '' : 's'} for this plan.
          </span>
        </button>

        <button
          type="button"
          disabled={!consent || approving || !fin?.planId}
          onClick={approve}
          className={`absolute left-[28px] top-[448px] w-[384px] h-[47px] rounded-[6px] text-[14px] font-medium transition ${
            consent && fin?.planId
              ? 'bg-brand text-white hover:brightness-110 active:brightness-95'
              : 'bg-[#dde5d7] text-[#65765e] cursor-not-allowed'
          }`}
        >
          {approving ? 'Approving…' : 'Approve & fund'}
        </button>
        <p className="absolute left-[28px] top-[515px] text-muted text-[11px]">
          {fin?.planId ? 'Confirm above to continue. No money has moved.' : `Plan id ${NA}: approval is disabled.`}
        </p>
      </section>

      <section className="absolute left-[56px] top-[674px] w-[816px] h-[210px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[18px]">
          What happens after approval
        </p>
        {steps.map((s, i) => {
          const top = 44 + i * 53
          return (
            <div key={s.n}>
              <p className="absolute left-0 font-medium text-brand text-[12px]" style={{ top: `${top + 1}px` }}>{s.n}</p>
              <p className="absolute left-[38px] font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>{s.title}</p>
              <p className="absolute left-[38px] text-muted text-[12px]" style={{ top: `${top + 23}px` }}>{s.desc}</p>
            </div>
          )
        })}
      </section>

      <Sources banking />
      <button
        type="button"
        onClick={() => go('/investment-memo')}
        className="absolute left-[1197px] top-[947px] text-brand text-[12px] hover:underline"
      >
        Review investment memo&nbsp;&nbsp;→
      </button>
    </Page>
  )
}
