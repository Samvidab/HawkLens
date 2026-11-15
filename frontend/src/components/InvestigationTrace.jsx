// The investigator's recorded steps for a building, as a numbered list: the feed line each step showed, the facts it
// quoted (with their source) and the images it returned. Only the investigation_trace widget's props
// (GET /investigation_trace/{id}); no trace -> "not available", never a filled-in list.
import { useEffect, useState } from 'react'
import { getInvestigationTrace, mediaUrl } from '../lib/api'

export default function InvestigationTrace({ buildingId }) {
  const [trace, setTrace] = useState(undefined) // undefined loading, null not available
  useEffect(() => {
    let alive = true
    setTrace(undefined)
    getInvestigationTrace(buildingId).then((t) => alive && setTrace(t)).catch(() => alive && setTrace(null))
    return () => { alive = false }
  }, [buildingId])

  const steps = trace?.steps || []
  return (
    <section data-testid="investigation-trace" className="space-y-3">
      <div>
        <p className="font-semibold text-ink text-[20px]">How the investigator surveyed this building</p>
        <p className="text-muted text-[13px]">Each step the agent chose, as recorded during the survey, with the images it pulled.</p>
      </div>
      {trace === undefined && <p className="text-muted text-[13px]">Loading…</p>}
      {trace === null && <p className="text-muted text-[13px]" data-testid="trace-na">Investigation steps not available for this building.</p>}
      {steps.length > 0 && (
        <ol className="space-y-3">
          {steps.map((s, i) => (
            <li key={i} data-trace-step={i + 1} className="flex gap-3 border-t border-line pt-3">
              <span className="w-[24px] shrink-0 text-right font-semibold text-brand text-[14px] tabular-nums">{i + 1}.</span>
              <div className="flex-1 min-w-0">
                <p className="text-ink text-[14px]">{s.feed_line}</p>
                <p className="text-muted text-[11px]">
                  tool: {s.tool}
                  {s.facts_quoted?.length > 0 && <> · quoted: {s.facts_quoted.map((f) => `“${f.text}” (${f.source})`).join(', ')}</>}
                </p>
              </div>
              {s.image_ids?.length > 0 && (
                <div className="flex gap-2 shrink-0">
                  {s.image_ids.map((id) => (
                    <a key={id} href={mediaUrl(id)} target="_blank" rel="noreferrer" title={id}>
                      <img src={mediaUrl(id)} alt={`Image from step ${i + 1}`} loading="lazy" className="h-[64px] w-[96px] object-cover rounded border border-line" data-trace-image={id} />
                    </a>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
