import { Link, useNavigate } from 'react-router-dom'
import logo from '../assets/logo.png'
import { useRun } from '../lib/store'

// Shared top navigation bar. `active` is one of: 'portfolio' | 'plan' | 'documents'.
const TABS = [
  { key: 'portfolio', label: 'Portfolio', to: '/', left: 283, width: 58 },
  { key: 'plan', label: 'Plan', to: '/plan', left: 389, width: 29 },
  { key: 'workspace', label: 'Workspace', to: '/workspace', left: 495, width: 74 },
  { key: 'documents', label: 'Documents', to: '/documents', left: 617, width: 76 },
]

export default function Navigation({ active = 'portfolio' }) {
  const navigate = useNavigate()
  const { portfolio } = useRun()
  const current = TABS.find((t) => t.key === active) ?? TABS[0]

  return (
    <nav className="absolute left-0 top-0 w-[1440px] h-[81px] overflow-hidden bg-white">
      <button
        type="button"
        onClick={() => navigate('/')}
        aria-label="Back to portfolio dashboard"
        title="Back to dashboard"
        className="absolute left-[56px] top-[16px] w-[72px] h-[48px] rounded hover:opacity-80 transition-opacity"
      >
        <img src={logo} alt="Hawk Lens" className="w-full h-full object-contain pointer-events-none" />
      </button>

      {TABS.map((tab) => {
        const isActive = tab.key === active
        return (
          <Link
            key={tab.key}
            to={tab.to}
            className={`absolute top-[33px] whitespace-nowrap text-[14px] transition-colors ${
              isActive ? 'font-medium text-ink' : 'text-muted hover:text-ink'
            }`}
            style={{ left: `${tab.left}px` }}
          >
            {tab.label}
          </Link>
        )
      })}

      <div
        className="absolute top-[78px] h-[2px] bg-ink transition-all duration-200"
        style={{ left: `${current.left}px`, width: `${current.width}px` }}
      />

      {portfolio?.city && ( // the real portfolio's city; no invented owner name
        <span className="absolute left-[1160px] top-[33px] whitespace-nowrap text-muted text-[13px]">
          {portfolio.city} portfolio
        </span>
      )}
      <div className="absolute left-0 top-[80px] w-[1440px] h-px bg-line" />
    </nav>
  )
}
