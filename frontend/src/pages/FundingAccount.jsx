import { useNavigate } from 'react-router-dom'

export default function FundingAccount() {
  const navigate = useNavigate()
  const close = () => navigate(-1)

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
          <p className="absolute left-[32px] top-[90px] font-medium text-ink text-[18px]">
            Owner checking · •• 2048
          </p>
          <p className="absolute left-[32px] top-[142px] text-muted text-[13px]">Available balance</p>
          <p className="absolute left-[32px] top-[167px] font-semibold text-ink text-[29px]">
            $2,400,000
          </p>
          <p className="absolute left-[32px] top-[227px] text-muted text-[13px] leading-[22px]">
            Nessie sandbox · Simulated account only.
            <br />
            No connection to a real bank account.
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
