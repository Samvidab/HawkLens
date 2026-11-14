import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import buildingModel from '../assets/building-model.svg'
import Page from '../components/Page'
import { useBuildingFocus } from '../lib/store'
import { buildingModel as selectBuilding, buildingTotals, upgradeRows } from '../lib/viewModels'
import { useGo } from '../lib/ui'

const PROFILE = [
  ['Floor area', '96,000 sq ft'],
  ['Year built', '1992'],
  ['Floors', '6'],
  ['Annual emissions', '420 tCO₂'],
  ['Annual energy spend', '$168,000'],
]

const UPGRADES = [
  { key: 'led', name: 'LED retrofit', co2: '24 tonnes', cost: '$18,000', npv: '+$26,000' },
  { key: 'solar', name: 'Rooftop solar · 120 kW', co2: '96 tonnes', cost: '$152,000', npv: '+$52,000' },
  { key: 'hvac', name: 'Heat pump conversion', co2: '90 tonnes', cost: '$100,000', npv: '+$14,000' },
]

export default function BuildingDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const [included, setIncluded] = useState({ led: true, solar: true, hvac: true })
  const run = useBuildingFocus()
  const bm = run.layout && run.layout.situation === 'building_detail' ? selectBuilding(run.layout) : null
  const live = bm ? upgradeRows(run.layout) : null
  const profile = bm ? bm.profile : PROFILE
  const ups = live || UPGRADES
  const rowH = ups.length > 3 ? 27 : 42
  const solar = live?.find((u) => u.type === 'rooftop_solar') || live?.[0]
  const flip = async (u) => {
    if (!live) return toggle(u.key)
    const verb = !u.on && u.includable ? ['include_unverified', { upgrade_id: u.id }] : ['toggle_upgrade', { upgrade_id: u.id, on: !u.on }]
    await run.act(...verb).catch(() => {})
  }
  const exclude = async () => {
    if (live) await run.act('exclude_building', { building_id: bm.id }).catch(() => {})
    navigate('/building-excluded', { state: bm ? { id: bm.id, name: bm.name } : null })
  }

  const toggle = (key) => setIncluded((s) => ({ ...s, [key]: !s[key] }))

  return (
    <Page active="portfolio">
      {/* Header */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;Houston portfolio
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        {bm ? bm.name : 'Midtown office'}
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        {bm ? `${bm.address} · ${bm.type}` : 'Houston, TX · Commercial office · HOU–04'}
      </p>
      <p className="absolute left-[1200px] top-[158px] font-medium text-brand text-[14px]">
        Adjust upgrades below
      </p>

      {/* Building model card */}
      <section className="absolute left-[56px] top-[262px] w-[848px] h-[375px] rounded-[8px] bg-model overflow-hidden">
        <p className="absolute left-[22px] top-[20px] font-medium text-ink text-[14px] z-10">
          Building model
        </p>
        <p className="absolute left-[670px] top-[22px] text-muted text-[12px] z-10">Roof&nbsp;&nbsp;/&nbsp;&nbsp;Interior</p>
        <img src={buildingModel} alt="" className="absolute inset-0 w-full h-full" />
        <div className="absolute left-[555px] top-[98px] w-[231px] h-[58px] rounded-[6px] bg-white overflow-hidden shadow-sm">
          <p className="absolute left-[13px] top-[11px] font-medium text-brand text-[14px]">
            {solar ? solar.name : '120 kW rooftop solar'}
          </p>
          <button
            type="button"
            onClick={() => go('/survey-evidence')}
            className="absolute left-[13px] top-[34px] text-brand text-[11px] hover:underline"
          >
            View supporting evidence&nbsp;&nbsp;→
          </button>
        </div>
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
        {profile.map(([label, value], i) => {
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
          All three data layers available
        </p>
        <p className="absolute left-[32px] top-[308px] text-muted text-[12px]">
          Records, aerial imagery and interior scans.
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
        onClick={exclude}
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
          {live ? buildingTotals(run.layout).line : '210 tCO₂ / year · $270k investment'}
        </p>
        <p className="absolute left-[1061px] top-[12px] text-muted text-[12px]">
          Changes update your portfolio plan.
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

        {ups.map((u, i) => {
          const top = 105 + i * rowH
          const on = live ? u.on : included[u.key]
          return (
            <div key={u.key}>
              <div
                className="absolute left-0 w-[1328px] h-px bg-line"
                style={{ top: `${top - 8}px` }}
              />
              <p className="absolute left-0 font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>
                {u.name}{live && u.verified !== 'verified' ? ` · ${u.verified}` : ''}
              </p>
              <p className="absolute left-[563px] text-ink text-[14px]" style={{ top: `${top}px` }}>
                {u.co2}
              </p>
              <p className="absolute left-[756px] text-ink text-[14px]" style={{ top: `${top}px` }}>
                {u.cost}
              </p>
              <p className="absolute left-[963px] text-brand text-[14px]" style={{ top: `${top}px` }}>
                {u.npv}
              </p>
              <button
                type="button"
                role="switch"
                aria-checked={on}
                aria-label={`Include ${u.name}`}
                onClick={() => flip(u)}
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
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        {live ? 'Live survey data · Changes update your portfolio plan' : 'Illustrative data · Not a live building survey'}
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
