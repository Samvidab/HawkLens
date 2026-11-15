import { useNavigate } from 'react-router-dom'
import Page from '../components/Page'
import LiveMemo from '../components/LiveMemo'

export default function InvestmentMemo() {
  const navigate = useNavigate()
  return <Page nav={false}>
    <button onClick={() => navigate('/documents')} className="absolute left-[1207px] top-[52px] font-medium text-brand text-[14px] hover:underline">Back to documents ×</button>
    <LiveMemo expanded />
  </Page>
}
