import { useLocation, useNavigate } from 'react-router-dom'
import { useRun } from '../lib/store'

export default function BuildingExcluded() {
  const navigate = useNavigate()
  const run = useRun()
  const selected = useLocation().state
  const excluded = run.state?.plan?.excluded_building_ids || []
  const id = selected?.id || (excluded.length === 1 ? excluded[0] : null)
  const b = id ? { id, name: selected?.name || run.portfolio?.buildings?.find((b) => b.building_id === id)?.name } : null
  const confirmed = !!b && excluded.includes(b.id)
  const again = async () => {
    try {
      if (run.layout && b?.id) {
        await run.act('include_building', { building_id: b.id })
        await run.act('open_building', { building_id: b.id })
      }
      navigate('/building')
    } catch {}

  }

  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      <div className="relative w-[1440px] h-[980px] shrink-0 bg-[rgba(0,0,0,0.35)]">
        <button
          type="button"
          aria-label="Close"
          onClick={() => navigate('/building')}
          className="absolute inset-0 w-full h-full cursor-default"
        />

        <div className="absolute left-[440px] top-[300px] w-[560px] h-[380px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[28px] top-[28px] font-semibold text-ink text-[20px] leading-[1.45]">
            {confirmed && b?.name ? `${b.name} excluded` : 'Exclusion status unavailable'}
          </p>
          <p className="absolute left-[28px] top-[81px] text-muted text-[14px] leading-[1.45]">
            {confirmed ? <>All upgrades for this building are off.<br />The portfolio baseline still includes its emissions;<br />only its retrofit options are excluded.</> : 'Open a building and exclude it to view its recorded exclusion status.'}
          </p>
          <button
            type="button"
            onClick={() => navigate('/plan')}
            className="absolute left-[28px] top-[218px] w-[504px] h-[46px] rounded-[6px] bg-brand text-white text-[13px] font-medium leading-[1.45] hover:brightness-110 active:brightness-95 transition"
          >
            View updated plan
          </button>
          <button
            type="button"
            onClick={again}
            disabled={!confirmed}
            className="absolute left-[28px] top-[281px] w-[504px] h-[46px] rounded-[6px] bg-model text-brand text-[13px] font-medium leading-[1.45] hover:brightness-95 transition disabled:opacity-50"
          >
            Include building again
          </button>
        </div>
      </div>
    </div>
  )
}
