import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './lib/ui'
import { RunProvider } from './lib/store'
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
import { RequireRun } from './components/Truth'

// Strict demo mode (always on): a page that needs a run shows "no survey data yet" instead of prototype content.
const gate = (el, need = 'layout', active = 'portfolio') => <RequireRun need={need} active={active}>{el}</RequireRun>

/** Every screen. Exported so tests can render any route inside their own router and run provider. */
export function AppRoutes() {
  return (
        <Routes>
          <Route path="/" element={gate(<Portfolio />)} />
          <Route path="/plan" element={gate(<PlanDetails />, 'layout', 'plan')} />
          <Route path="/building" element={gate(<BuildingDetails />)} />
          <Route path="/start-survey" element={gate(<StartSurvey />, 'portfolio')} />
          <Route path="/survey-in-progress" element={gate(<SurveyInProgress />, 'run')} />
          <Route path="/survey-complete" element={gate(<SurveyComplete />, 'run')} />
          <Route path="/financing-approval" element={gate(<FinancingApproval />, 'layout', 'plan')} />
          <Route path="/funding-confirmation" element={gate(<FundingConfirmation />, 'layout', 'plan')} />
          <Route path="/documents" element={gate(<Documents />, 'layout', 'documents')} />
          <Route path="/survey-evidence" element={gate(<SurveyEvidence />)} />
          <Route path="/investment-memo" element={gate(<InvestmentMemo />, 'layout', 'documents')} />
          <Route path="/risk-and-target" element={gate(<RiskAndTarget />, 'layout', 'plan')} />
          <Route path="/plan-preferences" element={gate(<PlanPreferences />, 'layout', 'plan')} />
          <Route path="/demo-document-notice" element={<DemoDocumentNotice />} />
          <Route path="/assumptions" element={gate(<Assumptions />, 'layout', 'plan')} />
          <Route path="/funding-account" element={gate(<FundingAccount />, 'layout', 'plan')} />
          <Route path="/building-insights" element={gate(<BuildingInsights />)} />
          <Route path="/building-excluded" element={gate(<BuildingExcluded />)} />
          <Route path="/expanded-portfolio-model" element={gate(<ExpandedPortfolioModel />)} />
          <Route path="/expanded-building-model" element={gate(<ExpandedBuildingModel />)} />
          <Route path="/expanded-survey-image" element={gate(<ExpandedSurveyImage />)} />
          <Route path="*" element={<Placeholder title="Not found" />} />
        </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <RunProvider demoRunId={import.meta.env.VITE_DEMO_RUN_ID}>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </RunProvider>
    </BrowserRouter>
  )
}
