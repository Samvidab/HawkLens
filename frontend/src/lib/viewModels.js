// Maps the backend's layout widgets onto the shapes the existing Figma pages already render.
// Pure functions: `layout` is the object returned by POST /compose or GET /state (`state.layout`). Widgets are
// looked up BY TYPE (the composer may reorder, drop or add widgets), and every selector returns null when its
// widget is absent. Strict: nothing is invented; a missing value is shown as NA ("not available"), never a sample.
// Money from the API is raw USD (may be null); tonnes are per year; *_pct is 0-100, probabilities are 0-1.

export const NA = 'not available'

export const UPGRADE_LABEL = {
  rooftop_solar: 'Rooftop solar',
  cool_roof: 'Cool roof',
  window_upgrade: 'Window upgrade',
  heat_pump: 'Heat pump conversion',
  insulation: 'Insulation',
  led_retrofit: 'LED retrofit',
}
export const upgradeLabel = (t) => UPGRADE_LABEL[t] || String(t || '').replace(/_/g, ' ')

// ---- formatting ("$9,506k", "+$120k", "1,234 tonnes / year"; missing -> NA) ------------------------------------
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
export const usdK = (usd) => (num(usd) === null ? NA : `$${Math.round(usd / 1000).toLocaleString('en-US')}k`)
export const signedUsdK = (usd) => (num(usd) === null ? NA : `${usd >= 0 ? '+' : '−'}${usdK(Math.abs(usd))}`)
export const usd = (v) => (num(v) === null ? NA : `$${Math.round(v).toLocaleString('en-US')}`)
export const signedUsd = (v) => (num(v) === null ? NA : `${v >= 0 ? '+' : '−'}${usd(Math.abs(v))}`)
export const tonnesFmt = (v) => (num(v) === null ? NA : Math.round(v).toLocaleString('en-US'))
export const pct = (p, digits = 0) => (num(p) === null ? NA : `${(p * 100).toFixed(digits)}%`)

// risk_lambda (engine): maximise E[NPV] + lambda x CVaR5, so 0 = expected NPV only (Growth) and higher = more weight on the
// worst-5 % outcome (Cautious). Three positions, Balanced in the middle. The effect saturates early on real portfolios
// (lambda 0.2 and 0.4 often give the same plan), and solves above ~0.5 can take over 3 s, so the scale stays small.
export const RISK_LABELS = ['Cautious', 'Balanced', 'Growth']
export const RISK_LAMBDA = { Cautious: 0.4, Balanced: 0.2, Growth: 0 }
export const riskLabel = (lambda) => (lambda < 0.1 ? 'Growth' : lambda > 0.3 ? 'Cautious' : 'Balanced')

// ---- widget access --------------------------------------------------------------------------------------------------
export const widget = (layout, type) => layout?.widgets?.find((w) => w.type === type)?.props ?? null
export const planIdOf = (layout, state) =>
  state?.plan_id ?? widget(layout, 'financing_card')?.plan_id ?? null

// ---- Portfolio: drop-in for lib/model.js deriveModel() ---------------------------------------------------------------
export function targetModel(layout) {
  const tc = widget(layout, 'target_control')
  if (!tc) return null
  const planned = num(tc.tonnes_planned)
  const needed = num(tc.tonnes_needed)
  const totals = widget(layout, 'plan_table')?.totals ?? {}
  const known = planned !== null && needed !== null
  const covered = known ? planned >= needed : null // null = not known: never claim "covered" without both numbers
  const tonnes = planned === null ? null : Math.round(planned)
  return {
    target: tc.target_pct,
    tonnes,
    investmentLabel: usdK(totals.upfront_usd),
    netValueLabel: signedUsdK(totals.exp_npv),
    covered,
    statusLabel: covered === null ? 'Coverage not available' : covered ? 'Your goal is covered' : 'Short of your goal',
    annualLabel: tonnes === null ? `Planned tonnes ${NA}` : `${tonnes.toLocaleString('en-US')} tonnes / year`,
    confidence: num(tc.p_hit_target) === null ? null : Math.round(tc.p_hit_target * 100),
    shortfall: known ? Math.max(0, Math.round(needed - planned)) : null,
    surplus: known ? Math.max(0, Math.round(planned - needed)) : null,
    tonnesNeeded: needed === null ? null : Math.round(needed),
    budgetUsd: tc.budget_usd ?? null,
    riskLambda: tc.risk_lambda,
    riskSupported: tc.risk_supported !== false,
    sample: !!widget(layout, 'plan_table')?.sample_pricing,
  }
}

