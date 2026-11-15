import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { FootprintMap, hasFootprints } from '../components/widgets'
import { useOverview } from '../lib/store'
import { widget } from '../lib/viewModels'

// Strict: the real footprints, large; clicking one opens that building.
export default function ExpandedPortfolioModel() {
  const navigate = useNavigate()
  const run = useOverview()
  const p = widget(run.layout, 'portfolio_3d')
  const open = async (b) => {
    await run.act('open_building', { building_id: b.building_id }).catch(() => {})
    navigate('/building')
  }

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        Your portfolio · building footprints
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1238px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to portfolio&nbsp;&nbsp;×
      </button>

      <section className="absolute left-[84px] top-[120px] w-[1272px] h-[780px] rounded-[12px] bg-model overflow-hidden p-[30px]">
        <p className="font-medium text-ink text-[20px]">Your buildings</p>
        <p className="text-muted text-[15px] mb-4">Click a footprint to open its building. Footprints from the building records, drawn in 2D.</p>
        {hasFootprints(p?.buildings)
          ? <FootprintMap buildings={p.buildings} focusId={p.focus_building_id} onPick={open} height={620} />
          : <p className="text-muted text-[14px]">Building footprints not available.</p>}
      </section>
    </Page>
  )
}
