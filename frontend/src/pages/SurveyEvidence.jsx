import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { Sources } from '../components/Truth'
import { useBuildingFocus } from '../lib/store'
import { mediaUrl } from '../lib/api'
import { buildingModel, evidenceModel, upgradeLabel, upgradeRows } from '../lib/viewModels'
import { useGo } from '../lib/ui'

/** The image the evidence screens lead with: a marked aerial image if there is one, else the first. */
export function mainEvidence(items) {
  return items.length ? items.find((i) => i.source !== 'matterport_pano' && i.marks?.length) || items[0] : null
}

// Strict: only the survey's own images (served by /media), the verifier's boxes and the recorded claims.
export default function SurveyEvidence() {
  const navigate = useNavigate()
  const go = useGo()
  const run = useBuildingFocus()
  const items = evidenceModel(run.layout, mediaUrl)?.items || []
  const bm = buildingModel(run.layout)
  const main = mainEvidence(items)
  const details = main ? main.summaries.slice(0, 3).map((s) => { const [k, ...v] = String(s).split(': '); return [k, v.join(': ')] }) : []
  // which in-plan upgrades this image supports (upgrade.evidence_ids)
  const supports = main ? (upgradeRows(run.layout) || []).filter((u) => u.evidenceIds.includes(main.id)) : []
  const inPlan = supports.filter((u) => u.on)
  const sources = items.slice(0, 3).map((i, n) => ({
    key: i.id, img: i.url, title: i.title, left: n * 450, provider: i.provider,
    kind: `${i.status} · ${i.summaries.length} finding${i.summaries.length === 1 ? '' : 's'}`,
  }))
  const name = bm?.name || 'Building'

  return (
    <Page active="portfolio">
      <button
        type="button"
        onClick={() => navigate('/building')}
        className="absolute left-[56px] top-[110px] text-brand text-[13px] hover:underline"
      >
        ←&nbsp;&nbsp;{name}
      </button>
      <h1 className="absolute left-[56px] top-[142px] font-semibold text-ink text-[32px]">
        See what the survey found
      </h1>
      <p className="absolute left-[56px] top-[191px] text-muted text-[14px]">
        {name} · Survey evidence · {items.length} image{items.length === 1 ? '' : 's'}
      </p>

      {/* Evidence viewer */}
      <section className="absolute left-[56px] top-[262px] w-[848px] h-[435px] rounded-[8px] overflow-hidden bg-model">
        {!main && <p className="absolute left-[24px] top-[24px] text-muted text-[14px]">No survey images for this building.</p>}
        {main && (
          <>
            <img src={main.url} alt={main.title} className="absolute inset-0 w-full h-full object-cover" />
            {main.marks.filter((m) => m.image_id === main.id && m.bbox).map((m, i) => (
              <div key={i} className="absolute border-2 border-white rounded-[3px] shadow" title={m.label}
                style={{ left: `${m.bbox[0] * 100}%`, top: `${m.bbox[1] * 100}%`, width: `${(m.bbox[2] - m.bbox[0]) * 100}%`, height: `${(m.bbox[3] - m.bbox[1]) * 100}%` }} />
            ))}
            <div className="absolute left-[16px] top-[16px] h-[30px] px-[11px] rounded-[4px] bg-white flex items-center">
              <span className="font-medium text-ink text-[12px]">{main.provider} · {main.title}</span>
            </div>
            <button
              type="button"
              onClick={() => go('/expanded-survey-image')}
              className="absolute left-[723px] top-[382px] w-[109px] h-[36px] rounded-[5px] bg-white text-left"
            >
              <span className="ml-[15px] text-muted text-[12px]">Enlarge ↗</span>
            </button>
          </>
        )}
      </section>

      {/* Finding details */}
      <section className="absolute left-[944px] top-[262px] w-[440px] h-[435px] overflow-hidden">
        <div className="absolute left-0 top-0 w-px h-[435px] bg-line" />
        {main ? (
          <>
            <p className="absolute left-[32px] top-[6px] font-semibold text-ink text-[21px]">{main.title}</p>
            <p className="absolute left-[32px] top-[43px] font-medium text-brand text-[13px]">
              {main.status === 'verified' ? 'Verified finding' : `Finding ${main.status}`}
            </p>
            {details.length === 0 && <p className="absolute left-[32px] top-[83px] text-muted text-[13px]">No claims recorded for this image.</p>}
            {details.map(([label, value], i) => {
              const top = 83 + i * 42
              return (
                <div key={`${label}${i}`}>
                  <p className="absolute left-[32px] w-[250px] truncate text-muted text-[13px]" style={{ top: `${top}px` }} title={label}>{label}</p>
                  <p className="absolute left-[292px] w-[140px] truncate font-medium text-ink text-[14px]" style={{ top: `${top}px` }} title={value}>{value}</p>
                </div>
              )
            })}
            <div className="absolute left-[32px] top-[220px] w-[376px] h-px bg-line" />
            <p className="absolute left-[32px] top-[240px] font-medium text-ink text-[14px]">Verifier notes</p>
            <p className="absolute left-[32px] top-[266px] w-[376px] text-muted text-[13px] leading-[21px] line-clamp-4">
              {main.notes?.length ? main.notes.join(' ') : 'No verifier notes recorded.'}
            </p>
            <p className="absolute left-[32px] top-[380px] w-[376px] font-medium text-brand text-[13px]">
              {inPlan.length
                ? `Supports ${inPlan.map((u) => upgradeLabel(u.type)).join(', ')} in your plan`
                : supports.length ? 'Supports upgrades that are not in your plan' : 'Not linked to an upgrade'}
            </p>
          </>
        ) : <p className="absolute left-[32px] top-[6px] text-muted text-[14px]">Findings not available.</p>}
      </section>

      {/* Survey sources */}
      <section className="absolute left-[56px] top-[744px] w-[1328px] h-[165px] overflow-hidden">
        <p className="absolute left-0 top-0 font-semibold text-ink text-[18px]">Survey sources</p>
        {!sources.length && <p className="absolute left-0 top-[42px] text-muted text-[13px]">No images.</p>}
        {sources.map((s) => (
          <div key={s.key}>
            <button
              type="button"
              onClick={() => go('/expanded-survey-image')}
              className="absolute top-[42px] w-[168px] h-[106px] rounded-[6px] overflow-hidden bg-model"
              style={{ left: `${s.left}px` }}
            >
              <img src={s.img} alt={s.title} className="w-full h-full object-cover" />
            </button>
            <p className="absolute font-medium text-ink text-[14px]" style={{ left: `${s.left + 184}px`, top: '49px' }}>{s.title}</p>
            <p className="absolute text-muted text-[12px]" style={{ left: `${s.left + 184}px`, top: '78px' }}>{s.kind}</p>
            <p className="absolute text-muted text-[11px]" style={{ left: `${s.left + 184}px`, top: '103px' }}>{s.provider}</p>
          </div>
        ))}
      </section>

      <Sources />
    </Page>
  )
}
