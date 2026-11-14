import { useNavigate } from 'react-router-dom'
import buildingModelLarge from '../assets/building-model-large.svg'
import Page from '../components/Page'
import { useGo } from '../lib/ui'

export default function ExpandedBuildingModel() {
  const navigate = useNavigate()
  const go = useGo()

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        Midtown office · Proposed rooftop solar
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1238px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to building&nbsp;&nbsp;×
      </button>

      <section className="absolute left-[84px] top-[170px] w-[1272px] h-[562.5px] rounded-[12px] bg-model overflow-hidden">
        <p className="absolute left-[33px] top-[30px] font-medium text-ink text-[21px] z-10">
          Building model
        </p>
        <img
          src={buildingModelLarge}
          alt="Schematic six-storey building and proposed rooftop solar"
          className="absolute inset-0 w-full h-full"
        />
        <div className="absolute left-[832.5px] top-[147px] w-[346.5px] h-[87px] rounded-[9px] bg-white overflow-hidden shadow-sm">
          <p className="absolute left-[19.5px] top-[16.5px] font-medium text-brand text-[21px]">
            120 kW rooftop solar
          </p>
          <button
            type="button"
            onClick={() => go('/survey-evidence')}
            className="absolute left-[19.5px] top-[51px] text-brand text-[16.5px] hover:underline"
          >
            View supporting evidence&nbsp;&nbsp;→
          </button>
        </div>
        <p className="absolute left-[33px] top-[519px] text-muted text-[16.5px]">
          Proposed upgrades · Schematic view
        </p>
      </section>
    </Page>
  )
}
