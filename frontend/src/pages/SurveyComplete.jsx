import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { fetchEvents, fetchRunState } from '../lib/api'
import { usePlan } from '../lib/plan'
import { plural, statusHeadline } from '../lib/format'

const hms = (ts) => (ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')

export default function SurveyComplete() {
  const navigate = useNavigate()
  const { runId, plan } = usePlan()
  const [state, setState] = useState(null)
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!runId) return undefined
    let alive = true
    fetchRunState(runId)
      .then((s) => alive && setState(s))
      .catch((e) => alive && setError(e.message))
    fetchEvents(runId)
      .then((ev) => alive && setEvents(ev.slice(-6)))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [runId])

  const res = state?.results || {}
  const ids = state?.building_ids || Object.keys(res)
  const done = ids.filter((b) => res[b]?.status === 'done')
  const failed = ids.filter((b) => res[b]?.status === 'error')
  const upgrades = done.reduce((a, b) => a + (res[b].upgrades || 0), 0)
  const included = done.reduce((a, b) => a + (res[b].included || 0), 0)
  const interior = done.filter((b) => res[b].interior).length
  const ready = state?.status === 'ready'

  const SUMMARY = [
    { label: 'Buildings surveyed', value: `${done.length} of ${ids.length}${failed.length ? ` · ${failed.length} failed` : ''}` },
    { label: 'Interior coverage', value: plural(interior, 'building') },
    { label: 'Feasible upgrades', value: `${upgrades} (${included} in the optimizer)` },
    { label: 'Plan', value: plan ? `${statusHeadline(plan)} · ${plan.plan_id}` : 'Not priced' },
  ]

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
        {!runId
          ? 'No survey yet'
          : ready
            ? 'Your survey is ready'
            : state?.status === 'no_plan'
              ? 'No plan could be priced'
              : state?.status === 'error'
                ? 'The survey stopped'
                : 'Survey results'}
      </h1>
      <p className="absolute left-[56px] top-[202px] text-muted text-[14px] leading-[1.45]">
        {error
          ? `Run unavailable: ${error}`
          : state?.status === 'no_plan'
            ? `${plural(failed.length, 'building')} failed to survey · ${state.reason || 'nothing to price'}`
            : runId
            ? `${plural(done.length, 'building')} inspected. Verified findings were priced by the quant engine.`
            : 'Start a survey to inspect the portfolio.'}
      </p>

      {/* Activity feed */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[440px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey activity
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          {runId ? `Run ${runId} · last ${events.length} events` : '—'}
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">{ready ? 'Complete' : state?.status || ''}</p>
        {events.map((e, i) => {
          const top = 86 + i * 48
          return (
            <div key={e.seq}>
              {i > 0 && (
                <div className="absolute left-[19px] w-[808px] h-px bg-line" style={{ top: `${top - 7}px` }} />
              )}
              <p className="absolute left-[19px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top}px` }}>
                {hms(e.ts)}
              </p>
              <p className="absolute left-[109px] w-[160px] truncate font-medium text-brand text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {e.agent}
              </p>
              <p
                className={`absolute left-[277px] w-[540px] truncate text-[14px] leading-[1.45] ${e.kind === 'error' ? 'text-[#b4532f]' : 'text-ink'}`}
                style={{ top: `${top}px` }}
              >
                {e.message}
              </p>
              <p className="absolute left-[277px] text-muted text-[11px] leading-[1.45]" style={{ top: `${top + 22}px` }}>
                {[e.building_name, e.kind].filter(Boolean).join(' · ')}
              </p>
            </div>
          )
        })}
        <p className="absolute left-[19px] top-[409px] text-muted text-[11px] leading-[1.45]">
          Recorded server events (GET /events)
        </p>
      </section>

      {/* Survey result summary */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[340px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[23px] font-semibold text-ink text-[20px] leading-[1.45]">
          {`${done.length} of ${plural(ids.length, 'building')} ready`}
        </p>
        {SUMMARY.map((s, i) => {
          const top = 85 + i * 46
          return (
            <div key={s.label}>
              <p className="absolute left-[24px] font-medium text-muted text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
                {s.label}
              </p>
              <p className="absolute left-[200px] w-[220px] truncate font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${top}px` }}>
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
        Live survey results from the backend run
      </p>
    </Page>
  )
}
