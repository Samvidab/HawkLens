# STATUS — Lane B (support), branch lane-support

## Done (all committed, 100 tests green)
- T1.2 schemas (`app/schemas/`)
- T1.3 LLM wrapper (`app/agents/llm.py`) — tested with a faked Gemini call only; no live call yet
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
- live Gemini smoke test of llm.py needs GEMINI_API_KEY + model names in .env
