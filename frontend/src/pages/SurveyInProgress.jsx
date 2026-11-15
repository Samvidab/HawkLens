import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA } from '../components/Truth'
import { useRun } from '../lib/store'
import { feedRows, surveyProgress } from '../lib/viewModels'

// Strict: the live event stream of the current run only (the route gate guarantees a run).
export default function SurveyInProgress() {
  const navigate = useNavigate()
  const run = useRun()
  const total = run.state?.building_ids?.length || run.portfolio?.buildings?.length || null
  const events = feedRows(run.events, 6)
  const progress = surveyProgress(run.events, total)
  const inspected = new Set(run.events.filter((e) => e.agent === 'Aerial' && e.building_id).map((e) => e.building_id)).size
  useEffect(() => { if (run.phase === 'ready') navigate('/survey-complete') }, [run.phase, navigate])
  const countLine = total ? `${inspected} of ${total} buildings inspected` : `${inspected} buildings inspected · total ${NA}`

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
          {countLine} · {run.events.length} events
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">{run.phase === 'error' ? 'Stopped' : 'In progress'}</p>
        {!events.length && <p className="absolute left-[19px] top-[86px] text-muted text-[13px]">Waiting for the first event…</p>}
        {events.map((e, i) => {
          const top = 86 + i * 48
          return (
            <div key={e.seq ?? `${e.time}${i}`}>
              {i > 0 && <div className="absolute left-[19px] w-[808px] h-px bg-line" style={{ top: `${top - 7}px` }} />}
              <p className="absolute left-[19px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top}px` }}>{e.time}</p>
              <p className="absolute left-[109px] font-medium text-brand text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>{e.agent}</p>
              <p className="absolute left-[277px] w-[550px] truncate text-ink text-[14px] leading-[1.45]" style={{ top: `${top}px` }}>{e.msg}</p>
              <p className="absolute left-[277px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top + 22}px` }}>{e.meta}</p>
            </div>
          )
        })}
        <p className="absolute left-[19px] top-[409px] text-muted text-[11px] leading-[1.45]">
          {run.error ? run.error : 'Structured events · live from the agents'}
        </p>
      </section>

      {/* Survey progress */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[440px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[21px] font-semibold text-ink text-[20px] leading-[1.45]">
          {countLine}
        </p>
        <div className="absolute left-[24px] top-[81px] w-[392px] h-[6px] rounded-[3px] bg-model" />
        {total && <div className="absolute left-[24px] top-[81px] h-[6px] rounded-[3px] bg-brand" style={{ width: `${Math.round(392 * Math.min(1, inspected / total))}px` }} />}
        {progress.map((p, i) => {
          const top = 128 + i * 49
          return (
            <div key={p.label}>
              <p className="absolute left-[24px] font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>{p.label}</p>
              <p className="absolute left-[220px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top}px` }}>{p.detail || NA}</p>
            </div>
          )
        })}
        <p className="absolute left-[24px] top-[343px] text-muted text-[11px] leading-[1.45]">
          Keep the workspace open while the survey runs.
        </p>
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Live survey · events stream from the backend (GET /events)
      </p>
    </Page>
  )
}
