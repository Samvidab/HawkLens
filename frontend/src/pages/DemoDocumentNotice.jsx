import { useNavigate } from 'react-router-dom'

export default function DemoDocumentNotice() {
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

        <div className="absolute left-[440px] top-[330px] w-[560px] h-[320px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[32px] top-[31px] font-semibold text-ink text-[24px]">
            Document preview
          </p>
          <p className="absolute left-[32px] top-[83px] font-medium text-ink text-[15px]">
            You&rsquo;re viewing an interactive prototype.
          </p>
          <p className="absolute left-[32px] top-[118px] text-muted text-[14px] leading-[24px]">
            Downloads and bank records are simulated here.
            <br />
            In the live app, this action exports the current
            <br />
            plan, survey or confirmation.
          </p>
          <button
            type="button"
            onClick={close}
            className="absolute left-[32px] top-[238px] w-[496px] h-[46px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
