import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo } from '../lib/ui'

const EVENTS = [
  { time: '09:41:12', agent: 'Records analyst', msg: 'Midtown office profile loaded.', meta: 'CoStar · 96,000 sq ft · 6 floors' },
  { time: '09:41:36', agent: 'Aerial inspector', msg: 'Found 1,200 m² of usable roof.', meta: 'Vexcel · Overhead + facade images' },
  { time: '09:42:04', agent: 'Interior inspector', msg: 'Flagged fluorescent ceiling fixtures.', meta: 'Matterport · Level 2 panorama' },
  { time: '09:42:18', agent: 'Verifier', msg: 'Roof claim verified at 0.91 confidence.', meta: 'Evidence 12 · No additional review loop' },
  { time: '09:42:31', agent: 'Pricing agent', msg: 'Preparing feasible upgrades for simulation.', meta: 'Engine inputs · Queued' },
  { time: '09:42:35', agent: 'Orchestrator', msg: 'Waiting for the remaining two buildings.', meta: 'Parallel survey · 3 active inspectors' },
]

const PROGRESS = [
  { label: 'Records', detail: '8 / 8 complete' },
  { label: 'Aerial inspection', detail: '6 / 8 complete' },
  { label: 'Interior inspection', detail: 'Hero building pending' },
  { label: 'Verification', detail: 'In progress' },
]

export default function SurveyInProgress() {
  const navigate = useNavigate()
  const go = useGo()

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
        Surveying your portfolio
      </h1>
      <p className="absolute left-[56px] top-[202px] text-muted text-[14px] leading-[1.45]">
        Pulling evidence, checking feasibility and verifying claims.
      </p>

      {/* Activity feed */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[440px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey activity
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          6 of 8 buildings inspected · Example event stream
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">In progress</p>
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

      {/* Survey progress */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[440px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[21px] font-semibold text-ink text-[20px] leading-[1.45]">
          6 of 8 buildings inspected
        </p>
        <div className="absolute left-[24px] top-[81px] w-[392px] h-[6px] rounded-[3px] bg-model" />
        <div className="absolute left-[24px] top-[81px] w-[294px] h-[6px] rounded-[3px] bg-brand" />
        {PROGRESS.map((p, i) => {
          const top = 128 + i * 49
          return (
            <div key={p.label}>
              <p className="absolute left-[24px] font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {p.label}
              </p>
              <p className="absolute left-[220px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top}px` }}>
                {p.detail}
              </p>
            </div>
          )
        })}
        <p className="absolute left-[24px] top-[343px] text-muted text-[11px] leading-[1.45]">
          Keep the workspace open while the survey runs.
        </p>
        <button
          type="button"
          onClick={() => navigate('/survey-complete')}
          className="absolute left-[24px] top-[388px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
        >
          Interior connection details&nbsp;&nbsp;→
        </button>
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Prototype survey sequence · Example buildings and findings, not live data
      </p>
    </Page>
  )
}
