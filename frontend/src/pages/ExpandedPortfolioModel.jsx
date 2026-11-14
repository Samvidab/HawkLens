import { useNavigate } from 'react-router-dom'
import portfolio3dLarge from '../assets/portfolio-3d-large.svg'
import Page from '../components/Page'

export default function ExpandedPortfolioModel() {
  const navigate = useNavigate()

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        Your portfolio · Schematic model
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1238px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to portfolio&nbsp;&nbsp;×
      </button>

      <section className="absolute left-[84px] top-[150px] w-[1272px] h-[630px] rounded-[12px] bg-model overflow-hidden">
        <p className="absolute left-[34.5px] top-[31.5px] font-medium text-ink text-[22.5px]">
          Your buildings
        </p>
        <p className="absolute left-[34.5px] top-[69px] text-muted text-[19.5px]">
          Select a building to see its opportunities.
        </p>
        <img
          src={portfolio3dLarge}
          alt="Schematic 3D portfolio with solar roof overlays"
          className="absolute left-[13.5px] top-[93px] w-[1240.8px] h-[465.3px]"
        />
        <div className="absolute left-[742.5px] top-[180px] w-[306px] h-[73.5px] rounded-[7.5px] bg-white overflow-hidden shadow-sm">
          <p className="absolute left-[18px] top-[12px] font-medium text-ink text-[19.5px]">
            Midtown office
          </p>
          <button
            type="button"
            onClick={() => navigate('/building')}
            className="absolute left-[18px] top-[43.5px] text-brand text-[16.5px] hover:underline"
          >
            View building&nbsp;&nbsp;→
          </button>
        </div>
        <p className="absolute left-[34.5px] top-[576px] text-muted text-[16.5px]">
          Solar shown on eligible roofs
        </p>
      </section>
    </Page>
  )
}
