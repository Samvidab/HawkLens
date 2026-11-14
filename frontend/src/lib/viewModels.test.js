import { describe, expect, it } from 'vitest'
import overview from '../test/fixtures/portfolio_overview.json'
import gap from '../test/fixtures/target_gap.json'
import detail from '../test/fixtures/building_detail.json'
import showcase from '../test/fixtures/building_detail_showcase.json'
import approved from '../test/fixtures/approved.json'
import issue from '../test/fixtures/verification_issue.json'
import * as vm from './viewModels'

const without = (layout, ...types) => ({ ...layout, widgets: layout.widgets.filter((w) => !types.includes(w.type)) })
const shuffled = (layout) => ({ ...layout, widgets: [...layout.widgets].reverse() })

describe('formatting', () => {
  it('money, tonnes and percentages like the Figma screens', () => {
    expect(vm.usdK(1_280_000)).toBe('$1,280k')
    expect(vm.signedUsdK(486_400)).toBe('+$486k')
    expect(vm.signedUsdK(-94_000)).toBe('−$94k')
    expect(vm.usd(152000)).toBe('$152,000')
    expect(vm.signedUsd(-26000)).toBe('−$26,000')
    expect(vm.tonnesFmt(1032.4)).toBe('1,032')
    expect([vm.usdK(null), vm.signedUsdK(undefined), vm.usd(NaN), vm.tonnesFmt(null), vm.pct(null)]).toEqual(['—', '—', '—', '—', '—'])
  })
  it('risk labels map both ways', () => {
    expect(vm.riskLabel(0.2)).toBe('Cautious'); expect(vm.riskLabel(0.5)).toBe('Balanced'); expect(vm.riskLabel(0.8)).toBe('Growth')
    for (const l of vm.RISK_LABELS) expect(vm.riskLabel(vm.RISK_LAMBDA[l])).toBe(l)
  })
})

describe('widgets are found by type, never by position', () => {
  it('survives reordering and a dropped widget', () => {
    expect(vm.targetModel(shuffled(overview)).target).toBe(25)
    expect(vm.planRows(without(overview, 'financing_card'))).toHaveLength(vm.planRows(overview).length)
  })
  it('every selector returns null when its widget is absent (pages then show their prototype data)', () => {
    const none = { situation: 'portfolio_overview', widgets: [] }
    for (const f of [vm.targetModel, vm.portfolioBuildings, vm.planMetrics, vm.planRows, vm.planSummary, vm.abatementGeometry, vm.riskModel,
      vm.buildingModel, vm.upgradeRows, vm.financingModel, vm.memoMarkdown]) {
      expect(f(none), f.name).toBeNull()
    }
    expect(vm.evidenceModel(none, (id) => id)).toBeNull()
  })
})

describe('portfolio / plan', () => {
  it('targetModel is a drop-in for deriveModel()', () => {
    const m = vm.targetModel(overview)
    expect(m).toMatchObject({ target: 25, covered: true, statusLabel: 'Your goal is covered' })
    expect(m.annualLabel).toMatch(/^[\d,]+ tonnes \/ year$/)
    expect(m.investmentLabel).toMatch(/^\$[\d,]+k$/); expect(m.netValueLabel).toMatch(/^[+−]\$[\d,]+k$/)
    expect(m.confidence).toBeGreaterThanOrEqual(0); expect(m.confidence).toBeLessThanOrEqual(100)
    expect(m.sample).toBe(true) // the samples use the stub engine
    expect(m.riskSupported).toBe(false)
  })
  it('an unreachable target is not covered and reports the shortfall', () => {
    const m = vm.targetModel(gap)
    expect(m.covered).toBe(false); expect(m.statusLabel).toBe('Short of your goal'); expect(m.shortfall).toBeGreaterThan(0); expect(m.surplus).toBe(0)
    expect(vm.planMetrics(gap)[0].sub).toMatch(/short of your goal/)
  })
  it('planMetrics has the four strip metrics at the Figma offsets', () => {
    const ms = vm.planMetrics(overview)
    expect(ms.map((m) => m.left)).toEqual([0, 338, 676, 1014])
    expect(ms[2].sub).toMatch(/^Budget .* · (Cautious|Balanced|Growth) risk$/)
  })
  it('planRows aggregates upgrades per type', () => {
    const rows = vm.planRows(overview)
    const raw = overview.widgets.find((w) => w.type === 'plan_table').props.rows
    expect(rows.length).toBe(new Set(raw.map((r) => r.type)).size)
    expect(rows.every((r) => r.name && /building/.test(r.coverage) && /^\$/.test(r.cost) && /tCO₂$/.test(r.co2))).toBe(true)
    expect(vm.planSummary(overview).count).toBe(`${raw.length} upgrades across ${new Set(raw.map((r) => r.building_name)).size} buildings`)
  })
  it('planSummary also works on the approved layout (no target widget)', () => {
    expect(vm.targetModel(approved)).toBeNull()
    expect(vm.planSummary(approved).count).toMatch(/\d+ upgrades across \d+ buildings/)
  })
})

