import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { fetchPortfolio } from '../lib/api'
import { usePlan } from '../lib/plan'
import { budgetLabel, plural, riskLabel } from '../lib/format'

export default function StartSurvey() {
  const navigate = useNavigate()
  const { plan, goal, startSurvey, repriceExisting } = usePlan()
  const [buildings, setBuildings] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    fetchPortfolio()
      .then((d) => alive && setBuildings(d.buildings || []))
      .catch((e) => alive && setLoadError(e.message))
    return () => {
      alive = false
    }
  }, [])

  const surveyed = new Set(plan?.coverage?.surveyed || [])
  const city = buildings[0]?.city || 'Houston'

  async function start() {
    setError(null)
    setStarting(true)
    try {
      await startSurvey()
      navigate('/survey-in-progress')
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  async function reprice() {
    setError(null)
    setStarting(true)
    const r = await repriceExisting()
    setStarting(false)
    if (r.ok) navigate('/')
    else setError(r.error?.message || 'Re-pricing failed')
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
        {city} portfolio · {plural(buildings.length, 'building')} · CoStar records, aerial imagery and interior scans where available
      </p>

      {/* Buildings in this survey */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[550px] overflow-hidden">
        <p className="absolute left-[20px] top-[17px] font-semibold text-ink text-[16px] leading-[1.45]">
          Buildings in this survey
        </p>
        {loadError && (
          <p className="absolute left-[20px] top-[75px] text-[#b4532f] text-[13px]">Couldn&rsquo;t load the portfolio ({loadError}).</p>
        )}
        {buildings.map((b, i) => {
          const divTop = 65 + i * 53
          const rowTop = 75 + i * 53
          return (
            <div key={b.building_id}>
              <div className="absolute left-[20px] w-[808px] h-px bg-line" style={{ top: `${divTop}px` }} />
              <p
                className="absolute left-[20px] w-[310px] truncate font-medium text-ink text-[13px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                {b.name || b.building_id}
              </p>
              <p
                className="absolute left-[347px] text-muted text-[14px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                {b.hero ? 'Records + aerial + interior' : 'Records + aerial'}
              </p>
              <p
                className="absolute left-[748px] text-brand text-[11px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                {surveyed.has(b.building_id) ? 'Surveyed' : 'Not surveyed'}
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
        {[
          { label: 'City', value: city },
          { label: 'Portfolio', value: plural(buildings.length, 'building') },
        ].map((s, i) => (
          <div key={s.label}>
            <p
              className="absolute left-[24px] font-medium text-muted text-[13px] leading-[1.45]"
              style={{ top: `${73 + i * 44}px` }}
            >
              {s.label}
            </p>
            <p
              className="absolute left-[262px] font-medium text-ink text-[13px] leading-[1.45]"
              style={{ top: `${73 + i * 44}px` }}
            >
              {s.value}
            </p>
          </div>
        ))}
        <p className="absolute left-[24px] top-[161px] font-medium text-muted text-[13px] leading-[1.45]">
          Carbon reduction goal
        </p>
        <p className="absolute left-[320px] top-[161px] font-medium text-brand text-[13px] leading-[1.45]">
          {goal.target_pct}%
        </p>
        <p className="absolute left-[24px] top-[205px] font-medium text-muted text-[13px] leading-[1.45]">
          Budget and risk
        </p>
        <p className="absolute left-[24px] top-[233px] text-muted text-[11px] leading-[1.45]">
          {budgetLabel(goal.budget_usd)} · {riskLabel(goal.risk_lambda)} risk
        </p>
      </section>

      <button
        type="button"
        disabled={starting || buildings.length === 0}
        onClick={start}
        className="absolute left-[944px] top-[597px] w-[440px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition disabled:opacity-50"
      >
        {starting ? 'Starting…' : 'Start survey'}
      </button>
      <button
        type="button"
        disabled={starting}
        onClick={reprice}
        className="absolute left-[944px] top-[660px] w-[440px] h-[46px] rounded-[6px] bg-model text-brand text-[13px] font-medium leading-[1.45] hover:brightness-95 transition disabled:opacity-50"
      >
        Re-price with existing survey results
      </button>
      {error && (
        <p className="absolute left-[944px] top-[720px] w-[440px] text-[#b4532f] text-[12px] leading-[1.45]">{error}</p>
      )}

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Starts POST /run: survey every building, then the quant engine prices the plan
      </p>
    </Page>
  )
}
