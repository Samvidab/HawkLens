# Lane A (critical path), branch `lane-data`

Tasks: T0.3 → T0.4 → T1.1 → T1.5 → T1.6 → T1.8

## Done
- T0.1, T0.2 (before this session)
- T0.3 **partial** (`f5a16ce`): kit read; `scripts/explore_toolkit.py`; `app/adapters/README.md`. CoStar record + Matterport model list cached for 23347.
- T0.4 **partial** (`d711f9f`): `adapters/costar.py` (`search_properties`, `get_property`, `matterport_model_ids`) over the local kit, streamed, cached; `tests/test_adapters.py` (6 tests incl. read_only cache hits).
- T1.1 (`a51e025`): `scripts/pick_portfolio.py` → `data/portfolio.json`: 8 Houston offices, hero 23551 Harwin Plaza II (10 Matterport models). Vexcel coverage = "unchecked".

## In progress
- none (everything left is blocked)

## Blocked
- **Imagery (T0.3 pulls 3–4, T0.4 vexcel.py, T1.6, T1.8):** no Vexcel docs/endpoints in the kit; CoStar aerial photo URLs on the CDN return 403 to a plain GET (header workaround not attempted: treated as an access control).
- **Matterport API (T0.4 matterport.py):** kit says connection details come in a separate zip; not received.
- **T1.5:** waits on Lane B schemas (`git merge agent` when told). Lane B's `BuildingProfile` on `agent` matches TRD §5.
- `app/agents/prompts/aerial.md` drafted (uncommitted until T1.6).

## Notes
- venv: main checkout `backend/.venv` (Python 3.11.9). Tests: 20 pass.
- `COSTAR_KIT_DIR` was only in the main checkout root `.env`; added to this worktree's `backend/.env`.
- No `models_index.csv` in the kit; `commercial-properties.csv` already carries `MatterportModelId`.
- City in CSV isn't normalized; use `primaryAddress.researchMarketId` (14 Houston, 20 LA).
- No building footprint in CoStar records; all footprints will be `estimated` (rba / stories square).
- `occupancy_pct` isn't in the property record (would need `location-occupancy.jsonl`); left null.
