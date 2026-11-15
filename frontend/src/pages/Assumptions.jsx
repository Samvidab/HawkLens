import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { NA } from '../components/Truth'
import { getAssumptions } from '../lib/api'
import { useRun } from '../lib/store'

const pctOf = (v) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : NA)
const n = (v, unit) => (typeof v === 'number' ? `${v.toLocaleString('en-US')} ${unit}` : NA)

// Strict: the quant engine's own assumptions (GET /assumptions), with the source text recorded next to each group.
export default function Assumptions() {
  const navigate = useNavigate()
  const run = useRun()
  const close = () => navigate(-1)
  const [a, setA] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    getAssumptions(run.portfolio?.city).then(setA).catch((e) => setErr(e.message))
  }, [run.portfolio?.city])
  const g = a?.global || {}
  const c = a?.city_values || {}
  const rows = a ? [
    ['Discount rate', pctOf(g.discount_rate)],
    ['General inflation', pctOf(g.general_inflation)],
    [`Electricity rate${a.city ? ` (${a.city})` : ''}`, n(c.electricity_rate_usd_per_kwh, '$ / kWh')],
    ['Grid emission factor', n(c.grid_kg_co2_per_kwh, 'kgCO₂ / kWh')],
    ['Solar yield', n(c.solar_kwh_per_kw_year, 'kWh / kW / year')],
    ['Simulated scenarios', typeof g.n_scenarios === 'number' ? g.n_scenarios.toLocaleString('en-US') : NA],
  ] : []

  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className="relative w-[1440px] h-[980px] shrink-0 bg-[rgba(34,42,49,0.35)]">
        <button type="button" aria-label="Close" onClick={close} className="absolute inset-0 w-full h-full cursor-default" />

        <div className="absolute left-[300px] top-[120px] w-[840px] h-[740px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[32px] top-[29px] font-semibold text-ink text-[25px]">Assumptions &amp; sources</p>
          <p className="absolute left-[32px] top-[72px] text-muted text-[13px]">
            The values the quant engine prices with (app/engine/assumptions.json){a?.city ? '' : a ? ` · city values ${NA}` : ''}
          </p>
          <button type="button" onClick={close} className="absolute left-[757px] top-[35px] font-medium text-brand text-[14px] hover:underline">
            Done
          </button>

          {!a && <p className="absolute left-[32px] top-[127px] text-muted text-[14px]">{err ? `Assumptions not available: ${err}` : 'Loading…'}</p>}
          {rows.map(([label, value], i) => (
            <div key={label}>
              <div className="absolute left-[32px] w-[776px] h-px bg-line" style={{ top: `${115 + i * 46}px` }} />
              <p className="absolute left-[32px] font-medium text-ink text-[14px]" style={{ top: `${127 + i * 46}px` }}>{label}</p>
              <p className="absolute left-[360px] text-ink text-[14px] tabular-nums" style={{ top: `${127 + i * 46}px` }}>{value}</p>
            </div>
          ))}
          {a && (
            <div className="absolute left-[32px] top-[400px] w-[776px] h-[310px] overflow-y-auto text-[11px] leading-[17px] text-muted space-y-2" data-testid="assumption-sources">
              <p className="font-medium text-ink text-[13px]">Sources as recorded</p>
              {g.source && <p><span className="font-medium">Global: </span>{g.source}</p>}
              {c.source && <p><span className="font-medium">{a.city}: </span>{c.source}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
