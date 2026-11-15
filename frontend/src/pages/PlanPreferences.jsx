import { useNavigate } from 'react-router-dom'
import { usePlan } from '../lib/plan'
import { RISK_PRESETS, budgetLabel, riskLabel } from '../lib/format'

// Investment ceilings the owner can pick (inputs to the optimizer, not results). null = no limit.
const BUDGETS = [1_000_000, 2_000_000, null]
const budgetText = (b) => (b === null ? 'No limit' : `$${(b / 1e6).toFixed(1)}M`)

export default function PlanPreferences() {
  const navigate = useNavigate()
  const { plan, goal, busy, actionError, requestBudget, requestRisk } = usePlan()
  const budget = goal.budget_usd ?? null
  const risk = goal.risk_lambda

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
            {budgetLabel(budget)} · {riskLabel(risk)} risk{busy ? ' · re-planning…' : ''}
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
          {BUDGETS.map((b, i) => {
            const selected = b === budget
            return (
              <button
                key={String(b)}
                type="button"
                disabled={busy}
                onClick={() => !selected && requestBudget(b)}
                className={`absolute top-[155px] w-[168px] h-[46px] rounded-[6px] text-[14px] font-medium transition ${
                  selected ? 'bg-[#e7ece3] text-brand ring-2 ring-brand/50' : 'bg-[#e7ece3] text-brand hover:brightness-95'
                }`}
                style={{ left: `${32 + i * 184}px` }}
              >
                {budgetText(b)}
              </button>
            )
          })}

          <p className="absolute left-[32px] top-[236px] font-medium text-ink text-[14px]">
            Risk preference
          </p>
          {RISK_PRESETS.map((r, i) => {
            const selected = r.lambda === risk
            return (
              <button
                key={r.label}
                type="button"
                disabled={busy}
                onClick={() => !selected && requestRisk(r.lambda)}
                className={`absolute top-[269px] w-[168px] h-[46px] rounded-[6px] text-[14px] font-medium transition ${
                  selected ? 'bg-[#e7ece3] text-brand ring-2 ring-brand/50' : 'bg-[#e7ece3] text-brand hover:brightness-95'
                }`}
                style={{ left: `${32 + i * 184}px` }}
              >
                {r.label}
              </button>
            )
          })}

          <p className="absolute left-[32px] top-[355px] text-muted text-[13px] leading-[23px]">
            {actionError ? (
              <span className="text-[#b4532f]">{actionError}</span>
            ) : plan ? (
              <>
                Each change re-runs the optimizer and replaces the plan (and any approval).
                <br />
                {plan.risk_supported ? 'Risk appetite is part of the optimization.' : 'Risk appetite is recorded; the engine does not apply it yet.'}
              </>
            ) : (
              <>
                No plan yet: these settings are used when you run the survey.
                <br />
                Every number comes from the backend optimizer.
              </>
            )}
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
