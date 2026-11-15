// Honesty helpers: nothing shown to the user may be invented (strict demo mode, always on).
//   <Stub/>       a visible STUB badge next to any value that comes from a stub (sample pricing engine, stub Nessie)
//   <Estimate/>   marks a value that is an estimate (benchmark baseline, estimated footprint, assumed upgrade)
//   NA            the text shown when data is missing
//   useStub()     { engine, nessie }: true when that source is a stub
//   <RequireRun/> route gate: a page that needs a run shows "no survey data yet" instead of any prototype content
//   <Sources/>    footer line naming where the numbers come from, with STUB badges
import { Link } from 'react-router-dom'
import Page from './Page'
import { useRun } from '../lib/store'
import { NA, widget } from '../lib/viewModels'

export { NA }

export function Stub({ title = 'Placeholder value from a stub, not real pricing' }) {
  return (
    <span title={title} data-stub="true"
      className="ml-[6px] inline-block align-middle rounded-[3px] bg-[#b4532f] px-[5px] py-[1px] text-[9px] font-bold tracking-[0.6px] text-white leading-[14px]">
      STUB
    </span>
  )
}

export function Estimate({ children = 'estimate', title = 'Estimated, not measured' }) {
  return (
    <span title={title} data-estimate="true"
      className="ml-[6px] inline-block align-middle rounded-[3px] border border-[#9a8a55] px-[4px] text-[9px] font-medium tracking-[0.4px] text-[#7a693b] leading-[13px]">
      {children}
    </span>
  )
}

/** Which sources are stubs: the engine (sample pricing) and Nessie (simulated bookings). Unknown health = not claimed live. */
export function useStub() {
  const run = useRun()
  const sample = !!widget(run.layout, 'plan_table')?.sample_pricing
  return {
    engine: sample || run.health?.engine_mode === 'stub',
    nessie: run.health?.nessie_mode === 'stub',
  }
}

/** `value` if present, else "not available" (for numbers already formatted as strings). */
export const orNA = (value) => (value === null || value === undefined || value === '' || value === '—' ? NA : value)

/** Where the numbers on the page come from. `banking` adds the Nessie source. */
export function Sources({ banking = false, className = 'absolute left-[56px] top-[947px]' }) {
  const run = useRun()
  const { engine, nessie } = useStub()
  const h = run.health
  return (
    <p className={`${className} whitespace-nowrap text-muted text-[11px]`} data-testid="sources">
      Survey data from the backend · Pricing: {engine ? <>sample prices (stub engine)<Stub /></> : h ? 'quant engine' : `engine mode ${NA}`}
      {banking && <> · Banking: {nessie ? <>simulated (stub Nessie)<Stub title="Simulated booking, nothing is sent to a bank" /></> : h ? 'Nessie sandbox (no real money)' : `Nessie mode ${NA}`}</>}
    </p>
  )
}

/** What a page shows when it needs data the run does not have (never prototype content). */
export function NoData({ title = 'No survey data yet', detail, active = 'portfolio' }) {
  const run = useRun()
  const loading = run.runId && run.phase !== 'error' && !run.layout
  return (
    <Page active={active}>
      <div className="absolute left-[56px] top-[150px] w-[900px]" data-testid="no-data">
        <h1 className="font-semibold text-ink text-[32px]">{loading ? 'Loading the workspace…' : title}</h1>
        <p className="mt-3 text-muted text-[14px]">
          {loading ? 'The run is still finishing; this page fills in when its data arrives.'
            : run.phase === 'error' && run.error ? `The run stopped: ${run.error}`
              : detail || 'This page shows real survey and pricing data only. Start a survey to fill it in.'}
        </p>
        {!loading && <Link to="/start-survey" className="mt-6 inline-block font-medium text-brand text-[14px] hover:underline">Start a survey&nbsp;&nbsp;→</Link>}
      </div>
    </Page>
  )
}

/** Route gate. need='layout': a composed workspace; need='run': a started run (survey screens); need='portfolio'. */
export function RequireRun({ need = 'layout', children, active }) {
  const run = useRun()
  if (need === 'portfolio') {
    return run.portfolio?.buildings?.length ? children
      : <NoData active={active} title="Portfolio not available" detail="The portfolio could not be loaded from the backend (GET /portfolio). Is the backend running?" />
  }
  if (need === 'run') return run.runId ? children : <NoData active={active} title="No survey running" />
  return run.layout ? children : <NoData active={active} />
}
