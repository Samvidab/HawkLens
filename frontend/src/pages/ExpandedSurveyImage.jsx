import { useNavigate } from 'react-router-dom'
import roofLarge from '../assets/evidence-roof-large.png'
import Page from '../components/Page'

export default function ExpandedSurveyImage() {
  const navigate = useNavigate()

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        Midtown office · Illustrative survey imagery
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1245px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to evidence&nbsp;&nbsp;×
      </button>

      <div className="absolute left-[56px] top-[115px] w-[1328px] h-[787px] overflow-hidden">
        <img src={roofLarge} alt="Expanded roof survey image" className="w-full h-full object-cover" />
      </div>
    </Page>
  )
}
