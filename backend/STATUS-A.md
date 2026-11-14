# Lane A (critical path), branch `lane-data`

Tasks: T0.3 → T0.4 → T1.1 → T1.5 → T1.6 → T1.8

## Done
- T0.1, T0.2 (before this session)
- T0.3 **partial**: kit read; `scripts/explore_toolkit.py` (inventory + `--pull <PropertyId>`); `app/adapters/README.md` with real field names. CoStar record + Matterport model list cached for 23347 "333 Northbelt"; read_only re-run hits cache.

## In progress
- T0.4 adapters: `costar.py` from the local kit (unblocked).
- T1.6 groundwork: `app/agents/prompts/aerial.md` drafted.

## Blocked
- **Overhead/oblique imagery (T0.3 pulls 3–4, T0.4 vexcel.py, T1.1 coverage filter, T1.6):** no Vexcel docs/endpoints anywhere in the kit; CoStar aerial photo URLs on the CDN return 403 to a plain GET (header workaround not attempted: treated as an access control).
- **Matterport API (T0.4 matterport.py):** kit says connection details come in a separate zip; not received.
- **T1.5:** waits on Lane B schemas (`git merge agent` when told).

## Notes
- venv: main checkout `backend/.venv` (Python 3.11.9).
- `COSTAR_KIT_DIR` was only in the main checkout root `.env`; added to this worktree's `backend/.env`.
- No `models_index.csv` in the kit; `commercial-properties.csv` already carries `MatterportModelId`.
- City in CSV isn't normalized; use `primaryAddress.researchMarketId` (14 Houston, 20 LA).