export function portfolioBuildings(layout) {
  const p = widget(layout, 'portfolio_3d')
  return p ? p.buildings.map((b) => ({ id: b.building_id, name: b.name, excluded: b.excluded, tonnes: b.color_value })) : null
}

// ---- Plan: metric strip, upgrade breakdown ---------------------------------------------------------------------------
export function planMetrics(layout) {
  const m = targetModel(layout)
  if (!m) return null
  const totals = widget(layout, 'plan_table')?.totals ?? {}
  return [
    { label: 'Annual CO₂ reduction', value: m.tonnes === null ? NA : `${m.tonnes.toLocaleString('en-US')} tonnes / year`,
      sub: m.covered === null ? 'Coverage not available' : m.covered ? 'Your goal is covered' : `${m.shortfall.toLocaleString('en-US')} t/yr short of your goal`, left: 0 },
    { label: 'Lifetime net value', value: signedUsdK(totals.exp_npv), sub: 'After retrofit costs', left: 338 },
    { label: 'Upfront investment', value: usdK(totals.upfront_usd),
      sub: `Budget ${m.budgetUsd == null ? 'not set' : usdK(m.budgetUsd)} · ${riskLabel(m.riskLambda)} risk`, left: 676 },
    { label: 'Chance of hitting the target', value: m.confidence === null ? NA : `${m.confidence}%`,
      sub: m.sample ? 'Sample pricing · not the quant engine' : 'Simulated outcomes · quant engine', left: 1014 },
  ]
}

/** plan_table rows are per upgrade per building; the page shows one row per upgrade type. */
export function planRows(layout) {
  const t = widget(layout, 'plan_table')
  if (!t) return null
  const groups = new Map()
  for (const r of t.rows) {
    const g = groups.get(r.type) || { type: r.type, buildings: new Set(), upfront: 0, npv: 0, tonnes: 0, unverified: 0 }
    g.buildings.add(r.building_name)
    // a group with any missing value has an unknown total (null), not a partial sum
    g.upfront = g.upfront === null || num(r.upfront_usd) === null ? null : g.upfront + r.upfront_usd
    g.npv = g.npv === null || num(r.exp_npv) === null ? null : g.npv + r.exp_npv
    g.tonnes = g.tonnes === null || num(r.tonnes_per_year) === null ? null : g.tonnes + r.tonnes_per_year
    g.unverified += r.verified === 'unverified' ? 1 : 0
    groups.set(r.type, g)
  }
  return [...groups.values()].map((g) => ({
    name: upgradeLabel(g.type),
    coverage: `${g.buildings.size} building${g.buildings.size === 1 ? '' : 's'}`,
    cost: usdK(g.upfront),
    co2: g.tonnes === null ? NA : `${tonnesFmt(g.tonnes)} tCO₂`,
    unverified: g.unverified,
    npv: signedUsdK(g.npv),
  }))
}

export function planSummary(layout) {
  const t = widget(layout, 'plan_table')
  if (!t) return null
  const m = targetModel(layout) // absent on the `approved` layout
  const n = t.rows.length
  const nb = new Set(t.rows.map((r) => r.building_name)).size
  return {
    upgrades: n, buildings: nb, target: m?.target ?? null,
    line: m ? `${n} upgrades · ${m.target}% reduction goal` : `${n} upgrades`, count: `${n} upgrades across ${nb} buildings`,
  }
}

