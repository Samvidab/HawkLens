# STATUS — Lane B (support), branch lane-support

## Done (all committed, 100 tests green)
- T1.2 schemas (`app/schemas/`)
- T1.3 LLM wrapper (`app/agents/llm.py`) — unit tests + live smoke test passed (real image + toy schema, 2nd call cached) using GEMINI_MODEL_VISION=gemini-3.5-flash override; added 60 s per-call timeout and no-retry on non-transient 4xx
- T1.4 events bus + SSE router (`app/events.py`) — router not yet mounted in main.py (not my file)
- T1.7 feasibility rules (`app/rules/`)
- widgets: registry, templates, resolver (`app/widgets/`)
- T4.1 guardrails: `check_numbers`, `guarded_text`, `fill_placeholders`, `StepCounter` (`app/guardrails.py`)

- llm.py: vision falls back once to GEMINI_MODEL_VISION_FALLBACK (=gemini-3.5-flash, set in all 3 .env) on 5xx/timeout after retries; cached under primary key

- main.py: events router mounted, GET /registry, GET /portfolio (returns portfolio.json as-is)

- T2.4 engine + Nessie stubs (`integrations/engine_client.py`, `nessie_client.py`, `fixtures/engine/stub_params.json`) with contract tests. Stub engine returns the extras the quant-engine branch documents (upfront_usd, tonnes_per_year, status, p_loss, hist_bins, tonnes_needed, shortfall_tonnes, cheapest_extra, baseline()) and flags `stub: true`. Live mode imports `app.engine`. Nessie `Bill` shape is mine (TRD left it undefined); teammate to replace file.

## In progress
- nothing

## Blocked / needs others
- pricing owner must match the plans/current.json shape in `app/widgets/resolver.py` docstring (incl. per-upgrade `upfront_usd`)
- aerial/interior authors must use claim field prefixes in `app/rules/feasibility.yaml`
- (model names: resolved, see below)

## Gemini model choice (resolved 2026-11-14; written to .env in support, data, and main checkouts)
VISION=`gemini-3.6-flash`, FAST=`gemini-3.5-flash-lite`. Three trials each (one image call / one tiny text call, 60-100 s cap):

| role | model | trial 1 | trial 2 | trial 3 | verdict |
|---|---|---|---|---|---|
| vision | gemini-pro-latest | 404 | - | - | not on key |
| vision | gemini-3.1-pro-preview-customtools | 404 | - | - | not on key |
| vision | gemini-3.7-flash | timeout 100 s | 503 | timeout 60 s | unreliable |
| vision | gemini-3.6-flash | 503 | ok 3.0 s | ok 18.2 s | **chosen** (llm.py retries 5xx) |
| vision | gemini-3.5-flash (extra baseline) | ok ~21 s (smoke) | - | ok 18.2 s | reliable, one tier older; fallback |
| fast | gemini-3.5-flash-lite | ok 5.4 s | ok 4.0 s | ok 0.8 s | **chosen** |
| fast | gemini-3.1-flash-lite | ok 2.4 s | timeout 100 s | ok 13.9 s | unreliable |
| fast | gemini-3.5-flash | ok 31.5 s | ok 3.2 s | ok 5.1 s | slower, variable |
Earlier: gemini-3.8-flash gave 503 / hang; gemini-3.1-pro-preview 404.
Latency is high and variable (vision 3-20 s per call); plan the demo from cache.
