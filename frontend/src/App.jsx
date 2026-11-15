import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './lib/ui'
import { PlanProvider } from './lib/plan'
import Portfolio from './pages/Portfolio'
import PlanDetails from './pages/PlanDetails'
import BuildingDetails from './pages/BuildingDetails'
import StartSurvey from './pages/StartSurvey'
import SurveyInProgress from './pages/SurveyInProgress'
import SurveyComplete from './pages/SurveyComplete'
import FinancingApproval from './pages/FinancingApproval'
import FundingConfirmation from './pages/FundingConfirmation'
import Documents from './pages/Documents'
import SurveyEvidence from './pages/SurveyEvidence'
import InvestmentMemo from './pages/InvestmentMemo'
import RiskAndTarget from './pages/RiskAndTarget'
import PlanPreferences from './pages/PlanPreferences'
import DemoDocumentNotice from './pages/DemoDocumentNotice'
import Assumptions from './pages/Assumptions'
import FundingAccount from './pages/FundingAccount'
import BuildingInsights from './pages/BuildingInsights'
import BuildingExcluded from './pages/BuildingExcluded'
import ExpandedPortfolioModel from './pages/ExpandedPortfolioModel'
import ExpandedBuildingModel from './pages/ExpandedBuildingModel'
import ExpandedSurveyImage from './pages/ExpandedSurveyImage'
import Placeholder from './pages/Placeholder'
import MissionControl from './components/MissionControl'


export default function App() {
  return (
    <BrowserRouter>
      <PlanProvider>
      <ToastProvider>
        <MissionControl />
        
        <Routes>
          <Route path="/" element={<Portfolio />} />
          <Route path="/plan" element={<PlanDetails />} />
          <Route path="/building" element={<BuildingDetails />} />
          <Route path="/start-survey" element={<StartSurvey />} />
          <Route path="/survey-in-progress" element={<SurveyInProgress />} />
          <Route path="/survey-complete" element={<SurveyComplete />} />
          <Route path="/financing-approval" element={<FinancingApproval />} />
          <Route path="/funding-confirmation" element={<FundingConfirmation />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/survey-evidence" element={<SurveyEvidence />} />
          <Route path="/investment-memo" element={<InvestmentMemo />} />
          <Route path="/risk-and-target" element={<RiskAndTarget />} />
          <Route path="/plan-preferences" element={<PlanPreferences />} />
          <Route path="/demo-document-notice" element={<DemoDocumentNotice />} />
          <Route path="/assumptions" element={<Assumptions />} />
          <Route path="/funding-account" element={<FundingAccount />} />
          <Route path="/building-insights" element={<BuildingInsights />} />
          <Route path="/building-excluded" element={<BuildingExcluded />} />
          <Route path="/expanded-portfolio-model" element={<ExpandedPortfolioModel />} />
          <Route path="/expanded-building-model" element={<ExpandedBuildingModel />} />
          <Route path="/expanded-survey-image" element={<ExpandedSurveyImage />} />
          <Route path="*" element={<Placeholder title="Not found" />} />
        </Routes>
      </ToastProvider>
      </PlanProvider>
    </BrowserRouter>
  )
}
