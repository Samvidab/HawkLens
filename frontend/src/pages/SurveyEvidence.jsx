import { useNavigate } from 'react-router-dom'
import roof from '../assets/evidence-roof.png'
import facade from '../assets/evidence-facade.png'
import interior from '../assets/evidence-interior.png'
import Page from '../components/Page'
import { useGo } from '../lib/ui'

const DETAILS = [
  ['Usable roof area', '1,200 m²'],
  ['Proposed solar size', '120 kW'],
  ['Annual CO₂ avoided', '96 tonnes'],
]

const SOURCES = [
  { img: roof, title: 'Roof · aerial', kind: 'Solar feasibility', provider: 'Vexcel source preview', left: 0 },
  { img: facade, title: 'South facade', kind: 'Windows & glazing', provider: 'Vexcel source preview', left: 450 },
  { img: interior, title: 'Interior · level 2', kind: 'Lighting & HVAC', provider: 'Matterport source preview', left: 900 },
]

export default function SurveyEvidence() {
  const navigate = useNavigate()
  const go = useGo()

  return (
    <Page active="portfolio">
      {/* Header */}
      <button
        type="button"
        onClick={() => navigate('/building')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;Midtown office
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        See what the survey found
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        Midtown office · Survey evidence
      </p>
      <button
        type="button"
        onClick={() => go('/demo-document-notice')}
        className="absolute left-[1197px] top-[157px] font-medium text-brand text-[13px] hover:underline"
      >
        Download survey&nbsp;&nbsp;↓
      </button>

      {/* Evidence viewer */}
      <section className="absolute left-[56px] top-[262px] w-[848px] h-[435px] rounded-[8px] overflow-hidden">
        <img src={roof} alt="Illustrative overhead roof image" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute left-[16px] top-[16px] w-[254px] h-[30px] rounded-[4px] bg-white flex items-center">
          <span className="ml-[11px] font-medium text-ink text-[12px]">Illustrative survey imagery</span>
        </div>
        <div className="absolute left-[313px] top-[200px] w-[176px] h-[34px] rounded-[5px] bg-white flex items-center">
          <span className="ml-[12px] font-medium text-brand text-[12px]">1,200 m² usable roof</span>
        </div>
        <button
          type="button"
          onClick={() => go('/expanded-survey-image')}
          className="absolute left-[723px] top-[382px] w-[109px] h-[36px] rounded-[5px] bg-white text-left"
        >
          <span className="ml-[15px] text-muted text-[12px]">Enlarge ↗</span>
        </button>
      </section>

      {/* Finding details */}
      <section className="absolute left-[944px] top-[262px] w-[440px] h-[435px] overflow-hidden">
        <div className="absolute left-0 top-0 w-px h-[435px] bg-line" />
        <p className="absolute left-[32px] top-[6px] font-semibold text-ink text-[21px]">
          Roof suitable for solar
        </p>
        <p className="absolute left-[32px] top-[43px] font-medium text-brand text-[13px]">
          Verified finding · 91% confidence
        </p>
        <p className="absolute left-[32px] top-[83px] text-muted text-[14px] leading-[23px]">
          A clear central roof area can support solar.
          <br />
          Equipment and edge setbacks are excluded.
        </p>
        {DETAILS.map(([label, value], i) => {
          const top = 157 + i * 42
          return (
            <div key={label}>
              <p className="absolute left-[32px] text-muted text-[13px]" style={{ top: `${top}px` }}>
                {label}
              </p>
              <p className="absolute left-[292px] font-medium text-ink text-[14px]" style={{ top: `${top}px` }}>
                {value}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[32px] top-[290px] w-[376px] h-px bg-line" />
        <p className="absolute left-[32px] top-[312px] font-medium text-ink text-[14px]">
          Needs a site check
        </p>
        <p className="absolute left-[32px] top-[338px] text-muted text-[13px] leading-[21px]">
          Roof loading and electrical connection still
          <br />
          need an on-site assessment before installation.
        </p>
        <p className="absolute left-[32px] top-[406px] font-medium text-brand text-[13px]">
          Included in your plan
        </p>
      </section>

      {/* Survey sources */}
      <section className="absolute left-[56px] top-[744px] w-[1328px] h-[165px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[18px]">Survey sources</p>
        {SOURCES.map((s) => (
          <div key={s.title}>
            <button
              type="button"
              onClick={() => go('/expanded-survey-image')}
              className="absolute top-[42px] w-[168px] h-[106px] rounded-[6px] overflow-hidden"
              style={{ left: `${s.left}px` }}
            >
              <img src={s.img} alt={s.title} className="w-full h-full object-cover" />
            </button>
            <button
              type="button"
              onClick={() => go('/expanded-survey-image')}
              className="absolute font-medium text-ink text-[14px] hover:text-brand"
              style={{ left: `${s.left + 184}px`, top: '49px' }}
            >
              {s.title}
            </button>
            <p className="absolute text-muted text-[12px]" style={{ left: `${s.left + 184}px`, top: '78px' }}>
              {s.kind}
            </p>
            <p className="absolute text-muted text-[11px]" style={{ left: `${s.left + 184}px`, top: '103px' }}>
              {s.provider}
            </p>
            <button
              type="button"
              onClick={() => go('/expanded-survey-image')}
              className="absolute text-brand text-[12px] hover:underline"
              style={{ left: `${s.left + 184}px`, top: '130px' }}
            >
              Open&nbsp;&nbsp;→
            </button>
          </div>
        ))}
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        Illustrative data and images · Not CoStar, Vexcel or Matterport survey results
      </p>
    </Page>
  )
}
