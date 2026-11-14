import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'

const BUILDINGS = [
  { id: 'HOU–01', layers: 'Records + aerial' },
  { id: 'HOU–02', layers: 'Records + aerial' },
  { id: 'HOU–03', layers: 'Records + aerial' },
  { id: 'Midtown office · HOU–04', layers: 'Records + aerial + interior' },
  { id: 'HOU–05', layers: 'Records + aerial' },
  { id: 'HOU–06', layers: 'Records + aerial' },
  { id: 'HOU–07', layers: 'Records + aerial' },
  { id: 'HOU–08', layers: 'Records + aerial' },
]

const SETTINGS = [
  { label: 'City', value: 'Houston' },
  { label: 'Portfolio', value: '8 buildings' },
]

export default function StartSurvey() {
  const navigate = useNavigate()

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
        Houston portfolio · 8 sample buildings · Records, aerial imagery and one interior scan
      </p>

      {/* Buildings in this survey */}
      <section className="absolute left-[56px] top-[265px] w-[848px] h-[550px] overflow-hidden">
        <p className="absolute left-[20px] top-[17px] font-semibold text-ink text-[16px] leading-[1.45]">
          Buildings in this survey
        </p>
        {BUILDINGS.map((b, i) => {
          const divTop = 65 + i * 53
          const rowTop = 75 + i * 53
          return (
            <div key={b.id}>
              <div className="absolute left-[20px] w-[808px] h-px bg-line" style={{ top: `${divTop}px` }} />
              <p
                className="absolute left-[20px] font-medium text-ink text-[13px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                {b.id}
              </p>
              <p
                className="absolute left-[347px] text-muted text-[14px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                {b.layers}
              </p>
              <p
                className="absolute left-[748px] text-brand text-[11px] leading-[1.45]"
                style={{ top: `${rowTop}px` }}
              >
                Ready
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
        {SETTINGS.map((s, i) => (
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
          40%
        </p>
        <p className="absolute left-[24px] top-[205px] font-medium text-muted text-[13px] leading-[1.45]">
          Budget and risk
        </p>
        <p className="absolute left-[24px] top-[233px] text-muted text-[11px] leading-[1.45]">
          Budget $1500k · Balanced risk
        </p>
      </section>

      <button
        type="button"
        onClick={() => navigate('/survey-in-progress')}
        className="absolute left-[944px] top-[597px] w-[440px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition"
      >
        Start survey
      </button>
      <button
        type="button"
        onClick={() => navigate('/survey-complete')}
        className="absolute left-[944px] top-[660px] w-[440px] h-[46px] rounded-[6px] bg-model text-brand text-[13px] font-medium leading-[1.45] hover:brightness-95 transition"
      >
        Use cached demo survey
      </button>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px] leading-[1.45]">
        Prototype survey sequence · Example buildings and findings, not live data
      </p>
    </Page>
  )
}
