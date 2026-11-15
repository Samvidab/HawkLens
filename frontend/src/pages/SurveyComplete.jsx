import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA } from '../components/Truth'
import { useRun } from '../lib/store'
import { feedRows, surveySummary } from '../lib/viewModels'

// Strict: the run's recorded events and its state.results only (the route gate guarantees a run).
export default function SurveyComplete() {
  const navigate = useNavigate()
  const run = useRun()
  const events = feedRows(run.events, 6)
  const summary = surveySummary(run.state, run.layout) || []
  const results = Object.values(run.state?.results || {})
  const nDone = results.filter((r) => r.status === 'done').length
  const nAll = results.length
  const ready = !!run.layout

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
        {ready ? 'Your survey is ready' : run.phase === 'error' ? 'The survey stopped' : 'Finishing the survey…'}
      </h1>
      <p className="absolute left-[56px] top-[202px] text-muted text-[14px] leading-[1.45]">
        {nAll ? `${nDone} of ${nAll} buildings inspected.` : `Building results ${NA}.`}{ready ? ' Verified findings are ready for pricing and planning.' : ''}
      </p>

      {/* Activity feed */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[440px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey activity
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          {nAll ? `${nDone} of ${nAll} buildings inspected` : `Buildings ${NA}`} · {ready ? 'Workspace ready' : 'Finishing up…'}
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">{ready ? 'Complete' : run.phase}</p>
        {!events.length && <p className="absolute left-[19px] top-[86px] text-muted text-[13px]">No events loaded.</p>}
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
          Structured events · recorded by the agents
        </p>
      </section>

      {/* Survey result summary */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[340px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[23px] font-semibold text-ink text-[20px] leading-[1.45]">
          {nAll ? `${nDone} building${nDone === 1 ? '' : 's'} ready` : `Results ${NA}`}
        </p>
        {summary.map((s, i) => {
          const top = 85 + i * 46
          return (
            <div key={s.label}>
              <p className="absolute left-[24px] font-medium text-muted text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>{s.label}</p>
              <p className="absolute left-[248px] font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>{s.value}</p>
            </div>
          )
        })}
      </section>

      <button
        type="button"
        onClick={() => navigate('/workspace')} // the composer's layout for this run
        disabled={!ready}
        className="absolute left-[944px] top-[637px] w-[440px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition disabled:opacity-50"
      >
        Open workspace
      </button>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Survey result from the backend (GET /state)
      </p>
    </Page>
  )
}
