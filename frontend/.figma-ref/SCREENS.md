# HawkLens — Figma screen inventory & navigation map

Figma file: `Y191JPH4msZ5TqPOTe0iA7` (prototype, single page `0:1`).
Design system: white bg, Inter font, accent green `#335d45`, ink `#222a31`,
muted `#67717a`, border `#e4e7ea`, model bg `#e7ece3`. Each screen is 1440×980.

The prototype's click-to-screen reactions are NOT exported by the Figma MCP tools,
so the navigation below is **inferred from button labels and screen names**. Treat
it as the intended flow; the user will correct any link that should point elsewhere.

## Screens (route ← Figma frame)

| # | Route | Figma frame | node id | Status |
|---|-------|-------------|---------|--------|
| 1 | `/` | Hawk Lens · Portfolio | 4:2 | DONE (interactive) |
| 2 | `/plan` | Hawk Lens · Plan details | 6:2 | DONE |
| 3 | `/building` | Hawk Lens · Building details | 11:2 | DONE |
| 4 | `/survey-evidence` | Hawk Lens · Survey evidence | 11:15 | placeholder |
| 5 | `/financing-approval` | Hawk Lens · Financing approval | 11:28 | DONE |
| 6 | `/documents` | Hawk Lens · Documents | 11:41 | DONE |
| 7 | `/funding-confirmation` | Hawk Lens · Funding confirmation | 17:106 | DONE |
| 8 | `/plan-preferences` | Hawk Lens · Plan preferences | 17:135 | placeholder |
| 9 | `/demo-document-notice` | Hawk Lens · Demo document notice | 17:168 | placeholder |
| 10 | `/expanded-survey-image` | Hawk Lens · Expanded survey image | 17:540 | placeholder |
| 11 | `/expanded-portfolio-model` | Hawk Lens · Expanded portfolio model | 17:548 | placeholder |
| 12 | `/investment-memo` | Hawk Lens · Expanded investment memo | 17:726 | placeholder |
| 13 | `/assumptions` | Hawk Lens · Assumptions and sources | 17:759 | placeholder |
| 14 | `/funding-account` | Hawk Lens · Funding account details | 17:788 | placeholder |
| 15 | `/expanded-building-model` | Hawk Lens · Expanded building model | 17:811 | placeholder |
| 16 | `/risk-and-target` | Hawk Lens · Risk and target | 30:1167 | placeholder |
| 17 | `/building-insights` | Hawk Lens · Building insights | 30:1263 | placeholder |
| 18 | `/start-survey` | Hawk Lens · Start survey | 30:1435 | DONE |
| 19 | `/survey-in-progress` | Hawk Lens · Survey in progress | 30:1450 | DONE |
| 20 | `/survey-complete` | Hawk Lens · Survey complete | 30:1465 | DONE |
| 21 | `/building-excluded` | Hawk Lens · Building excluded | 30:1660 | placeholder |

NOT screens (design-system frames — do not route): "Widget library" (30:57),
"Widget states" (30:449).

## Inferred navigation links

Global nav bar (present on most screens):
- Logo / "Hawk Lens" → `/`
- "Portfolio" → `/`   "Plan" → `/plan`   "Documents" → `/documents`
- Active tab = whichever section the current screen belongs to.

Portfolio (`/`):
- "Run survey →" → `/start-survey`
- "Building details →" → `/building`
- Building click / "View building →" → `/building`
- "Expand ↗" → `/expanded-portfolio-model`
- "Review plan" → `/plan`
- "Check target gap →" → `/risk-and-target`
- "See costs & evidence →" → `/plan`
- Upgrade row → `/plan`

Plan details (`/plan`):
- "Review & approve" → `/financing-approval`
- "Investment memo ↗" → `/investment-memo`
- "View survey evidence" / "↗" → `/survey-evidence`
- "Risk & target details →" → `/risk-and-target`

Building details (`/building`): expand model → `/expanded-building-model`;
insights → `/building-insights`; exclude → `/building-excluded`.

Survey evidence (`/survey-evidence`): expand image → `/expanded-survey-image`;
sources → `/assumptions`.

Financing approval (`/financing-approval`): confirm/approve → `/funding-confirmation`;
account details → `/funding-account`; preferences → `/plan-preferences`.

Documents (`/documents`): open any doc → `/demo-document-notice`.

Start survey (`/start-survey`): begin → `/survey-in-progress` → (auto/continue) → `/survey-complete`.

"Expanded …" and modal-like screens ("Demo document notice", "Building excluded",
"Funding confirmation") should offer a back/close affordance returning to their opener.

Any link whose target is ambiguous should go to the most specific matching screen,
or fall back to a no-op with a toast (match existing App.jsx toast pattern).
