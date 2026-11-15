import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import buildingModel from '../assets/building-model.svg'
import Page from '../components/Page'
import { useGo } from '../lib/ui'
import { fetchPortfolio } from '../lib/api'
import { usePlan } from '../lib/plan'
import { DASH, signedUsd, tonnes, typeLabel, usd } from '../lib/format'

const num = (v, unit = '') => (typeof v === 'number' ? `${Math.round(v).toLocaleString('en-US')}${unit}` : DASH)

export default function BuildingDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { plan, busy, actionError, act } = usePlan()
  const [portfolio, setPortfolio] = useState([])

  useEffect(() => {
    let alive = true
    fetchPortfolio()
      .then((d) => alive && setPortfolio(d.buildings || []))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  // ?id=<building_id>; default: the first building with upgrades in the plan, else the first in the portfolio.
  const bid =
    params.get('id') ||
    plan?.line_items?.[0]?.building_id ||
    plan?.coverage?.requested?.[0] ||
    portfolio[0]?.building_id
  const b = portfolio.find((x) => x.building_id === bid) || {}
  const base = plan?.baseline?.[bid] || {}
  const ups = plan?.upgrades_by_building?.[bid] || []
  const tot = plan?.building_totals?.[bid]
  const solar = ups.find((u) => u.type === 'rooftop_solar' && u.in_plan)
  const PROFILE = [
    ['Floor area', num(b.rba_sqft, ' sq ft')],
    ['Year built', b.year_built ? String(b.year_built) : DASH],
    ['Floors', b.stories ? String(b.stories) : DASH],
    ['Annual emissions', tonnes(base.tonnes_per_year, ' tCO₂')],
    ['Annual energy spend', usd(base.annual_spend_usd)],
  ]
  const toggle = (u) => act('toggle_upgrade', { upgrade_id: u.upgrade_id, on: u.excluded })

  return (
    <Page active="portfolio">
      {/* Header */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;{b.city || 'Houston'} portfolio
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        {b.name || plan?.building_names?.[bid] || bid || DASH}
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        {[b.address, b.property_type, bid].filter(Boolean).join(' · ') || DASH}
      </p>
      <p className="absolute left-[1200px] top-[158px] font-medium text-brand text-[14px]">
        {busy ? 'Re-planning…' : 'Adjust upgrades below'}
      </p>

      {/* Building model card */}
      <section className="absolute left-[56px] top-[262px] w-[848px] h-[375px] rounded-[8px] bg-model overflow-hidden">
        <p className="absolute left-[22px] top-[20px] font-medium text-ink text-[14px] z-10">
          Building model
        </p>
        <p className="absolute left-[670px] top-[22px] text-muted text-[12px] z-10">Roof&nbsp;&nbsp;/&nbsp;&nbsp;Interior</p>
        <img src={buildingModel} alt="" className="absolute inset-0 w-full h-full" />
        {solar && (
        <div className="absolute left-[555px] top-[98px] w-[231px] h-[58px] rounded-[6px] bg-white overflow-hidden shadow-sm">
          <p className="absolute left-[13px] top-[11px] font-medium text-brand text-[14px]">
            {num(solar.size_value, ` ${solar.size_unit}`)} rooftop solar
          </p>
          <button
            type="button"
            onClick={() => go('/survey-evidence')}
            className="absolute left-[13px] top-[34px] text-brand text-[11px] hover:underline"
          >
            View supporting evidence&nbsp;&nbsp;→
          </button>
        </div>
        )}
        <p className="absolute left-[22px] top-[346px] text-muted text-[11px]">
          Proposed upgrades · Schematic view
        </p>
        <button
          type="button"
          onClick={() => go('/expanded-building-model')}
          className="absolute left-[736px] top-[339px] text-muted text-[12px] hover:text-ink"
        >
          Expand ↗
        </button>
      </section>

      {/* Property profile */}
      <section className="absolute left-[944px] top-[262px] w-[440px] h-[375px] overflow-hidden">
        <div className="absolute left-0 top-0 w-px h-[375px] bg-line" />
        <p className="absolute left-[32px] top-[8px] font-semibold text-ink text-[18px]">
          About this building
        </p>
        {PROFILE.map(([label, value], i) => {
          const top = 55 + i * 38
          return (
            <div key={label}>
              <p className="absolute left-[32px] text-muted text-[13px]" style={{ top: `${top}px` }}>
                {label}
              </p>
              <p
                className="absolute left-[264px] font-medium text-ink text-[14px]"
                style={{ top: `${top}px` }}
              >
                {value}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[32px] top-[258px] w-[376px] h-px bg-line" />
        <p className="absolute left-[32px] top-[281px] font-medium text-brand text-[14px]">
          {b.hero ? 'All three data layers available' : 'Records and aerial imagery'}
        </p>
        <p className="absolute left-[32px] top-[308px] text-muted text-[12px]">
          {plan?.coverage?.surveyed?.includes(bid) ? 'Surveyed in the current plan.' : 'Not surveyed yet.'}
        </p>
        <button
          type="button"
          onClick={() => go('/survey-evidence')}
          className="absolute left-[32px] top-[345px] font-medium text-brand text-[13px] hover:underline"
        >
          Open survey evidence&nbsp;&nbsp;→
        </button>
      </section>

      <button
        type="button"
        onClick={() => go('/expanded-building-model')}
        className="absolute left-[1153px] top-[650px] font-medium text-brand text-[13px] hover:underline"
      >
        Floor plan, facades &amp; sizing&nbsp;&nbsp;→
      </button>
      <button
        type="button"
        onClick={() => go('/building-excluded')}
        className="absolute left-[1222px] top-[183px] w-[162px] h-[36px] rounded-[5px] bg-[#f5f7f2] text-[13px] font-medium text-[#9a493c] hover:brightness-95"
      >
        Exclude building
      </button>

      {/* Building upgrades table with real include toggles */}
      <section className="absolute left-[56px] top-[682px] w-[1328px] h-[225px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[20px]">
          Upgrades for this building
        </p>
        <p className="absolute left-0 top-[34px] text-muted text-[13px]">
          {tot ? `${tonnes(tot.tonnes_per_year, ' tCO₂ / year')} · ${usd(tot.upfront_usd)} investment` : 'No upgrades selected here in the current plan'}
        </p>
        <p className="absolute left-[1061px] top-[12px] text-muted text-[12px]">
          {actionError ? <span className="text-[#b4532f]">{actionError}</span> : 'Changes re-run the portfolio optimizer.'}
        </p>

        {['Upgrade', 'CO₂ avoided / year', 'Upfront cost', 'Lifetime net value', 'Include'].map(
          (h, i) => (
            <p
              key={h}
              className="absolute top-[77px] text-muted text-[11px]"
              style={{ left: `${[0, 563, 756, 963, 1262][i]}px` }}
            >
              {h}
            </p>
          ),
        )}

        {ups.length === 0 && (
          <p className="absolute left-0 top-[105px] text-muted text-[14px]">No feasible upgrades recorded for this building.</p>
        )}
        <div className="absolute left-0 top-[97px] w-[1328px] h-[128px] overflow-y-auto">
        {ups.map((u, i) => {
          const top = 8 + i * 42
          const on = !u.excluded
          return (
            <div key={u.upgrade_id}>
              <div
                className="absolute left-0 w-[1328px] h-px bg-line"
                style={{ top: `${top - 8}px` }}
              />
              <p className="absolute left-0 font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>
                {typeLabel(u.type)}
                {u.type === 'rooftop_solar' ? ` · ${num(u.size_value, ` ${u.size_unit}`)}` : ''}
                <span className="text-muted font-normal text-[12px]">
                  {u.in_plan ? ' · in plan' : u.excluded ? ' · switched off' : ' · not selected'}
                  {u.verified === 'unverified' ? ' · unverified' : ''}
                </span>
              </p>
              <p className="absolute left-[563px] text-ink text-[14px]" style={{ top: `${top}px` }}>
                {tonnes(u.tonnes_per_year, ' tonnes')}
              </p>
              <p className="absolute left-[756px] text-ink text-[14px]" style={{ top: `${top}px` }}>
                {usd(u.upfront_usd)}
              </p>
              <p className="absolute left-[963px] text-brand text-[14px]" style={{ top: `${top}px` }}>
                {signedUsd(u.exp_npv)}
              </p>
              <button
                type="button"
                role="switch"
                aria-checked={on}
                aria-label={`Include ${typeLabel(u.type)}`}
                disabled={busy}
                onClick={() => toggle(u)}
                className={`absolute left-[1271px] w-[38px] h-[22px] rounded-full transition-colors ${
                  on ? 'bg-brand' : 'bg-[#c7ccd1]'
                }`}
                style={{ top: `${top - 2}px` }}
              >
                <span
                  className={`block w-[16px] h-[16px] rounded-full bg-white shadow transition-transform ${
                    on ? 'translate-x-[19px]' : 'translate-x-[3px]'
                  }`}
                />
              </button>
            </div>
          )
        })}
        <div style={{ height: `${8 + ups.length * 42}px` }} />
        </div>
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        {plan ? `Quant engine · Plan ${plan.plan_id}` : 'No plan yet'}
      </p>
      <button
        type="button"
        onClick={() => go('/plan')}
        className="absolute left-[1235px] top-[947px] text-brand text-[12px] hover:underline"
      >
        View portfolio plan&nbsp;&nbsp;→
      </button>
    </Page>
  )
}
