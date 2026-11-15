import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import { Sources } from '../components/Truth'
import { RENDERERS } from '../components/widgets'
import { useBuildingFocus } from '../lib/store'
import { buildingModel, widget } from '../lib/viewModels'
import { useGo } from '../lib/ui'

// Strict: the building's real floor plan (Matterport rooms) and facade readings from the layout, or "not available".
export default function BuildingInsights() {
  const navigate = useNavigate()
  const go = useGo()
  const run = useBuildingFocus()
  const bm = buildingModel(run.layout)
  const floor = widget(run.layout, 'floor_plan')
  const facades = widget(run.layout, 'facade_compass')
  const Floor = RENDERERS.floor_plan
  const Facades = RENDERERS.facade_compass

  return (
    <Page active="portfolio" fluid>
      <button
        type="button"
        onClick={() => navigate('/building')}
        className="absolute left-[56px] top-[110px] font-medium text-brand text-[13px] leading-[1.45] hover:underline"
      >
        ←&nbsp;&nbsp;{bm?.name || 'Building'}
      </button>
      <h1 className="absolute left-[56px] top-[148px] font-semibold text-ink text-[32px] leading-[1.45]">
        Building insights
      </h1>
      <p className="absolute left-[56px] top-[201px] text-muted text-[14px] leading-[1.45]">
        The rooms and facades recorded by the survey.
      </p>

      <div className="pt-[260px] px-[56px] pb-[120px] grid grid-cols-12 gap-6">
        <section className="col-span-7 rounded-[8px] border border-line bg-white p-5">
          <p className="font-semibold text-ink text-[16px] mb-1">Floor plan</p>
          <p className="text-muted text-[11px] mb-3">Rooms from the Matterport scan</p>
          {floor ? <Floor p={floor} /> : <p className="text-muted text-[13px]">Floor plan not available for this building (no interior scan).</p>}
        </section>
        <section className="col-span-5 rounded-[8px] border border-line bg-white p-5">
          <p className="font-semibold text-ink text-[16px] mb-1">Facades</p>
          <p className="text-muted text-[11px] mb-3">Glazing by side, from the aerial imagery</p>
          {facades ? <Facades p={facades} /> : <p className="text-muted text-[13px]">Facade data not available for this building.</p>}
        </section>
        <div className="col-span-12">
          <button type="button" onClick={() => go('/survey-evidence')} className="font-medium text-brand text-[13px] hover:underline">
            Open all survey evidence&nbsp;&nbsp;→
          </button>
        </div>
      </div>
      <Sources className="absolute left-[56px] bottom-[24px]" />
    </Page>
  )
}
