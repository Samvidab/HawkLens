// ---------------------------------------------------------------------------
// Mock model — shared across screens.
// Everything is anchored on the Figma data point: 40% target ->
// 1032 tonnes/year, $1280k investment, +$486k lifetime net value, "covered".
// None of this is real data; it just makes the prototype feel alive.
// ---------------------------------------------------------------------------
export const TARGET_MIN = 0
export const TARGET_MAX = 80 // App Flow 2.1: slider 0-80 %
export const SLIDER_WIDTH = 376 // px, matches Figma track width
export const BUDGET_K = 1500 // "Budget $1500k"

export function fmtMoneyK(valueK) {
  return `$${Math.round(valueK).toLocaleString('en-US')}k`
}

export function clampTarget(value) {
  const snapped = Math.round(value / 5) * 5
  return Math.max(TARGET_MIN, Math.min(TARGET_MAX, snapped))
}

export function deriveModel(target) {
  const tonnes = Math.round((1032 / 40) * target)
  const investmentK = Math.round((1280 / 40) * target)
  const netValueK = Math.round(486 * (target / 40) * (1 - Math.max(0, target - 40) / 160))
  const covered = investmentK <= BUDGET_K
  const confidence = Math.max(
    35,
    Math.min(99, Math.round(99 - (investmentK / BUDGET_K) * 20 - Math.max(0, target - 40) * 1.2)),
  )
  return {
    target,
    tonnes,
    investmentLabel: fmtMoneyK(investmentK),
    netValueLabel: `${netValueK >= 0 ? '+' : '-'}${fmtMoneyK(Math.abs(netValueK))}`,
    covered,
    statusLabel: covered ? 'Your goal is covered' : 'Over your budget',
    annualLabel: `${tonnes.toLocaleString('en-US')} tonnes / year`,
    confidence,
  }
}
