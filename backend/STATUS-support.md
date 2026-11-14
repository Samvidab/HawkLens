# STATUS — Lane B (support), branch lane-support

## Done (all committed, 100 tests green)
- T1.2 schemas (`app/schemas/`)
- T1.3 LLM wrapper (`app/agents/llm.py`) — unit tests + live smoke test passed (real image + toy schema, 2nd call cached) using GEMINI_MODEL_VISION=gemini-3.5-flash override; added 60 s per-call timeout and no-retry on non-transient 4xx
- T1.4 events bus + SSE router (`app/events.py`) — router not yet mounted in main.py (not my file)
- T1.7 feasibility rules (`app/rules/`)
- widgets: registry, templates, resolver (`app/widgets/`)
- T4.1 guardrails: `check_numbers`, `guarded_text`, `fill_placeholders`, `StepCounter` (`app/guardrails.py`)

## In progress
- nothing

## Blocked / needs others
- main.py must `include_router(events.router)` and expose `GET /registry` -> `widgets.registry.json_schemas()`
- pricing owner must match the plans/current.json shape in `app/widgets/resolver.py` docstring (incl. per-upgrade `upfront_usd`)
- aerial/interior authors must use claim field prefixes in `app/rules/feasibility.yaml`
- **HUMAN: `.env` GEMINI_MODEL_VISION=gemini-3.1-pro-preview returns 404 on this key (same in main checkout .env).**
  Models the key lists include gemini-3.5-flash, 3.6-flash, 3.7-flash, 3.8-flash, 2.5-pro (2.5-flash is closed to new users).
  Observed 2026-11-14: 3.8-flash (= GEMINI_MODEL_FAST) gave 503 'high demand' / hung; 3.5-flash and 3.6-flash work but ~20 s per call.
  Need a decision on which model names to put in .env (I did not edit .env).
