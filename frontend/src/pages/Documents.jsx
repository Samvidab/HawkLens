import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'

const FILTERS = [
  { label: 'All documents', left: 0, width: 95 },
  { label: 'Plan', left: 148 },
  { label: 'Survey', left: 243 },
  { label: 'Financial', left: 338 },
]

const DOCS = [
  { title: 'Investment memo', meta: 'PDF · Houston portfolio · Draft', updated: 'Today, 09:42', highlight: true },
  { title: 'Portfolio survey', meta: 'PDF · 8 buildings · 3 data layers', updated: 'Today, 09:39' },
  { title: 'Assumptions & sources', meta: 'CSV · Input ranges and source references', updated: 'Today, 09:38' },
  { title: 'Upgrade schedule', meta: '18 upgrades across 8 buildings', updated: 'Today, 09:42' },
  { title: 'Reserve confirmation', meta: 'Available after you approve the plan', updated: 'Not yet available', disabled: true },
]

const PREVIEW_METRICS = [
  ['Upfront investment', '$1280k'],
  ['Expected lifetime net value', '+$486k'],
  ['Baseline simulation confidence', '87%'],
]

export default function Documents() {
  const navigate = useNavigate()

  return (
    <Page active="documents">
      {/* Header */}
      <div className="absolute left-[56px] top-[127px] w-[1328px] h-[105px] overflow-hidden">
        <h1 className="absolute left-0 top-0 font-semibold text-ink text-[32px]">Documents</h1>
        <p className="absolute left-0 top-[49px] text-muted text-[14px]">
          The plan, the evidence, and the assumptions behind it.
        </p>
        <button
          type="button"
          onClick={() => navigate('/demo-document-notice')}
          className="absolute left-[1160px] top-[3px] w-[168px] h-[44px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
        >
          Download all&nbsp;&nbsp;↓
        </button>
      </div>

      {/* Document list */}
      <section className="absolute left-[56px] top-[265px] w-[768px] h-[625px] overflow-hidden">
        {FILTERS.map((f, i) => (
          <button
            key={f.label}
            type="button"
            className={`absolute top-0 text-[13px] ${
              i === 0 ? 'font-medium text-ink' : 'text-muted hover:text-ink'
            }`}
            style={{ left: `${f.left}px` }}
          >
            {f.label}
          </button>
        ))}
        <div className="absolute left-0 top-[30px] w-[95px] h-[2px] bg-brand" />

        <p className="absolute left-[20px] top-[66px] text-muted text-[11px]">Document</p>
        <p className="absolute left-[508px] top-[66px] text-muted text-[11px]">Updated</p>

        <div className="absolute left-0 top-[93px] w-[768px] flex flex-col gap-[8px]">
          {DOCS.map((d) => (
            <button
              key={d.title}
              type="button"
              disabled={d.disabled}
              onClick={() => navigate('/demo-document-notice')}
              className={`relative block w-[768px] h-[83px] rounded-[6px] text-left overflow-hidden ${
                d.highlight ? 'bg-[#edf3e6]' : 'hover:bg-[#f6f7f3]'
              } ${d.disabled ? 'cursor-not-allowed' : ''}`}
            >
              <span
                className={`absolute left-[20px] top-[16px] text-[15px] ${
                  d.disabled ? 'text-muted' : 'font-medium text-ink'
                }`}
              >
                {d.title}
              </span>
              <span className="absolute left-[20px] top-[46px] text-muted text-[12px]">{d.meta}</span>
              <span className="absolute left-[508px] top-[28px] text-muted text-[12px]">{d.updated}</span>
              <span className="absolute left-[724px] top-[25px] text-brand text-[20px]">›</span>
            </button>
          ))}
        </div>

        <p className="absolute left-[20px] top-[588px] text-muted text-[12px]">
          Documents update when your plan changes.
        </p>
      </section>

      {/* Document preview */}
      <section className="absolute left-[880px] top-[265px] w-[504px] h-[625px] rounded-[7px] border border-line bg-white overflow-hidden">
        <div className="absolute left-0 top-0 w-full h-[47px] bg-[#f5f7f2]">
          <p className="absolute left-[25px] top-[17px] font-medium text-muted text-[10px] tracking-[1px]">
            DOCUMENT PREVIEW
          </p>
          <p className="absolute left-[437px] top-[17px] text-muted text-[10px]">1 page</p>
        </div>
        <p className="absolute left-[29px] top-[77px] font-semibold text-brand text-[13px]">Hawk Lens</p>
        <p className="absolute left-[29px] top-[111px] font-semibold text-ink text-[27px]">
          Investment memo
        </p>
        <p className="absolute left-[29px] top-[152px] text-muted text-[12px]">
          Houston portfolio · Draft for owner review
        </p>
        <div className="absolute left-[29px] top-[185px] w-[444px] h-px bg-line" />
        <p className="absolute left-[29px] top-[211px] font-semibold text-ink text-[16px]">
          Recommendation
        </p>
        <p className="absolute left-[29px] top-[243px] w-[444px] text-muted text-[13px] leading-[23px]">
          Fund 18 upgrades across 8 buildings.
          <br />
          Expected annual cut: 1032 tonnes CO₂.
        </p>
        {PREVIEW_METRICS.map(([label, value], i) => {
          const top = 314 + i * 38
          return (
            <div key={label}>
              <p className="absolute left-[29px] text-muted text-[12px]" style={{ top: `${top}px` }}>
                {label}
              </p>
              <p
                className="absolute left-[374px] font-medium text-ink text-[15px]"
                style={{ top: `${top - 1}px` }}
              >
                {value}
              </p>
            </div>
          )
        })}
        <div className="absolute left-[29px] top-[434px] w-[444px] h-px bg-line" />
        <p className="absolute left-[29px] top-[457px] font-medium text-ink text-[14px]">
          Before you commit
        </p>
        <p className="absolute left-[29px] top-[486px] text-muted text-[12px] leading-[21px]">
          The worst 5% of scenarios average −$94k NPV.
          <br />
          Site checks and contractor quotes are still required.
          <br />
          Savings interactions are not yet modeled.
        </p>
        <button
          type="button"
          onClick={() => navigate('/demo-document-notice')}
          className="absolute left-[29px] top-[583px] font-medium text-brand text-[13px] hover:underline"
        >
          Download memo&nbsp;&nbsp;↓
        </button>
        <p className="absolute left-[349px] top-[585px] text-muted text-[11px]">Draft · Not approved</p>
      </section>

      <p className="absolute left-[56px] top-[947px] text-muted text-[11px]">
        Illustrative documents · Figures match the sample portfolio plan
      </p>
    </Page>
  )
}