describe('abatement chart geometry fits the fixed chart area', () => {
  const g = vm.abatementGeometry(overview)
  it('bars are sorted by cost, split by sign, and stay inside the plot', () => {
    expect(g.bars.length).toBe(overview.widgets.find((w) => w.type === 'abatement_curve').props.bars.length)
    for (const b of g.bars) {
      expect(b.left).toBeGreaterThanOrEqual(64); expect(b.left + b.width).toBeLessThanOrEqual(64 + 562 + 2)
      expect(b.width).toBeGreaterThan(0); expect(b.height).toBeGreaterThan(0)
      if (b.profitable) { expect(b.top).toBe(165); expect(b.height).toBeLessThanOrEqual(45.01) } else { expect(b.top + b.height).toBeCloseTo(165); expect(b.height).toBeLessThanOrEqual(50.01) }
    }
    const lefts = g.bars.map((b) => b.left); expect(lefts).toEqual([...lefts].sort((a, b) => a - b))
    const profitable = g.bars.map((b) => b.profitable); expect(profitable).toEqual([...profitable].sort((a, b) => b - a)) // profitable first
  })
  it('axis labels come from the actual scales', () => {
    expect(g.xTicks).toHaveLength(4); expect(g.xTicks[0].label).toBe('0')
    expect(g.yLabel).toBeGreaterThan(0)
    expect(g.referenceLeft(1e9)).toBeLessThanOrEqual(64 + 562)
  })
})

describe('risk histogram', () => {
  const r = vm.riskModel(overview)
  it('30 bars inside the plot with a break-even line and the headline numbers', () => {
    expect(r.bars).toHaveLength(30)
    for (const b of r.bars) { expect(b.left).toBeGreaterThanOrEqual(56); expect(b.left + b.width).toBeLessThanOrEqual(56 + 551 + 1); expect(b.top + b.height).toBeCloseTo(262); expect(b.height).toBeLessThanOrEqual(158.01) }
    expect(Math.max(...r.bars.map((b) => b.height))).toBeCloseTo(158)
    expect(r.axis).toHaveLength(5); expect(r.expNpv).toMatch(/^[+−]\$/); expect(r.pLoss).toMatch(/%$/)
    if (r.breakEven !== null) { expect(r.breakEven).toBeGreaterThanOrEqual(56); expect(r.breakEven).toBeLessThanOrEqual(56 + 551) }
  })
  it('no break-even line when every outcome is positive', () => {
    const lay = JSON.parse(JSON.stringify(overview))
    const bins = lay.widgets.find((w) => w.type === 'risk_histogram').props.bins
    bins.forEach((b, i) => { b.x0 = 1000 + i; b.x1 = 1001 + i })
    expect(vm.riskModel(lay).breakEven).toBeNull()
    expect(vm.riskModel(lay).bars.every((b) => !b.loss)).toBe(true)
  })
})

