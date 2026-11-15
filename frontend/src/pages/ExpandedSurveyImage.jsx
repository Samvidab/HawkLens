import { useLocation, useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import RecordedImage from '../components/RecordedImage'
import { useBuildingFocus } from '../lib/store'
import { mediaUrl } from '../lib/api'
import { buildingModel, evidenceModel } from '../lib/viewModels'
import { mainEvidence } from './SurveyEvidence'

// Strict: the survey's own image (served by /media) with the verifier's boxes, or nothing.
export default function ExpandedSurveyImage() {
  const navigate = useNavigate()
  const run = useBuildingFocus()
  const bm = buildingModel(run.layout)
  const location = useLocation()
  const items = evidenceModel(run.layout, mediaUrl)?.items || []
  const main = items.find(i => i.id === location.state?.imageId) || mainEvidence(items)

  return (
    <Page nav={false}>
      <p className="absolute left-[56px] top-[49px] font-medium text-ink text-[18px]">
        {bm?.name || 'Building'}{main ? ` · ${main.provider} · ${main.title}` : ''}
      </p>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="absolute left-[1245px] top-[52px] font-medium text-brand text-[14px] hover:underline"
      >
        Back to evidence&nbsp;&nbsp;×
      </button>

      <div className="absolute left-[56px] top-[115px] w-[1328px] h-[787px] overflow-hidden bg-model">
        {main ? (
          <>
            <RecordedImage image={main} />
          </>
        ) : <p className="p-6 text-muted text-[14px]">No survey image for this building.</p>}
      </div>
    </Page>
  )
}
