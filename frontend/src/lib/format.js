// Display formatting only. These never compute a financial metric; they turn the engine's numbers into text.
// A missing value (null / undefined / NaN) always renders as an em dash, never as a made-up number.
export const DASH = '—'

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/** 1280000 -> "$1.28M", 486000 -> "$486k", 950 -> "$950" */
export function usd(v) {
  if (!isNum(v)) return DASH
  const a = Math.abs(v)
  const sign = v < 0 ? '−' : ''
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(a >= 1e7 ? 1 : 2)}M`
  if (a >= 1e3) return `${sign}$${Math.round(a / 1e3).toLocaleString('en-US')}k`
  return `${sign}$${Math.round(a).toLocaleString('en-US')}`
}

/** Exact dollars for money that is about to move: 1280000.5 -> "$1,280,000.50" */
export function usdExact(v) {
  if (!isNum(v)) return DASH
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

/** "+$486k" / "−$94k" */
export function signedUsd(v) {
  if (!isNum(v)) return DASH
  return v > 0 ? `+${usd(v)}` : usd(v)
}

export function tonnes(v, unit = ' tonnes / year') {
  if (!isNum(v)) return DASH
  return `${Math.round(v).toLocaleString('en-US')}${unit}`
}

/** 0.873 -> "87%" */
export function pct(p, digits = 0) {
  if (!isNum(p)) return DASH
  return `${(p * 100).toFixed(digits)}%`
}

export const TYPE_LABEL = {
  rooftop_solar: 'Rooftop solar',
  cool_roof: 'Cool roof',
  window_upgrade: 'Window upgrade',
  heat_pump: 'Heat pump conversion',
  insulation: 'Insulation',
  led_retrofit: 'LED retrofit',
}
export const typeLabel = (t) => TYPE_LABEL[t] || t || DASH

export const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

// Risk preference presets -> Goal.risk_lambda (backend default 0.5 = Balanced).
export const RISK_PRESETS = [
  { label: 'Cautious', lambda: 0.8 },
  { label: 'Balanced', lambda: 0.5 },
  { label: 'Growth', lambda: 0.0 },
]
export function riskLabel(lambda) {
  if (!isNum(lambda)) return DASH
  const hit = RISK_PRESETS.find((r) => Math.abs(r.lambda - lambda) < 1e-9)
  return hit ? hit.label : `λ ${lambda}`
}

export function budgetLabel(budget) {
  return isNum(budget) ? `Budget ${usd(budget)}` : 'No budget limit'
}

/** Plan status -> headline used by every page, so they all say the same thing for the same plan. */
export function statusHeadline(plan) {
  if (!plan) return 'No plan yet'
  if (plan.status === 'ok') return 'Your goal is covered'
  if (plan.status === 'infeasible') return 'Short of your goal'
  if (plan.status === 'no_data') return 'Not priced yet'
  return DASH
}
