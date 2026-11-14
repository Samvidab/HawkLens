import { Link } from 'react-router-dom'
import Page from '../components/Page'
import { Stub, useStub } from '../components/Truth'
import { RENDERERS } from '../components/widgets'
import { useRun } from '../lib/store'
import { buildingModel } from '../lib/viewModels'

// The composer-driven page: renders layout.widgets exactly in the composer's order and sizes (12-column grid,
// App Flow §4: full=12, wide=8, half=6, side=4), each with its title and `why` line. Props come from the backend
// resolver only; this page adds nothing of its own.
export const SPAN = { full: 'col-span-12', wide: 'col-span-8', half: 'col-span-6', side: 'col-span-4' }
const SITUATION = {
  portfolio_overview: 'Portfolio overview', target_gap: 'Target out of reach', verification_issue: 'Findings to review',
  building_detail: 'Building', approved: 'Plan approved',
}

export function WidgetCard({ w }) {
  const R = RENDERERS[w.type]
  return (
    <section data-widget={w.type} data-size={w.size} className={`${SPAN[w.size] || 'col-span-12'} rounded-[8px] border border-line bg-white p-4 min-w-0`}>
      <h2 className="text-[15px] font-semibold text-ink">{w.title}</h2>
      <p data-why className="text-[12px] italic text-muted mb-3">{w.why}</p>
      {R ? <R p={w.props} /> : <p className="text-[13px] text-muted">Widget type “{w.type}” is not supported by this page.</p>}
    </section>
  )
}

export default function Workspace() {
  const run = useRun()
  const stub = useStub()
  const L = run.layout
  return (
    <Page active="workspace" fluid>
      <div className="px-[56px] pt-[110px] pb-[40px]">
        {!L ? (
          <div className="space-y-2">
            <h1 className="text-[32px] font-semibold text-ink">Workspace</h1>
            <p className="text-muted text-[14px]">{run.phase === 'surveying' ? 'The survey is running…' : run.error ? `Not available: ${run.error}` : 'No workspace yet.'}</p>
            {run.phase !== 'surveying' && <Link to="/start-survey" className="text-brand font-medium">Start a survey →</Link>}
          </div>
        ) : (
          <>
            <header className="mb-5 flex items-end justify-between">
              <div>
                <h1 className="text-[32px] font-semibold text-ink">{SITUATION[L.situation] || L.situation}{L.situation === 'building_detail' && buildingModel(L) ? ` · ${buildingModel(L).name}` : ''}</h1>
                <p className="text-muted text-[13px]">Composed by the agent · {L.widgets.length} widgets · {new Date(L.generated_at).toLocaleString()}{run.busy ? ' · updating…' : ''}</p>
              </div>
              <p className="text-[12px] text-muted">
                {stub.engine ? <>Pricing: sample stub<Stub /></> : 'Pricing: quant engine'}{' · '}{stub.nessie ? <>Banking: simulated<Stub title="Stub Nessie: nothing is sent to a bank" /></> : 'Banking: Nessie sandbox'}
              </p>
            </header>
            {run.error && <p className="mb-3 text-[13px] text-[#b4532f]">{run.error}</p>}
            <div className="grid grid-cols-12 gap-4" data-testid="workspace-grid">
              {L.widgets.map((w) => <WidgetCard key={w.id} w={w} />)}
            </div>
          </>
        )}
      </div>
    </Page>
  )
}
