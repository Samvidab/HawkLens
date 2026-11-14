# CLAUDE.md — RetroAlpha backend (Agent + CoStar data)

You are building the agent team and CoStar data layer for RetroAlpha at HackPrinceton (deadline Sun Nov 15, 7am ET).

Read before any work, in order:
1. `../docs/agent/01-PRD.md` — what and why
2. `../docs/agent/02-TRD.md` — architecture, schemas, interfaces
3. `../docs/agent/03-APP-FLOW-UIUX.md` — layout JSON + widget contract
4. `../docs/agent/04-IMPLEMENTATION-PLAN.md` — do tasks in order; pass each check before the next

Hard rules
- Python 3.11, FastAPI, LangGraph, Gemini (`google-genai`), Pydantic v2.
- Never guess CoStar / Vexcel / Matterport API names or fields. Discover them (SDK, MCP, OpenAPI) or stop and ask.
- All external calls go through `adapters/cache.py`. Demo must run with `CACHE_MODE=read_only` and no network.
- LLMs never produce numbers shown to users. Numbers come from code or the quant engine; text uses placeholders.
- No chatbot, no voice, no free-text replies to the owner. Output is layout JSON from the widget registry.
- No database for CoStar data. JSON files in `data/` only. No keys in the browser or in git.
- Finance (Nessie) writes only after an `approve` action with the current `plan_id`.
- Validate every agent output with Pydantic; fall back to templates on failure.
- Work on branch `agent`. Commit after each passing task check and push right away. Merge to `main` only at the points in the plan's Git workflow table, after `pytest` passes.
- Never commit `.env`, `cache/`, or `data/` (except `data/portfolio.json`).
- Keep the build green; when a phase overruns by > 30 min, cut per the plan's fallback table.
- When a task needs an input from the human (see the plan's Inputs table) and it's missing, stop and ask, and move to the next unblocked task.
