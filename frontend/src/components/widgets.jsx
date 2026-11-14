// One renderer per widget type in the backend registry (App Flow §5). Each reads ONLY the widget's props
// (and the run for actions / the activity feed); missing data is shown as "not available", never filled in.
import { useState } from 'react'
import { API_BASE, mediaUrl } from '../lib/api'
import { Markdown } from '../lib/markdown'
import { useRun } from '../lib/store'
import { feedRows, riskLabel, upgradeLabel } from '../lib/viewModels'
import { Estimate, NA, Stub, useStub } from './Truth'

// ---- formatting: null/undefined -> "not available" ---------------------------------------------------------------------
const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
export const fmt = {
  usd: (v) => (isNum(v) ? `${v < 0 ? '−' : ''}$${Math.round(Math.abs(v)).toLocaleString('en-US')}` : NA),
  usdK: (v) => (isNum(v) ? `${v < 0 ? '−' : ''}$${Math.round(Math.abs(v) / 1000).toLocaleString('en-US')}k` : NA),
  t: (v) => (isNum(v) ? `${Math.round(v).toLocaleString('en-US')} t/yr` : NA),
  pct: (p) => (isNum(p) ? `${Math.round(p * 100)}%` : NA),
  num: (v, unit = '') => (isNum(v) ? `${Math.round(v).toLocaleString('en-US')}${unit}` : NA),
  perT: (v) => (isNum(v) ? `${v < 0 ? '−' : ''}$${Math.round(Math.abs(v)).toLocaleString('en-US')}/t` : NA),
}

const Stat = ({ label, value, stub, extra }) => (
  <div>
    <p className="text-[11px] text-muted">{label}</p>
    <p className={`text-[18px] font-semibold tabular-nums ${value === NA ? 'text-muted text-[14px] font-normal' : 'text-ink'}`}>
      {value}{stub && value !== NA && <Stub />}{extra}
    </p>
  </div>
)

const Empty = ({ children }) => <p className="text-[13px] text-muted">{children}</p>

// ---- target_control ---------------------------------------------------------------------------------------------------------
function TargetControl({ p }) {
  const run = useRun()
  const stub = useStub().engine
  const [target, setTarget] = useState(p.target_pct)
  const send = (v) => v !== p.target_pct && run.act('set_target', { target_pct: v }).catch(() => {})
  const short = isNum(p.tonnes_needed) && isNum(p.tonnes_planned) ? p.tonnes_needed - p.tonnes_planned : null
  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-3">
        <span className="text-[30px] font-semibold tabular-nums">{target}%</span><span className="text-muted text-[13px]">CO₂ reduction target</span>
      </div>
      <input aria-label="Carbon reduction target" type="range" min={0} max={80} step={5} value={target}
        onChange={(e) => setTarget(Number(e.target.value))} onMouseUp={() => send(target)} onKeyUp={() => send(target)} onTouchEnd={() => send(target)}
        className="w-full accent-[#335d45]" />
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Needed" value={fmt.t(p.tonnes_needed)} stub={stub} />
        <Stat label="Planned" value={fmt.t(p.tonnes_planned)} stub={stub} />
        <Stat label="Chance of hitting it" value={fmt.pct(p.p_hit_target)} stub={stub} />
      </div>
      <p className="text-[12px] text-muted">
        {short === null ? 'Coverage not available' : short > 0 ? `${fmt.t(short)} short of the target` : 'The plan covers the target'}
        {' · '}Budget {isNum(p.budget_usd) ? fmt.usdK(p.budget_usd) : 'not set'}
        {' · '}Risk: {p.risk_supported ? `${riskLabel(p.risk_lambda)} (λ ${p.risk_lambda})` : 'not applied by this engine'}
      </p>
    </div>
  )
}

// ---- portfolio_3d: real footprints in 2D (no 3D library) -----------------------------------------------------------------------
const rings = (wkt) => (String(wkt || '').match(/\(([^()]+)\)/g) || []).map((r) =>
  r.replace(/[()]/g, '').split(',').map((pt) => pt.trim().split(/\s+/).map(Number)).filter((xy) => xy.length === 2 && xy.every(Number.isFinite)))

