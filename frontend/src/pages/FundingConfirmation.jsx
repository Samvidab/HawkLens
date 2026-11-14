import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'

export default function FundingConfirmation() {
  const navigate = useNavigate()

  return (
    <Page active="plan">
      <section className="absolute left-[300px] top-[214px] w-[840px] h-[556px] rounded-[10px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[393px] top-[31px] font-semibold text-brand text-[36px]">✓</p>
        <p className="absolute left-[169px] top-[94px] font-semibold text-ink text-[30px]">
          Your retrofit plan is funded.
        </p>
        <p className="absolute left-[185px] top-[142px] text-muted text-[13px]">
          Simulated confirmation · No real account or money movement
        </p>

        <p className="absolute left-[46px] top-[202px] text-muted text-[14px]">Retrofit Reserve</p>
        <p className="absolute left-[554px] top-[202px] font-medium text-brand text-[14px]">
          Created in this demo
        </p>

        <p className="absolute left-[46px] top-[247px] text-muted text-[14px]">Reserved for upgrades</p>
        <p className="absolute left-[554px] top-[242px] font-semibold text-ink text-[24px]">$1280k</p>

        <p className="absolute left-[46px] top-[294px] text-muted text-[14px]">Contractor allocation</p>
        <p className="absolute left-[454px] top-[294px] text-ink text-[13px]">
          18 upgrades across 8 buildings
        </p>

        <div className="absolute left-[46px] top-[338px] w-[748px] h-px bg-[#dde3d8]" />
        <p className="absolute left-[46px] top-[363px] text-muted text-[14px]">
          Keep the memo, survey and demo confirmation together in Documents.
        </p>

        <button
          type="button"
          onClick={() => navigate('/documents')}
          className="absolute left-[46px] top-[414px] w-[355px] h-[46px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
        >
          View documents
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
          onClick={() => navigate('/')}
          className="absolute left-[352px] top-[502px] font-medium text-brand text-[13px] hover:underline"
        >
          Start a new demo
        </button>
      </section>
    </Page>
  )
}
