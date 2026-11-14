import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './lib/ui'
import Portfolio from './pages/Portfolio'
import PlanDetails from './pages/PlanDetails'
import BuildingDetails from './pages/BuildingDetails'
import Placeholder from './pages/Placeholder'

// Screens not yet built — each routes to a titled placeholder so the whole
// prototype stays navigable. These get replaced screen by screen.
const PENDING = [
  { path: '/survey-evidence', title: 'Survey evidence', active: 'plan' },
  { path: '/financing-approval', title: 'Financing approval', active: 'plan' },
  { path: '/documents', title: 'Documents', active: 'documents' },
  { path: '/funding-confirmation', title: 'Funding confirmation', active: 'plan' },
  { path: '/plan-preferences', title: 'Plan preferences', active: 'plan' },
  { path: '/demo-document-notice', title: 'Demo document notice', active: 'documents' },
  { path: '/expanded-survey-image', title: 'Expanded survey image', active: 'plan' },
  { path: '/expanded-portfolio-model', title: 'Expanded portfolio model', active: 'portfolio' },
  { path: '/investment-memo', title: 'Investment memo', active: 'plan' },
  { path: '/assumptions', title: 'Assumptions and sources', active: 'plan' },
  { path: '/funding-account', title: 'Funding account details', active: 'plan' },
  { path: '/expanded-building-model', title: 'Expanded building model', active: 'portfolio' },
  { path: '/risk-and-target', title: 'Risk and target', active: 'plan' },
  { path: '/building-insights', title: 'Building insights', active: 'portfolio' },
  { path: '/start-survey', title: 'Start survey', active: 'portfolio' },
  { path: '/survey-in-progress', title: 'Survey in progress', active: 'portfolio' },
  { path: '/survey-complete', title: 'Survey complete', active: 'portfolio' },
  { path: '/building-excluded', title: 'Building excluded', active: 'portfolio' },
]

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Portfolio />} />
          <Route path="/plan" element={<PlanDetails />} />
          <Route path="/building" element={<BuildingDetails />} />
          {PENDING.map((p) => (
            <Route
              key={p.path}
              path={p.path}
              element={<Placeholder title={p.title} active={p.active} />}
            />
          ))}
          <Route path="*" element={<Placeholder title="Not found" />} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}
