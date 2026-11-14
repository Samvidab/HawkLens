import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useGo } from '../lib/ui'

const TABS = [
  { label: 'Interior', left: 56, width: 52, active: true },
  { label: 'Exterior', left: 184 },
  { label: 'Roof & solar', left: 312 },
]

export default function BuildingInsights() {
  const navigate = useNavigate()
  const go = useGo()

  return (
    <Page active="portfolio">
      <button
        type="button"
        onClick={() => navigate('/building')}
        className="absolute left-[56px] top-[110px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
      >
        ←&nbsp;&nbsp;Midtown office
      </button>
      <h1 className="absolute left-[56px] top-[148px] font-semibold text-ink text-[32px] leading-[1.45]">
        Building insights
      </h1>
      <p className="absolute left-[56px] top-[201px] text-muted text-[14px] leading-[1.45]">
        The rooms, facades and roof behind the recommendations.
      </p>

      {/* Tabs */}
      {TABS.map((t) => (
        <button
          key={t.label}
          type="button"
          className={`absolute top-[242px] text-[13px] font-medium leading-[1.45] ${
            t.active ? 'text-ink' : 'text-muted hover:text-ink'
          }`}
          style={{ left: `${t.left}px` }}
        >
          {t.label}
        </button>
      ))}
      <div className="absolute left-[56px] top-[274px] w-[52px] h-[2px] bg-brand" />

      {/* Interior panel */}
      <div className="absolute left-[56px] top-[306px] w-[1328px] h-[435px] overflow-hidden">
        {/* Floor plan card */}
        <section className="absolute left-0 top-0 w-[848px] h-[420px] rounded-[8px] border border-line bg-white overflow-hidden">
          <p className="absolute left-[19px] top-[16px] font-semibold text-ink text-[16px] leading-[1.45]">
            Inside Midtown office
          </p>
          <p className="absolute left-[19px] top-[46px] text-muted text-[11px] leading-[1.45]">
            Level 2 · 16,000 sq ft · Illustrative room boundaries
          </p>

          {/* Open office room (highlighted) */}
          <div className="absolute left-[39px] top-[95px] w-[403.2px] h-[226px] bg-model border-2 border-brand overflow-hidden">
            <p className="absolute left-[10px] top-[16px] font-medium text-ink text-[13px] leading-[1.45]">
              Open office
            </p>
            <p className="absolute left-[10px] top-[46px] text-muted text-[11px] leading-[1.45]">
              8,400
              <br />
              sq ft
            </p>
            <div className="absolute left-[18px] top-[127px] w-[172px] h-[40px] rounded-[5px] bg-white flex items-center">
              <span className="ml-[12px] text-brand text-[11px]">01&nbsp;&nbsp;Fluorescent fixtures</span>
            </div>
          </div>
          {/* Meeting room */}
          <div className="absolute left-[442.2px] top-[95px] w-[124.8px] h-[226px] bg-[#f4f0e5] border-[3px] border-white overflow-hidden">
            <p className="absolute left-[9px] top-[15px] font-medium text-ink text-[13px] leading-[1.45]">Meeting</p>
            <p className="absolute left-[9px] top-[45px] text-muted text-[11px] leading-[1.45]">
              2,600
              <br />
              sq ft
            </p>
          </div>
          {/* Support room */}
          <div className="absolute left-[567px] top-[95px] w-[86.4px] h-[226px] bg-[#f5f7f2] border-[3px] border-white overflow-hidden">
            <p className="absolute left-[9px] top-[15px] font-medium text-ink text-[13px] leading-[1.45]">Support</p>
            <p className="absolute left-[9px] top-[45px] text-muted text-[11px] leading-[1.45]">
              1,800
              <br />
              sq ft
            </p>
          </div>
          {/* Circulation room */}
          <div className="absolute left-[653.4px] top-[95px] w-[153.6px] h-[226px] bg-line border-[3px] border-white overflow-hidden">
            <p className="absolute left-[9px] top-[15px] font-medium text-ink text-[13px] leading-[1.45]">
              Circulation
            </p>
            <p className="absolute left-[9px] top-[45px] text-muted text-[11px] leading-[1.45]">
              3,200
              <br />
              sq ft
            </p>
          </div>

          <p className="absolute left-[39px] top-[342px] font-medium text-brand text-[13px] leading-[1.45]">
            01&nbsp;&nbsp;&nbsp;Lighting finding · LED retrofit included in the sample plan
          </p>
          <button
            type="button"
            onClick={() => go('/survey-evidence')}
            className="absolute left-[39px] top-[382px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
          >
            Open panorama evidence&nbsp;&nbsp;→
          </button>
        </section>

        {/* Right info panel */}
        <p className="absolute left-[888px] top-[10px] font-semibold text-ink text-[20px] leading-[1.45]">
          What the interior tells us
        </p>
        <p className="absolute left-[888px] top-[57px] text-muted text-[14px] leading-[1.45]">
          Room boundaries size the envelope and
          <br />
          help locate findings in the scan.
        </p>
        <p className="absolute left-[888px] top-[139px] font-medium text-muted text-[13px] leading-[1.45]">
          Level 2 area
        </p>
        <p className="absolute left-[888px] top-[167px] font-semibold text-ink text-[30px] leading-[1.45]">
          16,000 sq ft
        </p>
        <p className="absolute left-[888px] top-[233px] font-medium text-muted text-[13px] leading-[1.45]">
          Whole-building floor area
        </p>
        <p className="absolute left-[888px] top-[261px] text-ink text-[14px] leading-[1.45]">
          96,000 sq ft · 6 levels
        </p>
        <p className="absolute left-[888px] top-[350px] text-muted text-[11px] leading-[1.45]">
          Illustrative plan, not a Matterport export.
        </p>
      </div>

      <button
        type="button"
        onClick={() => go('/survey-evidence')}
        className="absolute left-[56px] top-[799px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
      >
        Open all survey evidence&nbsp;&nbsp;→
      </button>
      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Illustrative imagery and measurements · Replace with verified survey payloads
      </p>
    </Page>
  )
}
