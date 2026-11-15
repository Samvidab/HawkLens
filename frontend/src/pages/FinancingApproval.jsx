import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo } from '../lib/ui'
import { fetchFundingAccount } from '../lib/api'
import { isPriced, usePlan } from '../lib/plan'
import { DASH, plural, typeLabel, usd, usdExact } from '../lib/format'

export default function FinancingApproval() {
  const navigate = useNavigate()
  const go = useGo()
  const { plan, loaded, loadError, busy, act } = usePlan()
  const [consent, setConsent] = useState(false)
  const [account, setAccount] = useState(null)
  const [accountError, setAccountError] = useState(null)
  const [approveError, setApproveError] = useState(null)
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    let alive = true
    fetchFundingAccount()
      .then((a) => alive && setAccount(a))
      .catch((e) => alive && setAccountError(e.message))
    return () => {
      alive = false
    }
  }, [])

  // A new plan (re-priced elsewhere) needs a fresh consent.
  useEffect(() => setConsent(false), [plan?.plan_id])

  const bundles = plan?.bundles || []
  const items = plan?.line_items || []
  const nBuildings = new Set(items.map((r) => r.building_id)).size
  const verdict = plan?.approval || { approvable: false, reasons: [plan ? 'no approval verdict' : 'no plan yet'], warnings: [] }
  const executed = Boolean(plan?.funding?.executed)
  const simulated = plan?.funding ? plan.funding.simulated : account?.simulated ?? true
  const canApprove = consent && verdict.approvable && !executed && !busy && !approving

  const statusText = executed
    ? 'Funded'
    : !loaded
      ? 'Loading…'
      : verdict.approvable
        ? 'Awaiting your approval'
        : 'Not ready to approve'

  async function approve() {
    setApproveError(null)
    setApproving(true)
    const r = await act('approve', { plan_id: plan.plan_id })
    setApproving(false)
    if (r.ok) navigate('/funding-confirmation')
    else setApproveError(r.error?.message || 'Approval failed')
  }

  const accountLine = accountError
    ? `Account unavailable: ${accountError}`
    : !account
      ? 'Loading account…'
      : account.simulated
        ? 'Nessie stub mode · simulated, no real account'
        : account.configured
          ? `Available ${usdExact(account.balance)} · Nessie live API`
          : account.error || 'Nessie source account not configured'

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
        {executed ? 'Funding recorded.' : 'Ready when you are.'}
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        Review the funding. Nothing moves until you approve.
      </p>
      <p
        className={`absolute right-[56px] top-[159px] font-medium text-[14px] ${
          verdict.approvable || executed ? 'text-brand' : 'text-[#b4532f]'
        }`}
      >
        {statusText}
      </p>

      {/* Funding breakdown */}
      <section className="absolute left-[56px] top-[265px] w-[816px] h-[350px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[20px]">
          Where your investment goes
        </p>
        <p className="absolute left-0 top-[34px] text-muted text-[13px]">
          {loadError
            ? `Plan unavailable: ${loadError}`
            : isPriced(plan)
              ? `${plural(items.length, 'upgrade')} across ${plural(nBuildings, 'building')} · plan ${plan.plan_id}`
              : plan?.status === 'no_data'
                ? `Not priced: ${plan.reason}`
                : 'No plan yet'}
        </p>
        <p className="absolute left-0 top-[91px] text-muted text-[12px]">Upgrade bundle</p>
        <p className="absolute left-[394px] top-[91px] text-muted text-[12px]">Contractor bill</p>
        <p className="absolute left-[670px] top-[91px] text-muted text-[12px]">Allocation</p>
        <div className="absolute left-0 top-[118px] w-[816px] h-[176px] overflow-y-auto">
          {bundles.map((a, i) => {
            const top = 18 + i * 57
            return (
              <div key={a.type}>
                <div className="absolute left-0 w-[816px] h-px bg-line" style={{ top: `${top - 18}px` }} />
                <p className="absolute left-0 font-medium text-ink text-[15px]" style={{ top: `${top}px` }}>
                  {typeLabel(a.type)}
                </p>
                <p className="absolute left-[394px] text-muted text-[13px]" style={{ top: `${top}px` }}>
                  {a.contractor || DASH} · {plural(a.n_buildings, 'building')}
                </p>
                <p className="absolute left-[670px] text-ink text-[15px]" style={{ top: `${top}px` }}>
                  {usd(a.upfront_usd)}
                </p>
              </div>
            )
          })}
          <div style={{ height: `${18 + bundles.length * 57}px` }} />
        </div>
        <div className="absolute left-0 top-[297px] w-[816px] h-px bg-line" />
        <p className="absolute left-0 top-[318px] font-medium text-ink text-[15px]">
          Total to fund
          {bundles.length > 0 && (
            <span className="text-muted text-[12px] font-normal">
              {' '}· {plural(bundles.length, 'contractor bill')}
              {bundles.length > 3 ? ` (scroll for ${bundles.length - 3} more)` : ''}
            </span>
          )}
          {plan && plan.reconciles === false && isPriced(plan) ? ' · line items do not reconcile' : ''}
        </p>
        <p className="absolute right-0 top-[313px] font-semibold text-ink text-[22px]">{usd(plan?.total_upfront)}</p>
      </section>

      {/* Approval summary card */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[548px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[28px] top-[25px] font-semibold text-ink text-[20px]">
          Fund your retrofit plan
        </p>
        <p className="absolute left-[28px] top-[74px] text-muted text-[13px]">Amount to transfer</p>
        <p className="absolute left-[28px] top-[99px] font-semibold text-ink text-[30px] whitespace-nowrap">
          {usdExact(plan?.total_upfront)}
        </p>

        <p className="absolute left-[28px] top-[166px] text-muted text-[12px]">From</p>
        <button
          type="button"
          onClick={() => go('/funding-account')}
          className="absolute left-[28px] top-[190px] w-[384px] h-[56px] rounded-[5px] bg-white border border-line text-left overflow-hidden"
        >
          <span className="absolute left-[13px] top-[11px] font-medium text-ink text-[14px]">
            {account && !account.simulated && account.configured
              ? `${account.nickname || 'Source account'} · ${account.account_id}`
              : 'Owner operating account'}
          </span>
          <span className="absolute left-[13px] top-[33px] w-[300px] truncate text-muted text-[11px]">{accountLine}</span>
          <span className="absolute left-[331px] top-[19px] text-muted text-[11px]">Details</span>
        </button>

        <p className="absolute left-[28px] top-[269px] text-muted text-[12px]">To</p>
        <p className="absolute left-[28px] top-[292px] font-medium text-ink text-[16px]">Retrofit Reserve</p>
        <p className="absolute left-[28px] top-[320px] text-muted text-[12px]">
          A dedicated account, created after approval{simulated ? ' (simulated)' : ''}.
        </p>

        <div className="absolute left-[28px] top-[357px] w-[384px] h-px bg-line" />

        {/* Consent toggle (hotspot covers checkbox + label) */}
        <button
          type="button"
          role="checkbox"
          aria-checked={consent}
          disabled={!verdict.approvable || executed}
          onClick={() => setConsent((v) => !v)}
          className="absolute left-[22px] top-[370px] w-[396px] h-[62px] text-left disabled:opacity-50"
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
            of {plural(bundles.length, 'contractor bill')} for this plan.
          </span>
        </button>

        <button
          type="button"
          disabled={!canApprove}
          onClick={approve}
          className={`absolute left-[28px] top-[448px] w-[384px] h-[47px] rounded-[6px] text-[14px] font-medium transition ${
            canApprove
              ? 'bg-brand text-white hover:brightness-110 active:brightness-95'
              : 'bg-[#dde5d7] text-[#65765e] cursor-not-allowed'
          }`}
        >
          {approving ? 'Approving…' : executed ? 'Already funded' : 'Approve & fund'}
        </button>
        <p
          title={[approveError, ...verdict.reasons].filter(Boolean).join('; ')}
          className={`absolute left-[28px] top-[507px] w-[384px] text-[11px] leading-[15px] line-clamp-2 ${
            approveError || !verdict.approvable ? 'text-[#b4532f]' : 'text-muted'
          }`}
        >
          {approveError
            ? approveError
            : executed
              ? 'This plan has already been funded.'
              : !verdict.approvable
                ? `Can't approve: ${verdict.reasons.join('; ')}`
                : verdict.warnings.length
                  ? `Note: ${verdict.warnings.join('; ')}. No money has moved.`
                  : 'Confirm above to continue. No money has moved.'}
        </p>
      </section>

      {/* Safeguards */}
      <section className="absolute left-[56px] top-[674px] w-[816px] h-[210px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[18px]">
          What happens after approval
        </p>
        {[
          { n: '01', title: 'Open your Retrofit Reserve', desc: 'Keep retrofit funds separate from day-to-day spending.' },
          { n: '02', title: 'Transfer the approved investment', desc: `Move exactly ${usdExact(plan?.total_upfront)} into the reserve.` },
          { n: '03', title: 'Create contractor bills', desc: `One bill per contractor for the ${plural(items.length, 'upgrade')} in your plan.` },
        ].map((s, i) => {
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
        {simulated
          ? 'Simulated funding · Nessie stub mode · No real account or money movement'
          : 'Nessie live API (Capital One sandbox) · Transfers only after you approve'}
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
