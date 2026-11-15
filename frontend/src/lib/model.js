// Target slider constants and helpers shared by the screens.
// The prototype's invented plan model (investment = 1280/40 × target, fixed NPV, $1.5M budget) is gone:
// every number on screen comes from the backend's persisted plan (GET /plan), produced by the quant engine.
export const TARGET_MIN = 0
export const TARGET_MAX = 80 // App Flow: slider 0-80 %
export const SLIDER_WIDTH = 376 // px, matches Figma track width

export function clampTarget(value) {
  const snapped = Math.round(value / 5) * 5
  return Math.max(TARGET_MIN, Math.min(TARGET_MAX, snapped))
}