// ---- Abatement curve -> the fixed chart on the Plan page --------------------------------------------------------------
const CHART = { x0: 64, width: 562, zeroY: 165, maxDown: 45, maxUp: 50, gap: 3 }
/** bars: [{name,left,top,width,height,profitable}], plus axis ticks computed from the actual scales. */
export function abatementGeometry(layout) {
  const c = widget(layout, 'abatement_curve')
  if (!c || !c.bars.length) return null
  const bars = [...c.bars].sort((a, b) => a.cost_per_tonne - b.cost_per_tonne)
  const total = bars.reduce((s, b) => s + b.tonnes_per_year, 0) + CHART.gap * (bars.length - 1)
  const kx = Math.min(0.4251, (CHART.width - 8 - CHART.gap * (bars.length - 1)) / Math.max(1, total - CHART.gap * (bars.length - 1)))
  const maxNeg = Math.max(1, ...bars.filter((b) => b.cost_per_tonne < 0).map((b) => -b.cost_per_tonne))
  const maxPos = Math.max(1, ...bars.filter((b) => b.cost_per_tonne >= 0).map((b) => b.cost_per_tonne))
  const ky = Math.min(0.47, CHART.maxDown / maxNeg, CHART.maxUp / maxPos)
  let left = CHART.x0 + 1
  const out = bars.map((b) => {
    const width = Math.max(2, b.tonnes_per_year * kx)
    const h = Math.max(1, Math.abs(b.cost_per_tonne) * ky)
    const bar = { name: `${upgradeLabel(b.type)} · ${b.building_name}`, upgradeId: b.upgrade_id, buildingId: b.building_id, inPlan: b.in_plan,
      profitable: b.cost_per_tonne < 0, left, width, height: h, top: b.cost_per_tonne < 0 ? CHART.zeroY : CHART.zeroY - h }
    left += width + CHART.gap
    return bar
  })
  const yTick = 47 / ky // dollars at the +/- grid lines (47 px from $0)
  const xMax = (CHART.width - 8) / kx
  const niceX = Math.max(1, Math.round(xMax / 3 / 100) * 100)
  return {
    bars: out, ky, kx,
    yLabel: Math.max(1, Math.round(yTick)), // dollars at the grid lines 47 px above/below $0 (exact, not rounded to a nice number)
    referenceLeft: (tonnes) => Math.min(CHART.x0 + CHART.width, CHART.x0 + tonnes * kx),
    xTicks: [0, 1, 2, 3].map((i) => ({ label: String(i * niceX), left: CHART.x0 - 5 + i * niceX * kx })),
    profitableTonnes: Math.round(bars.filter((b) => b.cost_per_tonne < 0).reduce((s, b) => s + b.tonnes_per_year, 0)),
  }
}

// ---- Risk histogram -> the bars on the Risk page ----------------------------------------------------------------------
const HIST = { left: 56, width: 551, baseY: 262, maxH: 158, gap: 3 }
export function riskModel(layout) {
  const h = widget(layout, 'risk_histogram')
  if (!h || !h.bins?.length) return null
  const bins = h.bins
  const xmin = bins[0].x0
  const xmax = bins[bins.length - 1].x1
  const span = xmax - xmin || 1
  const maxCount = Math.max(1, ...bins.map((b) => b.count))
  const step = HIST.width / bins.length
  const px = (v) => HIST.left + ((v - xmin) / span) * HIST.width
  return {
    bars: bins.map((b, i) => {
      const height = Math.max(1, (b.count / maxCount) * HIST.maxH)
      return { left: HIST.left + i * step, width: Math.max(2, step - HIST.gap), height, top: HIST.baseY - height, loss: (b.x0 + b.x1) / 2 < 0 }
    }),
    breakEven: xmin <= 0 && xmax >= 0 ? px(0) : null,
    axis: [0, 0.25, 0.5, 0.75, 1].map((f) => ({ label: signedAxis(xmin + f * span), left: HIST.left + f * HIST.width - 14 })),
    expNpv: signedUsdK(h.exp_npv), pLoss: h.p_loss == null ? NA : `${(h.p_loss * 100).toFixed(1)}%`,
    worst5: signedUsdK(h.cvar5), scope: h.scope,
    scenarios: bins.reduce((s, b) => s + (b.count || 0), 0), // displayed counts; the engine trims tail percentiles from its histogram
  }
}
const signedAxis = (v) => (Math.abs(v) < 500 ? '$0k' : `${v < 0 ? '−' : ''}$${Math.abs(Math.round(v / 1000)).toLocaleString('en-US')}k`)

