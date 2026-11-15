import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { useBuildingFocus } from '../lib/store'
import { buildingModel } from '../lib/viewModels'
import { BuildingPicture } from './BuildingDetails'

// Strict: the Matterport tour or the recorded footprint, large; never a schematic drawing.
export default function ExpandedBuildingModel() {
  const navigate = useNavigate()
  const run = useBuildingFocus()
  const bm = buildingModel(run.layout)

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        {bm?.name || 'Building'}
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1238px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to building&nbsp;&nbsp;×
      </button>

      <section className="absolute left-[84px] top-[120px] w-[1272px] h-[780px] rounded-[12px] bg-model overflow-hidden">
        <BuildingPicture layout={run.layout} height={640} />
      </section>
    </Page>
  )
}
