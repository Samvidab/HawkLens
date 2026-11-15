import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'

const EVENTS = [
  { time: '09:41:12', agent: 'Records analyst', msg: 'Midtown office profile loaded.', meta: 'CoStar · 96,000 sq ft · 6 floors' },
  { time: '09:41:36', agent: 'Aerial inspector', msg: 'Found 1,200 m² of usable roof.', meta: 'Vexcel · Overhead + facade images' },
  { time: '09:42:04', agent: 'Interior inspector', msg: 'Flagged fluorescent ceiling fixtures.', meta: 'Matterport · Level 2 panorama' },
  { time: '09:42:18', agent: 'Verifier', msg: 'Roof claim verified at 0.91 confidence.', meta: 'Evidence 12 · No additional review loop' },
  { time: '09:42:31', agent: 'Pricing agent', msg: 'Preparing feasible upgrades for simulation.', meta: 'Engine inputs · Queued' },
  { time: '09:42:35', agent: 'Orchestrator', msg: 'Survey complete. The plan is ready to review.', meta: 'Parallel survey · 3 active inspectors' },
]

const SUMMARY = [
  { label: 'Aerial coverage', value: '7 buildings' },
  { label: 'Interior coverage', value: '1 hero building' },
  { label: 'Feasible upgrades', value: '18 upgrades' },
  { label: 'Unverified claims', value: 'Excluded from plan' },
]

export default function SurveyComplete() {
  const navigate = useNavigate()

  return (
    <Page active="portfolio">
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-[56px] top-[110px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
      >
        ←&nbsp;&nbsp;Portfolio
      </button>
      <h1 className="absolute left-[56px] top-[148px] font-semibold text-ink text-[32px] leading-[1.45]">
        Your survey is ready
      </h1>
      <p className="absolute left-[56px] top-[202px] text-muted text-[14px] leading-[1.45]">
        7 buildings inspected. Verified findings are ready for pricing and planning.
      </p>

      {/* Activity feed */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[440px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey activity
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          7 of 7 buildings inspected · Workspace ready
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">Complete</p>
        {EVENTS.map((e, i) => {
          const top = 86 + i * 48
          return (
            <div key={e.time}>
              {i > 0 && (
                <div className="absolute left-[19px] w-[808px] h-px bg-line" style={{ top: `${top - 7}px` }} />
              )}
              <p className="absolute left-[19px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top}px` }}>
                {e.time}
              </p>
              <p className="absolute left-[109px] font-medium text-brand text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {e.agent}
              </p>
              <p className="absolute left-[277px] text-ink text-[14px] leading-[1.45]" style={{ top: `${top}px` }}>
                {e.msg}
              </p>
              <p className="absolute left-[277px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top + 22}px` }}>
                {e.meta}
              </p>
            </div>
          )
        })}
        <p className="absolute left-[19px] top-[409px] text-muted text-[11px] leading-[1.45]">
          Structured events · Illustrative sequence, not a live server feed
        </p>
      </section>

      {/* Survey result summary */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[340px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[23px] font-semibold text-ink text-[20px] leading-[1.45]">
          7 buildings ready
        </p>
        {SUMMARY.map((s, i) => {
          const top = 85 + i * 46
          return (
            <div key={s.label}>
              <p className="absolute left-[24px] font-medium text-muted text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {s.label}
              </p>
              <p className="absolute left-[248px] font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {s.value}
              </p>
            </div>
          )
        })}
      </section>

      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-[944px] top-[637px] w-[440px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition"
      >
        Open workspace
      </button>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Prototype survey sequence · Example buildings and findings, not live data
      </p>
    </Page>
  )
}
