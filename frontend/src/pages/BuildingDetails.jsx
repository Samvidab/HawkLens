import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { Estimate, NA, Sources, Stub, useStub } from '../components/Truth'
import { FootprintMap, hasFootprints } from '../components/widgets'
import { useBuildingFocus } from '../lib/store'
import { buildingModel as selectBuilding, buildingTotals, upgradeRows, widget } from '../lib/viewModels'
import { useGo } from '../lib/ui'

/** The building view's picture: the Matterport tour when the layout has one, else the recorded footprint, else nothing. */
export function BuildingPicture({ layout, height }) {
  const hero = widget(layout, 'hero_3d')
  const profile = widget(layout, 'building_header')?.profile
  if (hero?.mode === 'showcase' && hero.showcase_url) {
    return <iframe title="Matterport 3D tour" src={hero.showcase_url} className="w-full h-full" allow="fullscreen; xr-spatial-tracking" />
  }
  if (profile && hasFootprints([profile])) {
    return (
      <div className="px-[22px] pt-[56px]">
        <FootprintMap buildings={[profile]} focusId={profile.building_id} height={height} />
        <p className="mt-2 text-muted text-[11px]">
          Footprint from the building records, drawn in 2D
          {profile.footprint_source === 'estimated' && <Estimate title="Footprint estimated from floor area and floors">estimated footprint</Estimate>}
        </p>
      </div>
    )
  }
  return <p className="px-[22px] pt-[60px] text-muted text-[13px]">No 3D tour or footprint is available for this building.</p>
}

// Strict: the focused building's real profile, baseline (labelled an estimate) and upgrades; nothing else.
export default function BuildingDetails() {
  const go = useGo()
  const navigate = useNavigate()
  const run = useBuildingFocus()
  const stub = useStub().engine
  const bm = run.layout?.situation === 'building_detail' ? selectBuilding(run.layout) : null
  const ups = (bm && upgradeRows(run.layout)) || []
  const rowH = ups.length > 3 ? 27 : 42
  const solar = ups.find((u) => u.type === 'rooftop_solar') || ups[0]
  const gallery = widget(run.layout, 'evidence_gallery')?.items || []
  const layers = bm ? [
    'Records',
    gallery.some((i) => i.source !== 'matterport_pano') && 'aerial imagery',
    bm.hasMatterport && 'interior scan',
  ].filter(Boolean) : []
  const estimate = bm?.baselineBasis && /estimate/i.test(bm.baselineBasis)
  const city = run.portfolio?.city

  const flip = async (u) => {
    const verb = !u.on && u.includable ? ['include_unverified', { upgrade_id: u.id }] : ['toggle_upgrade', { upgrade_id: u.id, on: !u.on }]
    await run.act(...verb).catch(() => {})
  }
  const exclude = async () => {
    await run.act('exclude_building', { building_id: bm.id }).catch(() => {})
    navigate('/building-excluded', { state: { id: bm.id, name: bm.name } })
  }

  if (!bm) {
    return (
      <Page active="portfolio">
        <p className="absolute left-[56px] top-[150px] text-muted text-[14px]">{run.busy ? 'Opening the building…' : 'Building details not available.'}</p>
      </Page>
    )
  }

  return (
    <Page active="portfolio">
      {/* Header */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;{city ? `${city} portfolio` : 'Portfolio'}
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        {bm.name}
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        {bm.address || `Address ${NA}`} · {bm.type || `type ${NA}`}
      </p>
      <p className="absolute left-[1200px] top-[158px] font-medium text-brand text-[14px]">
        Adjust upgrades below
      </p>

      {/* Building picture card */}
      <section className="absolute left-[56px] top-[262px] w-[848px] h-[375px] rounded-[8px] bg-model overflow-hidden">
        <p className="absolute left-[22px] top-[20px] font-medium text-ink text-[14px] z-10">
          Building model
        </p>
        <div className="absolute inset-0"><BuildingPicture layout={run.layout} height={250} /></div>
        {solar && (
          <div className="absolute left-[555px] top-[98px] w-[260px] h-[58px] rounded-[6px] bg-white overflow-hidden shadow-sm">
            <p className="absolute left-[13px] top-[11px] w-[240px] truncate font-medium text-brand text-[14px]">
              {solar.name}
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
        {bm.profile.map(([label, value, kind], i) => {
          const top = 55 + i * 38
          return (
            <div key={label}>
              <p className="absolute left-[32px] text-muted text-[13px]" style={{ top: `${top}px` }}>
                {label}
              </p>
              <p className={`absolute left-[224px] text-[14px] ${value === NA ? 'text-muted' : 'font-medium text-ink'}`} style={{ top: `${top}px` }}>
                {value}
                {kind === 'baseline' && value !== NA && estimate && <Estimate title="Benchmark estimate (energy use per sq ft for the building type), not metered">estimate</Estimate>}
                {kind === 'baseline' && value !== NA && stub && <Stub />}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[32px] top-[258px] w-[376px] h-px bg-line" />
        <p className="absolute left-[32px] top-[281px] font-medium text-brand text-[14px]">
          Data available: {layers.join(', ')}
        </p>
        <p className="absolute left-[32px] top-[308px] text-muted text-[12px]">
          {bm.hasMatterport ? 'Includes a Matterport interior scan.' : 'No interior scan for this building.'}
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
        onClick={() => go('/building-insights')}
        className="absolute left-[1153px] top-[650px] font-medium text-brand text-[13px] hover:underline"
      >
        Floor plan &amp; facades&nbsp;&nbsp;→
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
          {buildingTotals(run.layout).line}{stub && <Stub />}
        </p>
        <p className="absolute left-[1061px] top-[12px] text-muted text-[12px]">
          Changes update your portfolio plan.
        </p>

        {['Upgrade', 'CO₂ avoided / year', 'Upfront cost', 'Lifetime net value', 'Include'].map((h, i) => (
          <p key={h} className="absolute top-[77px] text-muted text-[11px]" style={{ left: `${[0, 563, 756, 963, 1262][i]}px` }}>
            {h}
          </p>
        ))}
        {!ups.length && <p className="absolute left-0 top-[105px] text-muted text-[13px]">No feasible upgrades found for this building.</p>}

        {ups.map((u, i) => {
          const top = 105 + i * rowH
          return (
            <div key={u.key}>
              <div className="absolute left-0 w-[1328px] h-px bg-line" style={{ top: `${top - 8}px` }} />
              <p className="absolute left-0 font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>
                {u.name}
                {u.verified === 'assumed' ? <Estimate>assumed</Estimate> : u.verified !== 'verified' ? ` · ${u.verified}` : ''}
              </p>
              <p className="absolute left-[563px] text-ink text-[14px]" style={{ top: `${top}px` }}>
                {u.co2}{stub && u.co2 !== NA && <Stub />}
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
                aria-checked={u.on}
                aria-label={`Include ${u.name}`}
                onClick={() => flip(u)}
                className={`absolute left-[1271px] w-[38px] h-[22px] rounded-full transition-colors ${u.on ? 'bg-brand' : 'bg-[#c7ccd1]'}`}
                style={{ top: `${top - 2}px` }}
              >
                <span className={`block w-[16px] h-[16px] rounded-full bg-white shadow transition-transform ${u.on ? 'translate-x-[19px]' : 'translate-x-[3px]'}`} />
              </button>
            </div>
          )
        })}
      </section>

      <Sources />
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