describe('building detail', () => {
  it('profile, upgrades with the engine numbers, and the building totals', () => {
    const b = vm.buildingModel(detail)
    expect(b.name).toBe('Sample Tower'); expect(b.profile.map((p) => p[0])).toEqual(['Floor area', 'Year built', 'Floors', 'Annual emissions', 'Annual energy spend'])
    const rows = vm.upgradeRows(detail)
    expect(rows.length).toBe(6)
    const solar = rows.find((r) => r.type === 'rooftop_solar')
    expect(solar).toMatchObject({ on: true, verified: 'verified', name: expect.stringMatching(/^Rooftop solar · [\d,]+ kW$/) })
    expect(solar.cost).toMatch(/^\$[\d,]+$/); expect(solar.co2).toMatch(/tonnes$/)
    expect(vm.buildingTotals(detail).line).toMatch(/^[\d,]+ tCO₂ \/ year · \$[\d,]+k investment$/)
  })
  it('an unverified upgrade outside the plan can be included by the owner', () => {
    const issueRows = vm.upgradeRows(issue)
    const bad = issueRows.filter((r) => r.verified === 'unverified')
    expect(bad.length).toBeGreaterThan(0); expect(bad.every((r) => r.includable && !r.on)).toBe(true)
  })
  it('evidence items become sources with media urls and the verifier status first', () => {
    const e = vm.evidenceModel(issue, (id) => `/media/${id}`)
    expect(e.items.length).toBeGreaterThan(0)
    expect(e.items[0]).toMatchObject({ status: 'rejected', url: expect.stringMatching(/^\/media\//) })
    expect(e.items[0].notes[0]).toMatch(/spandrel/)
    expect(e.items.some((i) => i.provider === 'Matterport') || e.items.every((i) => i.provider === 'Vexcel')).toBe(true)
  })
  it('hero_3d mode survives in the showcase sample (frontend contract)', () => {
    const hero = vm.widget(showcase, 'hero_3d')
    expect(hero.mode).toBe('showcase'); expect(hero.showcase_url).toMatch(/^https:\/\/my\.matterport\.com\//); expect(hero.mesh_url).toBeNull()
    expect(vm.widget(detail, 'hero_3d').mode).toBe('mesh')
  })
})

describe('financing', () => {
  it('overview: proposed, with the plan id from the state', () => {
    const f = vm.financingModel(overview, { plan_id: 'plan_abc' })
    expect(f).toMatchObject({ planId: 'plan_abc', executed: false }); expect(f.total).toMatch(/^\$[\d,]+k$/)
  })
  it('approved: executed with the Nessie ids and one bill per contractor', () => {
    const f = vm.financingModel(approved, null)
    expect(f.executed).toBe(true); expect(f.nessieIds.account).toBeTruthy(); expect(f.nessieIds.transfer).toBeTruthy()
    expect(f.bills.length).toBeGreaterThan(0); expect(f.planId).toBeTruthy() // falls back to the financing_card's plan_id
    expect(vm.memoMarkdown(approved)).toMatch(/Retrofit plan memo/)
  })
})

describe('survey screens from the activity events', () => {
  const E = (seq, agent, building_id, kind, message = 'm') => ({ seq, agent, building_id, building_name: building_id && `B${building_id}`, kind, message, ts: `2026-11-14T09:41:${String(seq).padStart(2, '0')}.000Z` })
  const events = [E(0, 'Orchestrator', null, 'plan'), E(1, 'Records', '1', 'fetch'), E(2, 'Records', '2', 'fetch'), E(3, 'Aerial', '1', 'observe'),
    E(4, 'Verifier', '1', 'verify'), E(5, 'Interior', '1', 'observe')]
  it('progress counts distinct buildings per layer', () => {
    const p = vm.surveyProgress(events, 8)
    expect(p.map((x) => x.label)).toEqual(['Records', 'Aerial inspection', 'Interior inspection', 'Verification'])
    expect(p[0].detail).toBe('2 / 8 complete'); expect(p[1].detail).toBe('1 / 8 complete'); expect(p[2].done).toBe(true)
    expect(vm.surveyProgress([...events, E(6, 'Orchestrator', null, 'done')], 8)[3].done).toBe(true)
  })
  it('feed rows show the latest events with a clock time', () => {
    const rows = vm.feedRows(events, 3)
    expect(rows.map((r) => r.seq)).toEqual([3, 4, 5]); expect(rows[0].time).toBe('09:41:03'); expect(rows[0].meta).toBe('B1')
  })
  it('summary from the run state', () => {
    const s = vm.surveySummary({ results: { a: { status: 'done', upgrades: 3, interior: true, claims: { verified: 5, unverified: 1 } }, b: { status: 'done', upgrades: 2, claims: { rejected: 1 } }, c: { status: 'error' } } })
    expect(Object.fromEntries(s.map((x) => [x.label, x.value]))).toEqual({
      'Aerial coverage': '2 buildings', 'Interior coverage': '1 hero building', 'Feasible upgrades': '5 upgrades', 'Unverified claims': '2 excluded from plan' })
    expect(vm.surveySummary(null)).toBeNull()
  })
})
