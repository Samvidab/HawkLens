import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchFundingAccount } from '../lib/api'
import { usdExact } from '../lib/format'

export default function FundingAccount() {
  const navigate = useNavigate()
  const close = () => navigate(-1)
  const [account, setAccount] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    fetchFundingAccount()
      .then((a) => alive && setAccount(a))
      .catch((e) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [])

  const live = account && !account.simulated && account.configured
  const title = error
    ? 'Account unavailable'
    : !account
      ? 'Loading…'
      : live
        ? `${account.nickname || 'Source account'} · ${account.account_id}`
        : account.simulated
          ? 'Simulated account (Nessie stub mode)'
          : 'Not configured'

  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className="relative w-[1440px] h-[980px] shrink-0 bg-[rgba(34,42,49,0.35)]">
        <button
          type="button"
          aria-label="Close"
          onClick={close}
          className="absolute inset-0 w-full h-full cursor-default"
        />

        <div className="absolute left-[420px] top-[300px] w-[600px] h-[380px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[32px] top-[29px] font-semibold text-ink text-[24px]">
            Your funding account
          </p>
          <p className="absolute left-[32px] top-[90px] font-medium text-ink text-[18px]">{title}</p>
          <p className="absolute left-[32px] top-[142px] text-muted text-[13px]">Available balance</p>
          <p className="absolute left-[32px] top-[167px] font-semibold text-ink text-[29px]">
            {live ? usdExact(account.balance) : '—'}
          </p>
          <p className="absolute left-[32px] top-[227px] w-[536px] text-muted text-[13px] leading-[22px]">
            {error ? (
              error
            ) : live ? (
              <>
                Balance read from the Nessie API (Capital One sandbox).
                <br />
                Approval is refused if it does not cover the plan.
              </>
            ) : account?.simulated ? (
              <>
                NESSIE_MODE=stub: no account exists, so no balance is shown.
                <br />
                Approving records a simulated transfer only; no money moves.
              </>
            ) : (
              account?.error || 'Set NESSIE_SOURCE_ACCOUNT_ID on the backend.'
            )}
          </p>
          <button
            type="button"
            onClick={close}
            className="absolute left-[32px] top-[306px] w-[536px] h-[44px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