// ---- Building detail ---------------------------------------------------------------------------------------------------
export function buildingModel(layout) {
  const h = widget(layout, 'building_header')
  if (!h) return null
  const p = h.profile
  const b = h.baseline || {}
  return {
    id: p.building_id, name: p.name, address: p.address,
    profile: [
      ['Floor area', p.rba_sqft ? `${Math.round(p.rba_sqft).toLocaleString('en-US')} sq ft` : NA],
      ['Year built', p.year_built ? String(p.year_built) : NA],
      ['Floors', p.stories ? String(p.stories) : NA],
      ['Annual emissions', b.tonnes_per_year == null ? NA : `${tonnesFmt(b.tonnes_per_year)} tCO₂`, 'baseline'],
      ['Annual energy spend', b.annual_spend_usd == null ? NA : usd(b.annual_spend_usd), 'baseline'],
    ],
    baselineBasis: b.basis ?? null, // "benchmark estimate": label the baseline rows as estimates
    footprintEstimated: p.footprint_source === 'estimated',
    hasMatterport: !!p.matterport_model_id, type: p.property_type ?? null, city: p.city ?? null,
  }
}

export function upgradeRows(layout) {
  const u = widget(layout, 'upgrade_list')
  if (!u) return null
  return u.upgrades.map((r) => ({
    key: r.upgrade.upgrade_id, id: r.upgrade.upgrade_id, type: r.upgrade.type, evidenceIds: r.upgrade.evidence_ids || [],
    name: `${upgradeLabel(r.upgrade.type)} · ${num(r.upgrade.size_value) === null ? `size ${NA}` : `${Math.round(r.upgrade.size_value).toLocaleString('en-US')} ${r.upgrade.size_unit}`}`,
    on: !!r.in_plan, verified: r.upgrade.verified, ownerIncluded: !!r.owner_included, includable: r.upgrade.verified === 'unverified' && !r.in_plan,
    reason: r.upgrade.reason, confidence: r.upgrade.confidence, highlighted: !!r.highlighted,
    co2: r.tonnes_per_year == null ? NA : `${tonnesFmt(r.tonnes_per_year)} tonnes`, cost: usd(r.upfront_usd), npv: signedUsd(r.exp_npv),
    tonnes: r.tonnes_per_year, upfrontUsd: r.upfront_usd,
  }))
}

/** What this building contributes to the current plan (sum over its in-plan upgrades). */
export function buildingTotals(layout) {
  const rows = (upgradeRows(layout) || []).filter((r) => r.on)
  const add = (a, v) => (a === null || num(v) === null ? null : a + v)
  const t = rows.reduce((a, r) => ({ tonnes: add(a.tonnes, r.tonnes), upfront: add(a.upfront, r.upfrontUsd) }), { tonnes: 0, upfront: 0 })
  if (!rows.length) return { n: 0, line: 'No upgrades of this building are in the plan' }
  return { n: rows.length, line: `${t.tonnes === null ? `tonnes ${NA}` : `${tonnesFmt(t.tonnes)} tCO₂ / year`} · ${usdK(t.upfront)} investment` }
}

// ---- Evidence ---------------------------------------------------------------------------------------------------------
export function evidenceModel(layout, mediaUrl) {
  const g = widget(layout, 'evidence_gallery')
  if (!g) return null
  const items = g.items.map((i) => ({
    id: i.image_id, url: mediaUrl(i.image_id), source: i.source, status: i.status, marks: i.marks,
    summaries: i.claim_summaries, notes: i.verifier_notes,
    // titles and providers only from recorded fields: an image without a recorded source says so
    title: i.source === 'matterport_pano' ? 'Interior panorama' : i.orientation ? `${i.orientation} facade`
      : /overhead|aerial|roof/i.test(i.source || '') ? 'Roof · aerial' : 'Survey image',
    provider: /matterport/i.test(i.source || '') ? 'Matterport' : /vexcel/i.test(i.source || '') ? 'Vexcel'
      : /costar/i.test(i.source || '') ? 'CoStar' : 'Source not recorded',
  }))
  return { items }
}

