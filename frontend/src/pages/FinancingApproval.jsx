import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo } from '../lib/ui'

const ALLOCATIONS = [
  { name: 'LED retrofit', bills: '7 buildings · 7 bills', amount: '$120k' },
  { name: 'Rooftop solar', bills: '6 buildings · 6 bills', amount: '$760k' },
  { name: 'Heat pump conversion', bills: '4 buildings · 4 bills', amount: '$400k' },
]

const STEPS = [
  { n: '01', title: 'Open your Retrofit Reserve', desc: 'Keep retrofit funds separate from day-to-day spending.' },
  { n: '02', title: 'Transfer the approved investment', desc: 'Move the exact approved investment into the reserve.' },
  { n: '03', title: 'Create contractor bills', desc: 'Allocate the funds to the 18 upgrades in your plan.' },
]

export default function FinancingApproval() {
  const navigate = useNavigate()
  const go = useGo()
  const [consent, setConsent] = useState(false)

  return (
    <Page active="plan">
      {/* Header */}
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
        Awaiting your approval
      </p>

      {/* Funding breakdown */}
      <section className="absolute left-[56px] top-[265px] w-[816px] h-[350px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[20px]">
          Where your investment goes
        </p>
        <p className="absolute left-0 top-[34px] text-muted text-[13px]">
          18 upgrades across 7 buildings
        </p>
        <p className="absolute left-0 top-[91px] text-muted text-[12px]">Upgrade bundle</p>
        <p className="absolute left-[394px] top-[91px] text-muted text-[12px]">Contractor bills</p>
        <p className="absolute left-[670px] top-[91px] text-muted text-[12px]">Allocation</p>
        {ALLOCATIONS.map((a, i) => {
          const top = 136 + i * 57
          return (
            <div key={a.name}>
              <div className="absolute left-0 w-[816px] h-px bg-line" style={{ top: `${top - 18}px` }} />
              <p className="absolute left-0 font-medium text-ink text-[15px]" style={{ top: `${top}px` }}>
                {a.name}
              </p>
              <p className="absolute left-[394px] text-muted text-[13px]" style={{ top: `${top}px` }}>
                {a.bills}
              </p>
              <p className="absolute left-[670px] text-ink text-[15px]" style={{ top: `${top}px` }}>
                {a.amount}
              </p>
            </div>
          )
        })}
        <div className="absolute left-0 top-[297px] w-[816px] h-px bg-line" />
        <p className="absolute left-0 top-[318px] font-medium text-ink text-[15px]">Total to fund</p>
        <p className="absolute left-[650px] top-[313px] font-semibold text-ink text-[22px]">$1280k</p>
      </section>

      {/* Approval summary card */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[548px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[28px] top-[25px] font-semibold text-ink text-[20px]">
          Fund your retrofit plan
        </p>
        <p className="absolute left-[28px] top-[74px] text-muted text-[13px]">Amount to transfer</p>
        <p className="absolute left-[28px] top-[99px] font-semibold text-ink text-[34px]">$1280k</p>

        <p className="absolute left-[28px] top-[166px] text-muted text-[12px]">From</p>
        <button
          type="button"
          onClick={() => go('/funding-account')}
          className="absolute left-[28px] top-[190px] w-[384px] h-[56px] rounded-[5px] bg-white border border-line text-left overflow-hidden"
        >
          <span className="absolute left-[13px] top-[11px] font-medium text-ink text-[14px]">
            Owner checking · •• 2048
          </span>
          <span className="absolute left-[13px] top-[33px] text-muted text-[11px]">
            Available $2,400,000 · Nessie sandbox
          </span>
          <span className="absolute left-[331px] top-[19px] text-muted text-[11px]">Details</span>
        </button>

        <p className="absolute left-[28px] top-[269px] text-muted text-[12px]">To</p>
        <p className="absolute left-[28px] top-[292px] font-medium text-ink text-[16px]">Retrofit Reserve</p>
        <p className="absolute left-[28px] top-[320px] text-muted text-[12px]">
          A dedicated account, created after approval.
        </p>

        <div className="absolute left-[28px] top-[357px] w-[384px] h-px bg-line" />

        {/* Consent toggle (hotspot covers checkbox + label) */}
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
            of 18 contractor bills for this plan.
          </span>
        </button>

        <button
          type="button"
          disabled={!consent}
          onClick={() => navigate('/funding-confirmation')}
          className={`absolute left-[28px] top-[448px] w-[384px] h-[47px] rounded-[6px] text-[14px] font-medium transition ${
            consent
              ? 'bg-brand text-white hover:brightness-110 active:brightness-95'
              : 'bg-[#dde5d7] text-[#65765e] cursor-not-allowed'
          }`}
        >
          Approve &amp; fund
        </button>
        <p className="absolute left-[28px] top-[515px] text-muted text-[11px]">
          Confirm above to continue. No money has moved.
        </p>
      </section>

      {/* Safeguards */}
      <section className="absolute left-[56px] top-[674px] w-[816px] h-[210px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[18px]">
          What happens after approval
        </p>
        {STEPS.map((s, i) => {
          const top = 44 + i * 53
          return (
            <div key={s.n}>
              <p className="absolute left-0 font-medium text-brand text-[12px]" style={{ top: `${top + 1}px` }}>
                {s.n}
              </p>
              <p className="absolute left-[38px] font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>
                {s.title}
              </p>
              <p className="absolute left-[38px] text-muted text-[12px]" style={{ top: `${top + 23}px` }}>
                {s.desc}
              </p>
            </div>
          )
        })}
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        Illustrative data · Nessie sandbox · No real funds
      </p>
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
