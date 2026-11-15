// Strings that only the prototype's invented data contained (names, figures, timestamps, "illustrative" labels).
// Strict demo mode: none may ever render. Used by the unit audit (pages/Strict.test.jsx) and the browser audit (e2e).
export const FORBIDDEN = [
  'Midtown', 'HOU–', 'Houston Asset Partners', 'Owner checking', '•• 2048', '$2,400,000', '$1280k', '+$486k', '1032 tonnes',
  '1,032', '87%', '1,200 m²', '120 kW', '96 tonnes', '−$94k', '4.2%', '09:41', '09:42', '09:43', 'Illustrative', 'illustrative',
  'Created in this demo', 'Draft · Not approved', '18 upgrades across 8 buildings', 'Baseline sample', '10,000 scenarios',
  '$1500k', 'Use cached demo survey', '8 sample buildings', 'interactive prototype', 'Today, 09', 'Schematic', '16,000 sq ft',
  '96,000 sq ft', '$168,000', '420 tCO₂', 'Confidence 0.91', 'Panorama 04', 'Evidence 12', 'Example',
  'sample plan', 'Baseline downside', 'Reference: 40%', 'Start a new demo', 'Hawk Lens Operating',
]

export const PROTOTYPE_IMAGES = /evidence-(roof|facade|interior)|portfolio-3d|building-model/

/** A regex for one forbidden string; a figure never matches inside a longer real number ("396 tonnes" is not "96 tonnes"). */
export const forbiddenRe = (s) =>
  new RegExp(`${/^[\d$+−]/.test(s) ? '(?<![\\d,.])' : ''}${s.replace(/[.*+?^${}()|[\]\\$]/g, '\\$&')}`)

/** The forbidden strings found in `text` (empty = clean). */
export const inventedIn = (text) => FORBIDDEN.filter((s) => forbiddenRe(s).test(text))

export const ROUTES = ['/', '/plan', '/building', '/start-survey', '/survey-in-progress', '/survey-complete', '/financing-approval',
  '/funding-confirmation', '/documents', '/survey-evidence', '/investment-memo', '/risk-and-target', '/plan-preferences',
  '/assumptions', '/funding-account', '/building-insights', '/building-excluded', '/expanded-portfolio-model',
  '/expanded-building-model', '/expanded-survey-image', '/workspace', '/demo-document-notice']
