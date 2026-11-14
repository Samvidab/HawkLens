import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'

// Temporary page for Figma screens not yet built. Keeps navigation working
// end-to-end: every link lands on a real, titled route with a way back.
export default function Placeholder({ title, active = 'portfolio' }) {
  const navigate = useNavigate()
  return (
    <Page active={active}>
      <div className="absolute left-[56px] top-[160px] right-[56px]">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-brand text-[13px] hover:underline"
        >
          ←&nbsp;&nbsp;Back
        </button>
        <h1 className="mt-6 font-semibold text-ink text-[32px]">{title}</h1>
        <p className="mt-3 text-muted text-[14px]">
          This screen is part of the Hawk Lens prototype and is coming next.
        </p>
        <div className="mt-8 w-[520px] h-[320px] rounded-[8px] border border-dashed border-line bg-model/40 flex items-center justify-center text-muted text-[13px]">
          {title} — layout pending
        </div>
      </div>
    </Page>
  )
}
