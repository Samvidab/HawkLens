# Lane A (critical path), branch `lane-data`

Phase 1 done (AC-1). **Phase 2 done live** (Gemini via Vertex AI, 2026-11-14 ~19:25–19:45 UTC): genuine send_back, hero interior, full cache warm-up, read_only replay all pass.

## Done
- T0.1, T0.2 (before this session)
- T0.3/T0.4 (`f5a16ce`, `d711f9f`, `0a1e311`): `adapters/README.md`; `costar.py`, `matterport.py`, `vexcel.py` (overhead), `types.py`. Live test (`-m live`) passes.
- T1.1 (`a51e025`, `0a1e311`): `data/portfolio.json`, 8 Houston offices, all with Vexcel overhead. Hero 23551 Harwin Plaza II, model `hu9LX64osUN` (17 panos, 3 rooms, public).
- T1.5 (`93f652f`) records agent · T1.6 (`dc629c7`) aerial inspector · T1.8 (`bbcffd3`) `survey_one.py`, **AC-1 passes**.
- T2.1 (`dff900c`): `agents/graph.py` (orchestrator plan → `Send` fan-out → survey subgraph [records → aerial ∥ interior → site engineer → verify ⟲ reinspect → finalize] → collect). Live run_8e9dd656: 8/8 buildings, 4 at a time, 23 upgrades; aerial Gemini calls for all 8 cached.
- T2.2 (`d52f2ac`): `agents/verifier.py` (batched per building/inspector; verified / rejected / sent back ≤2 loops / unverified; errors never send back). Path proven in tests incl. 3 `send_back` events.
- T2.3 (`fc0d908`): `agents/interior.py` (5 farthest-point panos × 3 faces, lighting/HVAC/window claims, 3D pins, MatterPak when available).
- Merges of `agent`: `41b48e4` (resolved llm.py/main.py keeping both sides; `POST /run` = survey → Lane B goal replan → `done`), `228e4c5` (quant engine, fast-forward).
- `35eb598`: Matterport skybox links re-signed on 410 Gone (seen live).
- `31de528` **showcase_url**: `BuildingProfile.showcase_url` (optional) set by the records agent for public/unlisted hero models and merged into `interior_scan.json` (where the resolver reads it). Live: hero 23551 → `https://my.matterport.com/show/?m=hu9LX64osUN`. Samples regenerated with `scripts/make_samples.py`.
- `ENGINE_MODE=live` set in this worktree's `backend/.env`. Live engine end to end (run `warm_full`, 2026-11-14 18:39 UTC): 8/8 surveyed → live optimize (`stub: false`) → composer `target_gap` ("2,006 t/yr short": every claim unverified, so solar/cool roof stay out of the optimizer) → `done`.
- `scripts/warm_cache.py`: `--probe` checks Gemini; default = hero first (verifier + interior get quota first), then the full `POST /run` pipeline, summary in `data/runs/warm_full/warm_summary.json`.

- **Live runs via Vertex AI** (merge `6561e1b`, `VERTEX_API_KEY` express mode, `scripts/warm_cache.py`):
  - **Genuine send_back** (hero, interior HVAC claim): `sent back: "Is there a photo clearly showing the wall-mounted thermostat?"` → inspector re-check dropped the thermostat (`re-check: hvac vav_diffuser`) → verified on loop 1.
  - **Hero interior** (`hu9LX64osUN`, 5 of 17 panos): lighting fluorescent (verified: "Fluorescent troffer fixtures are clearly visible in the ceiling tiles"), HVAC vav_diffuser (verified after the send_back), windows unknown (unverified, nothing seen). 5 pins at scan xyz, all verified. LED retrofit is now backed by an observed claim instead of assumed.
  - **warm_summary.json** (`data/runs/warm_full/`): 8/8 buildings, **43 claims: 42 verified, 1 unverified** (hero window), 0 rejected; 1 send_back, 1 re-check; only error event = mesh unavailable.
  - **Target gap closed**: before (all claims unverified, run 18:39) live optimize was infeasible, 2,006 t/yr short, p(hit) 0.00, layout `target_gap`. Now plan `31c0d8cb3a2e`: status ok, shortfall 0, p(hit) 0.811, 22 upgrades selected, 4,119 t/yr, upfront $24,750,248 (live engine, `stub: false`), layout `portfolio_overview`.
  - Memo for that plan written and cached via `memo.write_memo` (no approve, so no finance/Nessie calls).
  - **read_only replay** (`ro_check`): full pipeline from cache only → same plan, same send_back, `done: Workspace ready`. 32 Gemini responses cached.
- Fix found by the live run: `verification.json` is the resolver's `list[Claim]` (final statuses), written at finalize; my per-round log moved to `verification_log.json`. Pricing/compose had failed on the old shape.

## Blocked / open
- Gemini blocker resolved by Vertex AI. History: free-tier 20/day cap (429), then prepaid credits depleted (402); the overnight 30-min retry loop was not started in time (my error), later replaced by an immediate run after the Vertex merge.
- **MatterPak not downloadable**: all 37 portfolio models report `unlocked` but resources `unavailable`. The Showcase tour covers the 3D view meanwhile.
- **Hero scan is one suite** (1,026 sf of 105,717 sf, coverage 0.97%, empty wall graph): scanned area not used as building floor area; envelope null → no insulation.
- **Vexcel obliques**: `backend/toolkit/` still not on `agent`; facades empty, no window_upgrade.

## Requests for Lane B (I no longer edit main.py or llm.py)
- `memo.py`: the number guardrail makes the model spell out numbers inside building names ("seventy-nine hundred Fannin", "CityNorth six", "Harwin Plaza two"). Building names should be allowed verbatim (they're in `sources`, but as whole strings, so their digits aren't matched).
- `schemas/profile.py`: I added optional `showcase_url` (additive) and regenerated `docs/agent/samples/` with your `make_samples.py`. Shout if you'd rather own that field.
- `composer.save_state` overwrites `state.json`; `graph.run_full` re-merges `status`/`results` after it. A merge in `save_state` would be cleaner.

## Notes
- venv: main checkout `backend/.venv` (Python 3.11.9, no pip). The engine merge needs `pulp[cbc]`; installed the pinned requirements with `uv pip install --python …/.venv/bin/python -r requirements.txt` (CBC solver available).
- Tests: 402 pass (both lanes + engine) + live-marked.
- Port 8765 is taken by another process; I run the API on 8791.
- `COSTAR_KIT_DIR` added to this worktree's `backend/.env`. CoStar CDN photos (403) skipped by decision.