function Portfolio3D({ p }) {
  const run = useRun()
  const shapes = p.buildings.map((b) => ({ b, rings: rings(b.footprint_wkt) })).filter((s) => s.rings.length)
  const pts = shapes.flatMap((s) => s.rings.flat())
  let svg = null
  if (pts.length) {
    const lat0 = pts.reduce((a, q) => a + q[1], 0) / pts.length
    const kx = Math.cos((lat0 * Math.PI) / 180)
    const xs = pts.map((q) => q[0] * kx), ys = pts.map((q) => q[1])
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    const W = 600, H = 260, pad = 14, s = Math.min((W - 2 * pad) / (x1 - x0 || 1e-6), (H - 2 * pad) / (y1 - y0 || 1e-6))
    const P = (q) => `${pad + (q[0] * kx - x0) * s},${H - pad - (q[1] - y0) * s}`
    svg = (
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[260px] bg-[#f3f5f0] rounded" role="img" aria-label="Building footprints">
        {shapes.map(({ b, rings: rs }) => rs.map((r, i) => (
          <polygon key={`${b.building_id}-${i}`} points={r.map(P).join(' ')} onClick={() => run.act('open_building', { building_id: b.building_id }).catch(() => {})}
            className="cursor-pointer" fill={b.excluded ? '#d5d9d1' : b.building_id === p.focus_building_id ? '#335d45' : '#7f9c7c'} stroke="#335d45" strokeWidth="1">
            <title>{b.name}</title>
          </polygon>
        )))}
      </svg>
    )
  }
  return (
    <div className="space-y-2">
      {svg || <Empty>Footprints not available.</Empty>}
      <p className="text-[11px] text-muted">Footprints in 2D from the building records (a 3D view is not available). Click a building to open it.</p>
      <ul className="grid grid-cols-2 gap-x-4 text-[12px]">
        {p.buildings.map((b) => (
          <li key={b.building_id} className="flex justify-between border-b border-line/60 py-1">
            <button type="button" className={`text-left hover:text-brand ${b.excluded ? 'text-muted line-through' : ''}`}
              onClick={() => run.act('open_building', { building_id: b.building_id }).catch(() => {})}>{b.name}</button>
            <span className="flex gap-2">
              <span className="text-muted tabular-nums">{isNum(b.color_value) ? fmt.t(b.color_value) : 'not in plan'}</span>
              <button type="button" className="text-brand" onClick={() => run.act(b.excluded ? 'include_building' : 'exclude_building', { building_id: b.building_id }).catch(() => {})}>
                {b.excluded ? 'Include' : 'Exclude'}
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ---- hero_3d: the Matterport tour (showcase) or the mesh files ---------------------------------------------------------------
function Hero3D({ p }) {
  if (p.mode === 'showcase' && p.showcase_url) {
    return (
      <div className="space-y-2">
        <iframe title="Matterport 3D tour" src={p.showcase_url} className="w-full h-[360px] rounded border border-line" allow="fullscreen; xr-spatial-tracking" />
        <p className="text-[11px] text-muted">Matterport 3D tour · {p.pins.length} finding pin{p.pins.length === 1 ? '' : 's'} recorded (positions are in mesh coordinates)</p>
      </div>
    )
  }
  return (
    <div className="space-y-2 text-[13px]">
      <p>3D mesh available: <a className="text-brand underline" href={mediaUrlAbs(p.mesh_url)}>OBJ</a>{p.mtl_url && <> · <a className="text-brand underline" href={mediaUrlAbs(p.mtl_url)}>MTL</a></>}</p>
      <p className="text-[11px] text-muted">An in-page 3D viewer is not available. {p.pins.length} finding pin{p.pins.length === 1 ? '' : 's'}.</p>
      <ul className="text-[12px]">{p.pins.map((pin) => <li key={pin.claim_id}>{pin.label} · {pin.status}</li>)}</ul>
    </div>
  )
}
const mediaUrlAbs = (path) => (path ? API_BASE + path : null)

// ---- abatement_curve -------------------------------------------------------------------------------------------------------
function AbatementCurve({ p }) {
  const run = useRun()
  const stub = useStub().engine
  const bars = [...p.bars].sort((a, b) => a.cost_per_tonne - b.cost_per_tonne)
  if (!bars.length) return <Empty>No upgrades on the curve.</Empty>
  const total = bars.reduce((s, b) => s + b.tonnes_per_year, 0) || 1
  const maxAbs = Math.max(1, ...bars.map((b) => Math.abs(b.cost_per_tonne)))
  const W = 600, H = 220, mid = H / 2, ky = (mid - 12) / maxAbs
  let x = 0
  return (
    <div className="space-y-1">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[220px]" role="img" aria-label="Abatement cost curve">
        <line x1="0" x2={W} y1={mid} y2={mid} stroke="#9aa68f" />
        {bars.map((b) => {
          const w = (b.tonnes_per_year / total) * W, h = Math.abs(b.cost_per_tonne) * ky
          const el = (
            <rect key={b.upgrade_id} x={x + 0.5} width={Math.max(1, w - 1)} y={b.cost_per_tonne < 0 ? mid : mid - h} height={Math.max(1, h)}
              fill={b.in_plan ? (b.cost_per_tonne < 0 ? '#335d45' : '#7f9c7c') : '#dde4d5'} className="cursor-pointer"
              onClick={() => run.act('select_bar', { upgrade_id: b.upgrade_id }).catch(() => {})}>
              <title>{`${upgradeLabel(b.type)} · ${b.building_name}: ${fmt.perT(b.cost_per_tonne)}, ${fmt.t(b.tonnes_per_year)}${b.in_plan ? ' (in plan)' : ''}`}</title>
            </rect>
          )
          x += w
          return el
        })}
      </svg>
      <p className="text-[11px] text-muted">
        Width = tonnes avoided per year, height = net cost per tonne (below the line pays for itself). Dark = in the plan. Range ±{fmt.perT(maxAbs)}.{stub && <Stub />}
      </p>
    </div>
  )
}

// ---- plan_table -----------------------------------------------------------------------------------------------------------------
function PlanTable({ p }) {
  const stub = useStub().engine
  return (
    <div className="space-y-2">
      <table className="w-full text-[12px]">
        <thead><tr className="text-left text-muted">{['Building', 'Upgrade', 'Size', 'Upfront', 'Expected NPV', '$/t', 't/yr', 'Verified'].map((h) => <th key={h} className="font-medium pb-1 pr-2">{h}</th>)}</tr></thead>
        <tbody>
          {p.rows.map((r) => (
            <tr key={r.upgrade_id} className="border-t border-line/60">
              <td className="py-1 pr-2">{r.building_name}</td><td className="pr-2">{upgradeLabel(r.type)}</td><td className="pr-2 tabular-nums">{r.size}</td>
              <td className="pr-2 tabular-nums">{fmt.usd(r.upfront_usd)}</td><td className="pr-2 tabular-nums">{fmt.usd(r.exp_npv)}</td>
              <td className="pr-2 tabular-nums">{fmt.perT(r.cost_per_tonne)}</td><td className="pr-2 tabular-nums">{fmt.num(r.tonnes_per_year)}</td>
              <td>{r.verified === 'assumed' ? <Estimate>assumed</Estimate> : r.verified}{r.owner_included && ' · owner-included'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!p.rows.length && <Empty>No upgrades selected.</Empty>}
      <p className="text-[12px] tabular-nums">Total upfront {fmt.usd(p.totals.upfront_usd)} · expected NPV {fmt.usd(p.totals.exp_npv)} · {fmt.t(p.totals.tonnes_per_year)}{(stub || p.sample_pricing) && <Stub />}</p>
    </div>
  )
}

// ---- risk_histogram -------------------------------------------------------------------------------------------------------------
function RiskHistogram({ p }) {
  const stub = useStub().engine
  if (!p.bins?.length) return <Empty>Distribution not available.</Empty>
  const max = Math.max(1, ...p.bins.map((b) => b.count))
  return (
    <div className="space-y-2">
      <div className="flex items-end gap-[2px] h-[120px]" role="img" aria-label="Distribution of lifetime net value">
        {p.bins.map((b, i) => <div key={i} title={`${fmt.usd(b.x0)} to ${fmt.usd(b.x1)}: ${b.count}`} className={`flex-1 ${(b.x0 + b.x1) / 2 < 0 ? 'bg-[#7a693b]' : 'bg-brand'}`} style={{ height: `${(b.count / max) * 100}%` }} />)}
      </div>
      <p className="text-[11px] text-muted tabular-nums">{fmt.usd(p.bins[0].x0)} … {fmt.usd(p.bins[p.bins.length - 1].x1)} · {p.scope === 'building' ? 'this building' : 'the plan'}</p>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Expected NPV" value={fmt.usd(p.exp_npv)} stub={stub} />
        <Stat label="Worst 5% average" value={fmt.usd(p.cvar5)} stub={stub} />
        <Stat label="Chance of a loss" value={fmt.pct(p.p_loss)} stub={stub} />
      </div>
    </div>
  )
}

// ---- evidence_gallery -------------------------------------------------------------------------------------------------------------
const STATUS_COLOR = { verified: 'text-brand', rejected: 'text-[#b4532f]', unverified: 'text-[#b4532f]', sent_back: 'text-[#9a6a1f]', pending: 'text-muted' }
function EvidenceGallery({ p }) {
  if (!p.items.length) return <Empty>No evidence images.</Empty>
  return (
    <div className="grid grid-cols-3 gap-3">
      {p.items.map((it) => (
        <figure key={it.image_id} className="space-y-1">
          <div className="relative aspect-square overflow-hidden rounded bg-[#f3f5f0]">
            <img src={mediaUrl(it.image_id)} alt={`${it.source || 'survey'} image`} className="absolute inset-0 w-full h-full object-cover" />
            {it.marks.filter((m) => m.bbox).map((m, i) => (
              <div key={i} title={m.label} className="absolute border-2 border-white shadow"
                style={{ left: `${m.bbox[0] * 100}%`, top: `${m.bbox[1] * 100}%`, width: `${(m.bbox[2] - m.bbox[0]) * 100}%`, height: `${(m.bbox[3] - m.bbox[1]) * 100}%` }} />
            ))}
          </div>
          <figcaption className="text-[11px]">
            <span className={`font-medium ${STATUS_COLOR[it.status] || ''}`}>{it.status}</span> · {it.source || 'source not available'}{it.orientation ? ` · ${it.orientation}` : ''}
            {it.claim_summaries.map((c, i) => <div key={i} className="text-muted">{c}</div>)}
            {it.verifier_notes.map((n, i) => <div key={`n${i}`} className="text-[#7a693b]">Verifier: {n}</div>)}
          </figcaption>
        </figure>
      ))}
    </div>
  )
}

// ---- facade_compass ----------------------------------------------------------------------------------------------------------------
function FacadeCompass({ p }) {
  const sides = ['N', 'E', 'S', 'W']
  if (!Object.keys(p.facades || {}).length) return <Empty>No side imagery: facade data not available.</Empty>
  return (
    <div className="grid grid-cols-4 gap-2 text-center">
      {sides.map((s) => {
        const f = p.facades[s]
        return (
          <div key={s} className="rounded bg-[#f3f5f0] p-2">
            <p className="font-semibold">{s}</p>
            <p className="text-[12px] tabular-nums">{f ? fmt.pct(f.glazing_ratio) : NA} glazing</p>
            <p className="text-[11px] text-muted tabular-nums">{f && isNum(f.window_count_est) ? <>~{f.window_count_est} windows<Estimate /></> : `windows ${NA}`}</p>
          </div>
        )
      })}
    </div>
  )
}

// ---- floor_plan ---------------------------------------------------------------------------------------------------------------------
function FloorPlan({ p }) {
  if (!p.rooms.length) return <Empty>Floor plan not available.</Empty>
  return (
    <div className="space-y-1 text-[12px]">
      <ul>{p.rooms.map((r) => <li key={r.room_id} className="flex justify-between border-b border-line/60 py-1"><span>{r.type || 'unlabelled room'}</span><span className="tabular-nums text-muted">{isNum(r.area_sqft) ? `${fmt.num(r.area_sqft)} sq ft` : `area ${NA}`}</span></li>)}</ul>
      <p className="text-[11px] text-muted">{p.rooms.some((r) => r.polygon?.length) ? '' : 'Room outlines not available; list only. '}{p.pins.length} finding pin{p.pins.length === 1 ? '' : 's'}.</p>
    </div>
  )
}

// ---- upgrade_list -----------------------------------------------------------------------------------------------------------------
function UpgradeList({ p }) {
  const run = useRun()
  const stub = useStub().engine
  if (!p.upgrades.length) return <Empty>No feasible upgrades.</Empty>
  return (
    <table className="w-full text-[12px]">
      <thead><tr className="text-left text-muted">{['Upgrade', 'Size', 't/yr', 'Upfront', 'Expected NPV', 'Status', 'In plan'].map((h) => <th key={h} className="font-medium pb-1 pr-2">{h}</th>)}</tr></thead>
      <tbody>
        {p.upgrades.map((r) => {
          const u = r.upgrade
          const unverified = u.verified === 'unverified'
          const flip = () => run.act(!r.in_plan && unverified && !r.owner_included ? 'include_unverified' : 'toggle_upgrade',
            !r.in_plan && unverified && !r.owner_included ? { upgrade_id: u.upgrade_id } : { upgrade_id: u.upgrade_id, on: !r.in_plan }).catch(() => {})
          return (
            <tr key={u.upgrade_id} className={`border-t border-line/60 ${r.highlighted ? 'bg-[#edf3e6]' : ''}`}>
              <td className="py-1 pr-2" title={u.reason}>{upgradeLabel(u.type)}</td>
              <td className="pr-2 tabular-nums">{fmt.num(u.size_value)} {u.size_unit}</td>
              <td className="pr-2 tabular-nums">{fmt.num(r.tonnes_per_year)}{stub && isNum(r.tonnes_per_year) && <Stub />}</td>
              <td className="pr-2 tabular-nums">{fmt.usd(r.upfront_usd)}</td>
              <td className="pr-2 tabular-nums">{fmt.usd(r.exp_npv)}</td>
              <td className="pr-2">{u.verified === 'assumed' ? <Estimate>assumed</Estimate> : u.verified}{r.owner_included && ' · owner-included'}</td>
              <td><button type="button" role="switch" aria-checked={r.in_plan} aria-label={`Include ${upgradeLabel(u.type)}`} onClick={flip}
                className={`w-[34px] h-[20px] rounded-full ${r.in_plan ? 'bg-brand' : 'bg-[#c7ccd1]'}`}><span className={`block w-[14px] h-[14px] rounded-full bg-white transition-transform ${r.in_plan ? 'translate-x-[17px]' : 'translate-x-[3px]'}`} /></button></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ---- building_header ---------------------------------------------------------------------------------------------------------------
function BuildingHeader({ p }) {
  const run = useRun()
  const stub = useStub().engine
  const pr = p.profile
  const b = p.baseline || {}
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <div><p className="text-[22px] font-semibold">{pr.name}</p><p className="text-[12px] text-muted">{pr.address || `address ${NA}`} · {pr.property_type || NA}{pr.building_class ? ` · class ${pr.building_class}` : ''}</p></div>
        <button type="button" className="text-brand text-[13px]" onClick={() => run.act('open_building', { building_id: null }).catch(() => {})}>← Portfolio</button>
      </div>
      <div className="grid grid-cols-5 gap-3">
        <Stat label="Floor area (RBA)" value={isNum(pr.rba_sqft) ? `${fmt.num(pr.rba_sqft)} sq ft` : NA} />
        <Stat label="Year built" value={pr.year_built ? String(pr.year_built) : NA} />
        <Stat label="Floors" value={pr.stories ? String(pr.stories) : NA} />
        <Stat label="Annual emissions" value={fmt.t(b.tonnes_per_year)} stub={stub} extra={isNum(b.tonnes_per_year) && <Estimate title="Benchmark estimate (energy use per sq ft for the building type), not metered">estimate</Estimate>} />
        <Stat label="Annual energy spend" value={fmt.usd(b.annual_spend_usd)} stub={stub} extra={isNum(b.annual_spend_usd) && <Estimate title="Benchmark estimate, not utility bills">estimate</Estimate>} />
      </div>
      {pr.footprint_source === 'estimated' && <p className="text-[11px] text-[#7a693b]">Footprint estimated from floor area and floors (no recorded footprint).</p>}
    </div>
  )
}

// ---- target_gap_card ---------------------------------------------------------------------------------------------------------------
function TargetGapCard({ p }) {
  const stub = useStub().engine
  return (
    <div className="space-y-2">
      <Stat label="Short of the target" value={fmt.t(p.shortfall_tonnes)} stub={stub} />
      {p.cheapest_extra.length ? (
        <ul className="text-[12px]">{p.cheapest_extra.map((e) => <li key={e.upgrade_id} className="flex justify-between border-b border-line/60 py-1"><span>{upgradeLabel(String(e.upgrade_id).split(':')[1])} · {String(e.upgrade_id).split(':')[0]}</span><span className="tabular-nums">{fmt.perT(e.cost_per_tonne)} · {fmt.t(e.tonnes_per_year)}</span></li>)}</ul>
      ) : <Empty>No single extra upgrade can close the gap.</Empty>}
    </div>
  )
}

// ---- financing_card ----------------------------------------------------------------------------------------------------------------
function FinancingCard({ p }) {
  const run = useRun()
  const { engine, nessie } = useStub()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const approve = async () => {
    setBusy(true); setErr(null)
    try { await run.act('approve', { plan_id: p.plan_id }) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2 text-[13px]">
      <Stat label="Total upfront" value={fmt.usd(p.total_upfront_usd)} stub={engine} />
      <ul className="text-[12px]">{p.bills.map((b) => <li key={b.contractor} className="flex justify-between border-b border-line/60 py-1"><span>{b.contractor}</span><span className="tabular-nums">{fmt.usd(b.amount)}</span></li>)}</ul>
      {!p.bills.length && <Empty>Contractor bills are created on approval.</Empty>}
      {p.state === 'executed' ? (
        <div className="text-[12px]">
          <p className="font-medium text-brand">Executed{nessie ? ' (simulated: stub Nessie)' : ' in the Nessie sandbox'}{nessie && <Stub title="Simulated booking, nothing was sent to a bank" />}</p>
          <ul className="text-muted">{Object.entries(p.nessie_ids || {}).map(([k, v]) => <li key={k}>{k}: <span className="font-mono">{v}</span></li>)}</ul>
        </div>
      ) : (
        <button type="button" onClick={approve} disabled={busy || !p.plan_id}
          className="w-full h-[38px] rounded bg-brand text-white font-medium disabled:opacity-50">{busy ? 'Approving…' : 'Approve & fund'}</button>
      )}
      {err && <p className="text-[12px] text-[#b4532f]">{err}</p>}
      <p className="text-[11px] text-muted">Plan {p.plan_id || NA}</p>
    </div>
  )
}

// ---- memo / activity_feed --------------------------------------------------------------------------------------------------------
function MemoWidget({ p }) {
  return p.markdown ? <Markdown text={p.markdown} /> : <Empty>The memo is written after the plan is approved.</Empty>
}

function ActivityFeed() {
  const run = useRun()
  const rows = feedRows(run.events, 14).reverse()
  if (!rows.length) return <Empty>No events loaded.</Empty>
  return (
    <ol className="space-y-2 text-[12px]">
      {rows.map((e) => (
        <li key={e.seq ?? `${e.time}${e.msg}`}>
          <span className="text-muted tabular-nums">{e.time}</span> <span className="font-medium text-brand">{e.agent}</span>
          <div>{e.msg}</div>{e.meta && e.meta !== e.kind && <div className="text-[10px] text-muted">{e.meta}</div>}
        </li>
      ))}
    </ol>
  )
}

export const RENDERERS = {
  target_control: TargetControl, portfolio_3d: Portfolio3D, hero_3d: Hero3D, abatement_curve: AbatementCurve, plan_table: PlanTable,
  risk_histogram: RiskHistogram, evidence_gallery: EvidenceGallery, facade_compass: FacadeCompass, floor_plan: FloorPlan,
  upgrade_list: UpgradeList, building_header: BuildingHeader, target_gap_card: TargetGapCard, financing_card: FinancingCard,
  memo: MemoWidget, activity_feed: ActivityFeed,
}
