import { useNavigate } from 'react-router-dom'

export default function BuildingExcluded() {
  const navigate = useNavigate()

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
            Midtown office excluded
          </p>
          <p className="absolute left-[28px] top-[81px] text-muted text-[14px] leading-[1.45]">
            All three upgrades for this building are off.
            <br />
            The portfolio baseline still includes its emissions;
            <br />
            only its retrofit options are excluded.
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
            onClick={() => navigate('/building')}
            className="absolute left-[28px] top-[281px] w-[504px] h-[46px] rounded-[6px] bg-model text-brand text-[13px] font-medium leading-[1.45] hover:brightness-95 transition"
          >
            Include building again
          </button>
        </div>
      </div>
    </div>
  )
}
