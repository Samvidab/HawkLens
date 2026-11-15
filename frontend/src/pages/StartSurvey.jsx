import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { NA } from '../components/Truth'
import { useRun } from '../lib/store'
import { useToast } from '../lib/ui'
import { riskLabel, usdK } from '../lib/viewModels'

/** The data layers a building actually has, from GET /portfolio (records always; aerial and interior when recorded). */
export function layersOf(b) {
  const c = b.coverage || {}
  return ['Records', (c.vexcel || c.costar_aerial_photos) && 'aerial', (b.matterport_model_id || b.matterport_model_ids?.length) && 'interior']
    .filter(Boolean).join(' + ')
}

// Strict: the building list and settings come from GET /portfolio (the route gate guarantees it loaded).
export default function StartSurvey() {
  const navigate = useNavigate()
  const run = useRun()
  const toast = useToast()
  const { prefs, portfolio } = run
  const buildings = (portfolio?.buildings || []).map((b) => ({ key: b.building_id, name: b.name || b.building_id, layers: layersOf(b) }))
  const nInterior = buildings.filter((b) => b.layers.includes('interior')).length
  const city = portfolio?.city || null
  const settings = [
    { label: 'City', value: city || NA },
    { label: 'Portfolio', value: `${buildings.length} building${buildings.length === 1 ? '' : 's'}` },
  ]
  const begin = async (opts) => {
    const id = await run.start({ city, target_pct: prefs.target_pct, budget_usd: prefs.budget_usd, risk_lambda: prefs.risk_lambda }, opts)
    if (id) navigate('/survey-in-progress')
    else toast('Could not start the survey: is the backend running?')
  }

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
        Inspect your buildings
      </h1>
      <p className="absolute left-[56px] top-[202px] text-muted text-[14px] leading-[1.45]">
        {city ? `${city} portfolio` : 'Portfolio'} · {buildings.length} building{buildings.length === 1 ? '' : 's'} · Records, aerial imagery{nInterior ? ` and ${nInterior} interior scan${nInterior === 1 ? '' : 's'}` : ''}
      </p>

      {/* Buildings in this survey */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[550px] overflow-y-auto">
        <p className="absolute left-[20px] top-[17px] font-semibold text-ink text-[16px] leading-[1.45]">
          Buildings in this survey
        </p>
        {buildings.map((b, i) => {
          const divTop = 65 + i * 53
          const rowTop = 75 + i * 53
          return (
            <div key={b.key}>
              <div className="absolute left-[20px] w-[808px] h-px bg-line" style={{ top: `${divTop}px` }} />
              <p className="absolute left-[20px] w-[310px] truncate font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${rowTop}px` }}>
                {b.name}
              </p>
              <p className="absolute left-[347px] text-muted text-[14px] leading-[1.45]" style={{ top: `${rowTop}px` }}>
                {b.layers}
              </p>
            </div>
          )
        })}
      </section>

      {/* Survey settings summary */}
      <section className="absolute left-[944px] top-[265px] w-[440px] h-[300px] rounded-[8px] bg-[#f5f7f2] overflow-hidden">
        <p className="absolute left-[24px] top-[20px] font-semibold text-ink text-[16px] leading-[1.45]">
          Survey settings
        </p>
        {settings.map((s, i) => (
          <div key={s.label}>
            <p className="absolute left-[24px] font-medium text-muted text-[13px] leading-[1.45]" style={{ top: `${73 + i * 44}px` }}>
              {s.label}
            </p>
            <p className="absolute left-[262px] font-medium text-ink text-[13px] leading-[1.45]" style={{ top: `${73 + i * 44}px` }}>
              {s.value}
            </p>
          </div>
        ))}
        <p className="absolute left-[24px] top-[161px] font-medium text-muted text-[13px] leading-[1.45]">
          Carbon reduction goal
        </p>
        <p className="absolute left-[320px] top-[161px] font-medium text-brand text-[13px] leading-[1.45]">
          {prefs.target_pct}%
        </p>
        <p className="absolute left-[24px] top-[205px] font-medium text-muted text-[13px] leading-[1.45]">
          Budget and risk
        </p>
        <p className="absolute left-[24px] top-[233px] text-muted text-[11px] leading-[1.45]">
          Budget {prefs.budget_usd == null ? 'not set' : usdK(prefs.budget_usd)} · {riskLabel(prefs.risk_lambda)} risk
        </p>
      </section>

      <button
        type="button"
        onClick={() => begin()}
        className="absolute left-[944px] top-[597px] w-[440px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition"
      >
        Start survey
      </button>
      {run.demoRunId && ( // replays a recorded real run; offered only when one is configured
        <button
          type="button"
          onClick={() => begin({ replay: true })}
          className="absolute left-[944px] top-[660px] w-[440px] h-[46px] rounded-[6px] bg-model text-brand text-[13px] font-medium leading-[1.45] hover:brightness-95 transition"
        >
          Replay the recorded survey
        </button>
      )}

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Buildings from GET /portfolio · the agents work from the portfolio records and the survey cache
      </p>
    </Page>
  )
}