// ---- Financing / approval ----------------------------------------------------------------------------------------------
export function financingModel(layout, state) {
  const plan = state?.plan?.plan_id && state.plan.plan_id === state.plan_id ? state.plan : null
  const saved = plan?.financing
  const f = widget(layout, 'financing_card')
  const planId = planIdOf(layout, state)
  const t = widget(layout, 'plan_table')
  if (!f && !t && !plan) return null
  const recordedBills = f?.bills || plan?.bills
  const bills = recordedBills?.length ? recordedBills.map((b) => ({ name: b.contractor, amount: usdK(b.amount) }))
    : null
  return {
    planId, executed: (saved?.state ?? f?.state) === 'executed', nessieIds: saved?.nessie_ids ?? f?.nessie_ids ?? null,
    total: usdK(f?.total_upfront_usd ?? t?.totals?.upfront_usd ?? plan?.total_upfront), totalUsd: f?.total_upfront_usd ?? t?.totals?.upfront_usd ?? plan?.total_upfront ?? null,
    bills, upgrades: t ? t.rows.length : null,
  }
}

export const memoMarkdown = (layout, state) => widget(layout, 'memo')?.markdown || (state?.plan?.plan_id && state.plan.plan_id === state.plan_id ? state.memo_markdown : null) || null

// ---- Survey screens: from the activity events -----------------------------------------------------------------------------
export const clock = (ts) => (ts ? new Date(ts).toISOString().slice(11, 19) : '')

export function feedRows(events, n = 6) {
  return events.slice(-n).map((e) => ({
    time: clock(e.ts), agent: e.agent, msg: e.message,
    meta: [e.building_name, e.evidence_id && `Evidence ${e.evidence_id}`].filter(Boolean).join(' · ') || e.kind, kind: e.kind, seq: e.seq,
  }))
}

/** Progress per survey layer, from which buildings each agent has reported on. */
export function surveyProgress(events, total) {
  const seen = (agent, kinds) => new Set(events.filter((e) => e.agent === agent && e.building_id && (!kinds || kinds.includes(e.kind))).map((e) => e.building_id))
  const done = events.some((e) => e.kind === 'done')
  const row = (label, n, tot, pendingText) => ({ label, detail: tot ? `${n} / ${tot} complete` : pendingText, done: tot ? n >= tot : false })
  return [
    row('Records', seen('Records').size, total),
    row('Aerial inspection', seen('Aerial').size, total),
    { label: 'Interior inspection', detail: seen('Interior').size ? `${seen('Interior').size} building scanned` : done ? 'Hero building complete' : 'Hero building pending', done: seen('Interior').size > 0 },
    { label: 'Verification', detail: done ? 'Complete' : seen('Verifier').size ? `${seen('Verifier').size} / ${total || '…'} checked` : 'In progress', done },
  ]
}

export function surveySummary(state, layout) {
  if (!state) return null
  const res = Object.values(state.results || {})
  const ok = res.filter((r) => r.status === 'done')
  const claims = ok.reduce((a, r) => { for (const [k, v] of Object.entries(r.claims || {})) a[k] = (a[k] || 0) + v; return a }, {})
  const bad = (claims.unverified || 0) + (claims.rejected || 0)
  return [
    { label: 'Aerial coverage', value: `${ok.length} building${ok.length === 1 ? '' : 's'}` },
    { label: 'Interior coverage', value: `${ok.filter((r) => r.interior).length} hero building` },
    { label: 'Feasible upgrades', value: `${ok.reduce((s, r) => s + (r.upgrades || 0), 0)} upgrades` },
    { label: 'Unverified claims', value: bad ? `${bad} excluded from plan` : 'None' },
  ]
}
