import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { eventsUrl, fetchRunState } from '../lib/api'
import { usePlan } from '../lib/plan'
import { plural } from '../lib/format'

const hms = (ts) => (ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')

/** Survey progress from GET /state/{run_id}: per-building results written by the survey graph. */
function summarize(st) {
  const ids = st?.building_ids || Object.keys(st?.results || {})
  const res = st?.results || {}
  const done = ids.filter((b) => res[b]?.status === 'done').length
  const failed = ids.filter((b) => res[b]?.status === 'error').length
  const upgrades = ids.reduce((a, b) => a + (res[b]?.upgrades || 0), 0)
  return { total: ids.length, done, failed, upgrades, status: st?.status }
}

export default function SurveyInProgress() {
  const navigate = useNavigate()
  const { runId, refresh } = usePlan()
  const [events, setEvents] = useState([])
  const [state, setState] = useState(null)
  const [streamError, setStreamError] = useState(null)
  const [finished, setFinished] = useState(false)
  const lastPoll = useRef(0)

  useEffect(() => {
    if (!runId) return undefined
    const poll = () => fetchRunState(runId).then(setState).catch(() => {})
    poll()
    const es = new EventSource(eventsUrl(runId))
    es.onmessage = (m) => {
      let ev
      try {
        ev = JSON.parse(m.data)
      } catch {
        return
      }
      setEvents((xs) => (xs.some((x) => x.seq === ev.seq) ? xs : [...xs, ev]))
      if (Date.now() - lastPoll.current > 1000) {
        lastPoll.current = Date.now()
        poll()
      }
      if (ev.kind === 'done') {
        es.close()
        setFinished(true)
        poll()
        refresh().then(() => navigate('/survey-complete'))
      }
    }
    es.onerror = () => {
      // The stream closes normally after `done`; anything else is a lost connection.
      if (es.readyState === EventSource.CLOSED) setStreamError('Lost the live event stream; reload to reconnect.')
    }
    return () => es.close()
  }, [runId, refresh, navigate])

  const sum = summarize(state)
  const shown = events.slice(-6)
  const progressPx = sum.total ? Math.round(((sum.done + sum.failed) / sum.total) * 392) : 0

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
        {runId ? `Run ${runId} · pulling evidence, checking feasibility and verifying claims.` : 'No survey running. Start one from the survey screen.'}
      </p>

      {/* Activity feed */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[440px] rounded-[8px] border border-line bg-white overflow-hidden">
        <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey activity
        </p>
        <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
          {sum.total ? `${sum.done + sum.failed} of ${plural(sum.total, 'building')} inspected` : 'Waiting for the first event…'}
        </p>
        <p className="absolute left-[726px] top-[21px] text-brand text-[11px] leading-[1.45]">
          {finished ? 'Complete' : 'In progress'}
        </p>
        {shown.map((e, i) => {
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
          {streamError || 'Live server events (GET /events)'}
        </p>
      </section>

      {/* Survey progress */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[440px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[21px] font-semibold text-ink text-[20px] leading-[1.45]">
          {sum.total ? `${sum.done} of ${plural(sum.total, 'building')} surveyed` : 'Starting…'}
        </p>
        <div className="absolute left-[24px] top-[81px] w-[392px] h-[6px] rounded-[3px] bg-model" />
        <div className="absolute left-[24px] top-[81px] h-[6px] rounded-[3px] bg-brand" style={{ width: `${progressPx}px` }} />
        {[
          { label: 'Surveyed', detail: `${sum.done} / ${sum.total}` },
          { label: 'Failed', detail: String(sum.failed) },
          { label: 'Feasible upgrades', detail: String(sum.upgrades) },
          { label: 'Pricing', detail: finished ? 'Done' : sum.status === 'surveyed' ? 'Running the quant engine' : 'After the survey' },
        ].map((p, i) => {
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
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Live survey · events and results from the backend run
      </p>
    </Page>
  )
}
