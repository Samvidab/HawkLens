import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import LiveMemo from '../components/LiveMemo'

export default function Documents() {
  const navigate = useNavigate()
  return <Page active="documents">
    <div className="absolute left-[56px] top-[127px]">
      <h1 className="font-semibold text-ink text-[32px]">Documents</h1>
      <p className="text-muted text-[14px] mt-2">The plan, the evidence, and the assumptions behind it.</p>
    </div>
    <section className="absolute left-[56px] top-[265px] w-[768px]">
      <p className="text-muted text-sm mb-5">Plan documents</p>
      <button onClick={() => navigate('/investment-memo')} className="w-full text-left rounded-[6px] bg-[#edf3e6] p-5 hover:brightness-95">
        <span className="font-medium text-ink">Investment memo</span>
        <p className="text-muted text-xs mt-2">Live plan figures · PDF available after generation</p>
      </button>
      <p className="text-muted text-xs mt-8">Memo updates can be generated whenever the plan changes.</p>
    </section>
    <section className="absolute left-[880px] top-[265px] w-[504px] h-[625px]"><LiveMemo /></section>
  </Page>
}
