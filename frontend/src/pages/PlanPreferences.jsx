import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOverview } from '../lib/store'
import { RISK_LAMBDA, riskLabel, targetModel, usdK, widget } from '../lib/viewModels'

const RISKS = ['Cautious', 'Balanced', 'Growth']

export default function PlanPreferences() {
  const navigate = useNavigate()
  const run = useOverview()
  const tm = run.layout ? targetModel(run.layout) : null
  // With a real plan the budget choices scale with its cost (a fixed $1000k-$2000k would make any real portfolio infeasible).
  const total = tm ? (widget(run.layout, 'plan_table')?.totals?.upfront_usd ?? 0) : 0
  const options = tm && total > 0
    ? [{ label: 'No cap', usd: null }, { label: usdK(Math.round((total * 0.8) / 1e5) * 1e5), usd: Math.round((total * 0.8) / 1e5) * 1e5 }, { label: usdK(Math.round((total * 1.2) / 1e5) * 1e5), usd: Math.round((total * 1.2) / 1e5) * 1e5 }]
    : [{ label: 'No cap', usd: null }] // no priced plan yet: only 'no cap' (any other figure would be invented)
  const [budget, setBudget] = useState(tm && tm.budgetUsd != null ? usdK(tm.budgetUsd) : 'No cap')
  const [risk, setRisk] = useState(tm ? riskLabel(tm.riskLambda) : 'Balanced')
  useEffect(() => { // the plan loads asynchronously after a reload: show ITS budget and risk
    if (!tm) return
    setBudget(tm.budgetUsd == null ? 'No cap' : usdK(tm.budgetUsd))
    setRisk(riskLabel(tm.riskLambda))
  }, [tm?.budgetUsd, tm?.riskLambda]) // eslint-disable-line react-hooks/exhaustive-deps
  const pickBudget = (o) => { setBudget(o.label); run.setPrefs({ budget_usd: o.usd }); if (run.layout) run.act('set_budget', { budget_usd: o.usd }).catch(() => {}) }
  const riskOn = !tm || tm.riskSupported // no plan yet: local choice only; with a plan, only if the engine applies risk_lambda
  const pickRisk = (r) => {
    if (!riskOn) return
    setRisk(r)
    run.setPrefs({ risk_lambda: RISK_LAMBDA[r] })
    if (run.layout) run.act('set_risk', { risk_lambda: RISK_LAMBDA[r] }).catch(() => {})
  }

  const close = () => navigate(-1)

  return (
    <div className="min-h-full w-full flex justify-center py-10 px-4">
      {/* dimmed full-frame backdrop */}
      <div className="relative w-[1440px] h-[980px] shrink-0 bg-[rgba(34,42,49,0.35)]">
        {/* clicking the backdrop closes */}
        <button
          type="button"
          aria-label="Close"
          onClick={close}
          className="absolute inset-0 w-full h-full cursor-default"
        />

        <div className="absolute left-[420px] top-[258px] w-[600px] h-[464px] rounded-[10px] bg-white overflow-hidden">
          <p className="absolute left-[32px] top-[28px] font-semibold text-ink text-[24px]">
            Plan preferences
          </p>
          <p className="absolute left-[32px] top-[70px] text-muted text-[13px]">
            Budget {budget} · {risk} risk
          </p>
          <button
            type="button"
            onClick={close}
            className="absolute left-[519px] top-[33px] font-medium text-brand text-[14px] hover:underline"
          >
            Done
          </button>

          <p className="absolute left-[32px] top-[122px] font-medium text-ink text-[14px]">
            Investment ceiling
          </p>
          {options.map((o, i) => {
            const b = o.label
            const selected = b === budget
            return (
              <button
                key={b}
                type="button"
                onClick={() => pickBudget(o)}
                className={`absolute top-[155px] w-[168px] h-[46px] rounded-[6px] text-[14px] font-medium transition ${
                  selected ? 'bg-[#e7ece3] text-brand ring-2 ring-brand/50' : 'bg-[#e7ece3] text-brand hover:brightness-95'
                }`}
                style={{ left: `${32 + i * 184}px` }}
              >
                {b}
              </button>
            )
          })}

          <p className="absolute left-[32px] top-[236px] font-medium text-ink text-[14px]">
            Risk preference
          </p>
          <p className="absolute left-[32px] top-[330px] w-[536px] text-muted text-[12px] leading-[18px]">
            {riskOn
              ? 'Cautious favours plans with a better worst case; Growth maximises the expected return.'
              : 'Risk preference is not applied by the current pricing engine yet.'}
          </p>
          {RISKS.map((r, i) => {
            const selected = r === risk
            return (
              <button
                key={r}
                type="button"
                onClick={() => pickRisk(r)}
                disabled={!riskOn}
                aria-pressed={selected}
                className={`absolute top-[269px] w-[168px] h-[46px] rounded-[6px] text-[14px] font-medium transition ${
                  !riskOn ? 'bg-[#eef0ec] text-[#a3aaa0] cursor-not-allowed' : selected ? 'bg-[#e7ece3] text-brand ring-2 ring-brand/50' : 'bg-[#e7ece3] text-brand hover:brightness-95'
                }`}
                style={{ left: `${32 + i * 184}px` }}
              >
                {r}
              </button>
            )
          })}

          <p className="absolute left-[32px] top-[355px] text-muted text-[13px] leading-[23px]">
            {tm
              ? 'Changes re-plan your portfolio and reset any prior approval.'
              : 'The plan is not available yet.'}
            <br />
            {tm ? 'The plan is re-priced each time you choose.' : ''}
          </p>

          <button
            type="button"
            onClick={close}
            className="absolute left-[32px] top-[400px] w-[536px] h-[46px] rounded-[6px] bg-brand text-white text-[14px] font-medium hover:brightness-110 active:brightness-95 transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
