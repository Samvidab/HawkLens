# CLAUDE.md: HawkLens quant engine (`backend/app/engine/`)

You are building the quant engine for HawkLens (HackPrinceton Fall 2026, Sustainability track; the docs still say RetroAlpha). Deadline: submit by Sun Nov 15, 7am ET.

The engine prices the feasible upgrades the agent team finds, ranks them by cost per tonne of CO2, and picks the cheapest, lowest-risk set of upgrades that hits the owner's CO2 target.

## Read first
- `../../../docs/agent/02-TRD.md`: §5 schemas (`FeasibleUpgrade`, `Goal`), §8.1 the engine contract, §9 replan routing.
- `../../../docs/agent/03-APP-FLOW-UIUX.md`: §5 widget props (`abatement_curve`, `plan_table`, `risk_histogram`, `target_control`, `target_gap_card`, `building_header`). Your outputs feed these.
- `backend/CLAUDE.md` is written for the agent-team role. For work in this folder, THIS file sets your role, branch and tasks. Its hard rules about data, caching, Python 3.11, Pydantic v2 and "no LLM-generated numbers" still apply.

The owner of this folder is new to NumPy, PuLP and FastAPI. After each change, explain the code in plain language, and point out anything that would be hard to defend to a judge.

## Scope and boundaries
- **Houston only.** `assumptions.json` and the test fixtures cover Houston and nothing else. `Goal.city` still allows "Los Angeles" so it matches the TRD, but don't add LA values or LA fixtures.
- Edit only `backend/app/engine/` and `backend/tests/engine/`. The one allowed change outside them: add `numpy` and `pulp[cbc]` to `backend/requirements.txt` (pin versions after install, like the rest of the file).
- Do not edit `integrations/engine_client.py`. The agent owner switches it to call this engine with `ENGINE_MODE=live`.
- The engine is imported in-process by the backend (TRD §8.1 prefers this). No HTTP endpoints needed unless the team decides otherwise.
- Never commit `data/`, `cache/` or `.env`. Never store CoStar, Vexcel or Matterport data anywhere else. The engine works on derived numbers only (areas, sizes, kWh, costs).
- No LLM calls in the engine. Every number the app shows comes from this code.

## Git
- Work on branch `quant-engine`, based on current `main` (the remote branch only has the initial commit, so start it from `main`).
- Commit after each step's tests pass. Run `pytest` from `backend/` before every merge.
- Merge into `main` at the team's points (TRD plan "Git workflow"): by ~Sat 10am–1pm (contract functions working), ~Sat 4–6pm (live engine wiring), ~Sat 8–9pm (MVP). Never in the last hour before judging.

## Setup
```
cd backend
python -m pip install "pulp[cbc]" numpy
python -c "import pulp; print(pulp.listSolvers(onlyAvailable=True))"   # must include PULP_CBC_CMD
```
- Solve with `pulp.PULP_CBC_CMD(msg=0)`. It uses the CBC binary bundled inside pulp, so it works without the venv on PATH. PuLP 3.3 marks it deprecated (removed in 4.0), so `optimizer._solver()` silences that one warning; `requirements.txt` pins pulp 3.3.2. Before any PuLP upgrade, switch to `COIN_CMD(path=<venv>/bin/cbc, msg=0)`. Plain `COIN_CMD()` without `path` looks for `cbc` on PATH and fails when the venv isn't activated.
- Fallback solver: HiGHS (`pip install highspy`), `pulp.HiGHS(msg=0)`, used only if `PULP_CBC_CMD` isn't in `listSolvers(onlyAvailable=True)`.
- Use `app.config.get_settings()` for `data_dir`. Don't hardcode paths.

## Contract (must match TRD §8.1 exactly)
Put these in `backend/app/engine/__init__.py` (implemented in the modules below):

```python
simulate(upgrades: list[FeasibleUpgrade], assumptions: dict) -> {
    upgrade_id: {exp_npv, p_loss, cvar5, tonnes_lifetime, cost_per_tonne, hist_bins,
                 upfront_usd, tonnes_per_year}}          # last two: extra, needed by plan_table
macc(exclusions: list[str]) -> {bars: [{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}]}
optimize(target_pct, risk_lambda, budget_usd, exclusions, *, min_p_hit=0.8) -> {
    plan_id, selected: [upgrade_id], exp_npv, cvar5, p_hit_target, total_upfront, tonnes_per_year,
    # extra, needed by widgets:
    status,            # "ok" | "infeasible"
    p_loss, hist_bins, # plan-level risk_histogram
    tonnes_needed,     # target_control (always the owner's target_pct)
    shortfall_tonnes, cheapest_extra,   # target_gap_card, when infeasible; each extra has fits_budget
    internal_target_pct, min_p_hit, met_min_p_hit, p_hit_retries}
set_assumption(key, value) -> {ok} | {ok: False, error}
baseline(building_id) -> {annual_spend_usd, tonnes_per_year}   # extra, for building_header
```
- `min_p_hit` (extra, keyword-only, default 0.8): the target constraint uses *expected* tonnes, so a plan that only just clears it hits the target in about half the scenarios. If `p_hit_target < min_p_hit`, `optimize` raises the internal target by 2 percentage points and re-solves, at most 10 times. It returns the first plan that reaches `min_p_hit`, or the one with the highest `p_hit_target` (stopping early if a raised target becomes unreachable). `tonnes_needed`, `p_hit_target` and `shortfall_tonnes` always use the owner's `target_pct`; `internal_target_pct` is the one actually solved. `min_p_hit=0` turns it off.
- `cheapest_extra[i].fits_budget`: True if adding that upgrade (dropping whatever it replaces in its building/category slot) keeps total upfront within `budget_usd`. Always True with no budget.
- `set_assumption` keys are dotted paths into assumptions.json (`upgrades.led_retrofit.unit_cost`); a bare global key (`discount_rate`) also works. Unknown keys, wrong types and values the engine rejects (dry-run on the cached upgrades) return `{ok: False, error}` and change nothing. Overrides persist across `simulate` calls until restart.
- `risk_lambda` is accepted and part of `plan_id`, but not applied until build step 7.
- `simulate` and `baseline` take an extra keyword `buildings_root` (default `data_dir/buildings`); tests point it at the fixtures.
- `hist_bins` = `[{x0, x1, count}]`, 30 bins (the `risk_histogram` widget's format).
- The extra fields only add to the contract; they don't break it. Tell the agent owner they exist.
- State: `simulate` caches its scenario arrays in module memory. `macc` and `optimize` use the latest cached simulation. `set_assumption` updates assumptions and marks the cache stale (re-simulate on next call).
- `exclusions` may contain upgrade IDs or building IDs. A building ID excludes all its upgrades.
- Skip upgrades with `include_in_optimizer == False` unless they are passed in explicitly as included.
- Until the agent branch's schemas (`app/schemas/upgrades.py`) reach `main`, mirror `FeasibleUpgrade` and `Goal` from TRD §5 in `engine/models.py` and swap to the real import once they land.

### Unconfirmed (assume, but confirm with the agent owner)
- `target_pct` scale: assume a percentage 0–100 (the UI slider shows 0–80 %, default 40).
- Building fields: read `rba_sqft`, `floor_area_sqft`, `envelope_area_sqft`, `city` from `data/buildings/<id>/profile.json` and `interior.json` (TRD §8.1). Isolate this in `buildings.py`, so a field-name change touches one file.
  - Only buildings with a Matterport scan have `interior.json`. Without one: `floor_area_sqft` = `rba_sqft`, and `envelope_area_sqft` = 4 × √(rba_sqft / stories) × floor height × stories (square footprint, TRD §7 floor height). Both are flagged `*_estimated = True`.
- Property types: `buildings.PROPERTY_TYPE_TO_BENCHMARK` maps CoStar `property_type` to a benchmark key; unknown types use `"Other"`. TODO: confirm against CoStar's real names.
- Baseline energy: from Nessie bills (`integrations/nessie_client.get_bills(building_id)`, TRD §8.2) when `NESSIE_MODE=live`; otherwise a benchmark: energy use per sq ft by building type × `rba_sqft`. The `Bill` schema isn't defined yet, so isolate it in `buildings.py` too.

## Upgrade vocabulary (from TRD §5)
| type | category | size_unit | cost basis |
| --- | --- | --- | --- |
| rooftop_solar | solar | kW | $/kW; generation = kW × kWh/kW/yr (city yield) |
| cool_roof | roof | sqft | $/sqft; savings in kWh per sqft of roof per year (`savings_unit: kwh_per_sqft_year`) |
| window_upgrade | envelope | sqft | $/sqft |
| insulation | envelope | sqft | $/sqft; savings in kWh per sqft of wall per year (`kwh_per_sqft_year`) |
| heat_pump | hvac | sqft (served area) | $/sqft |
| led_retrofit | lighting | sqft (floor area, TRD §7) | $/sqft |

At most one upgrade per building per category. Savings basis per type is `savings_unit` in assumptions.json: `kwh_per_sqft_year` (cool roof, insulation: kWh = s × sqft treated), `fraction_of_building_kwh` (windows fixed; heat pump and LED scaled by coverage = size / floor area), `fraction_of_modeled_generation` (solar). Upfront cost C0 = max(unit_cost − avoided_replacement_cost_per_unit, 0) × size (incremental over like-for-like); incentive and maintenance use the full unit_cost × size, and the incentive is capped at that full cost.

Caps, applied in every scenario before dollars and CO2:
- Efficiency upgrades (everything except solar): kWh saved ≤ building baseline kWh × `global.max_savings_share` (placeholder 0.5). Excess is dropped.
- `rooftop_solar`: self-consumed kWh ≤ building baseline kWh × 1.0, valued at `electricity_rate_usd_per_kwh`. Generation above that is exported, valued at `cities.<city>.export_rate_usd_per_kwh` (placeholder 0.04; must be sourced). CO2 counts all generation, exported or not. Use the `exports_excess` flag, not `export_rate > 0`, to tell solar apart, so a $0 buyback rate still counts exported CO2.

## assumptions.json (`backend/app/engine/assumptions.json`)
The data/pitch owner fills in sourced values; every field's unit and definition is in `ASSUMPTIONS.md`. Until then, use placeholders and mark each with `"source": "PLACEHOLDER"`.
- Global: `n_scenarios` 10000, `n_scenarios_optimizer` 1000, `seed`, `discount_rate` 0.07 (overridden by `Goal.discount_rate`), `energy_price_growth` {mu, sd}, `carbon_price` {p_fee_starts, start_year_range, price_range_per_tonne}.
- Building estimates: `floor_height_m` (for the envelope fallback).
- Per city (Houston only): `electricity_rate_usd_per_kwh`, `grid_kg_co2_per_kwh`, `solar_kwh_per_kw_year`, benchmark `kwh_per_sqft_year` by benchmark type (incl. `"Other"`).
- Per upgrade type: `cost_unit` (matches the size unit), `unit_cost`, `avoided_replacement_cost_per_unit` (optional, default 0), `savings_unit`, `savings_mu`, `savings_sd`, `life_min`, `life_max`, `incentive_fraction`, `incentive_p`, `incentive_lag_years` (1 tax credit, 0 rebate), `maint_frac_per_year`, `source`.
- Global also has `general_inflation` (grows maintenance).

## Math
### NPV per scenario (vectorized over K scenarios)
```
NPV = -C0 + I/(1+r)^lag + sum_{t=1..L} [ B*s*(1+g)^t + T*P_t - M*(1+i)^t ] / (1+r)^t
```
C0 upfront cost; I incentive (paid with probability incentive_p); lag `incentive_lag_years`; B baseline annual energy spend (portion this upgrade affects); s savings fraction; g energy price growth; T annual tonnes avoided; P_t carbon price in year t (0 before a fee starts); M maintenance at today's prices; i `general_inflation`; r discount rate; L lifespan.
- Energy-savings sum, closed form: `B*s*q*(1-q**L)/(1-q)` with `q=(1+g)/(1+r)`. If q == 1, use `B*s*L`. Maintenance uses the same form with `q=(1+i)/(1+r)`.
- t starts at 1, not 0.
- Year 1 already includes one year of growth (`(1+g)^1`) on purpose: B is the trailing 12 months of bills, so year 1 (the next 12 months) is one year later.
- Annual tonnes: `T = kwh_saved_per_year * grid_kg_co2_per_kwh / 1000`. Lifetime = T × L.

### Monte Carlo (`monte_carlo.py`)
- `rng = np.random.default_rng(seed)`.
- Energy price growth g: ONE array of K draws shared by all upgrades (this creates correlation). Never per upgrade.
- Carbon fee (whether it starts, start year, price per `carbon_price`): also ONE shared draw per scenario. A fee is market-wide, so every upgrade sees the same one.
- Per upgrade: s ~ Normal(mu, sd) floored at 0; L ~ integer uniform [life_min, life_max]; incentive ~ Bernoulli(p). Each upgrade's stream is seeded from (seed, crc32(upgrade_id)), so excluding one upgrade never changes another's numbers.
- Carbon fee start years count from year 1, the first year after install: start year 3 means the fee applies in years 3..L. Draw from `start_year_range` as whole years ≥ 1 and pass them straight to `npv.carbon_pv` / `npv(carbon_start_year=...)`. A start year > L earns nothing; don't clip it to L. Scenarios where the fee never starts pass price 0.
- Keep per upgrade: `npv[K]`, `tonnes_per_year[K]`, `tonnes_lifetime[K]`.

### Risk (`risk.py`), alpha = 0.05
exp_npv = mean; p_loss = mean(npv < 0); cvar5 = mean of the worst 5% of npv (usually negative; higher = better worst case); hist_bins over the 0.5–99.5 percentile range.

### Abatement curve (`macc.py`)
cost_per_tonne = -exp_npv / mean(tonnes_lifetime). Negative = cuts carbon and makes money. Bars sorted ascending by cost_per_tonne.

### Optimizer (`optimizer.py`)
- Binary x_i per eligible upgrade (PuLP).
- Constraints: sum(E[tonnes_per_year_i] x_i) >= target_pct/100 × portfolio baseline tonnes per year; one per building per category; sum(upfront) <= budget_usd if given; excluded = 0.
- Step 1 (MVP): maximize expected NPV.
- Step 2 (after step 1 passes tests): maximize E[NPV] + risk_lambda × CVaR (Rockafellar–Uryasev over n_scenarios_optimizer): variables eta (free), u_k >= 0, u_k >= eta - sum_i npv[i,k] x_i; CVaR term = eta - sum(u_k)/(alpha*K).
- p_hit_target = share of scenarios where the plan's tonnes_per_year >= the target.
- Infeasible: status "infeasible", shortfall_tonnes, and cheapest_extra = up to 3 excluded-or-unselected upgrades with the lowest cost_per_tonne.
- plan_id = short hash of (inputs, target, lambda, budget, exclusions), so the same request gives the same ID.
- `brute_force()` enumerates every plan for small cases. It is the test oracle for PuLP.
- Speed: optimize < 1 s for 10 buildings. If slower, precompute plans for target steps of 5 %.

## Files
```
backend/app/engine/
  CLAUDE.md  __init__.py  models.py  assumptions.json  ASSUMPTIONS.md
  buildings.py   # building fields + baseline (one place for field names)
  npv.py  monte_carlo.py  risk.py  macc.py  optimizer.py  state.py
backend/tests/engine/
  fixtures/      # sample feasibility.json + profile.json for 3 buildings
  test_npv.py  test_monte_carlo.py  test_optimizer.py  test_contract.py
```

## Build order (each step: tests pass → commit)
1. Branch from main, add deps, `models.py`, `assumptions.json` placeholders, fixtures for 3 buildings.
2. `npv.py`. Test: 2 hand-checked cases match a spreadsheet to the dollar.
3. `monte_carlo.py` + `risk.py`. Test: all sd = 0 and fixed life → mean NPV equals the deterministic NPV. Mean stabilizes from K = 1,000 to 10,000.
4. `macc.py`. Test: sorted ascending; negative cost_per_tonne when NPV > 0.
5. `optimizer.py` step 1 + brute force. Test: PuLP == brute force on the 3-building fixture.
6. Contract functions in `__init__.py`. Test (`test_contract.py`): output keys and types match TRD §8.1 + the extras above. **Tell the agent owner they can set `ENGINE_MODE=live`.**
7. Optimizer step 2 (CVaR). Test: raising risk_lambda lowers or holds p_loss.
8. Carbon price scenario. Real assumptions from the pitch owner.

## Sanity checks before the demo
- Same inputs → same outputs (fixed seed, same plan_id).
- At lambda = 0 with no budget, raising the target never raises exp_npv.
- Raising lambda lowers or holds p_loss.
- Doubling a building's baseline spend makes its upgrades more attractive.
- An unreachable target returns status "infeasible" with a shortfall, not an error.

## Common mistakes
- Discounting from t = 0; mixing monthly and annual values; writing 7 instead of 0.07.
- Drawing energy price growth per upgrade (kills correlation).
- Flipping the CVaR sign or averaging the wrong tail.
- Missing the one-per-building-per-category constraint or the budget.
- Dividing by zero when q == 1.
- Python loops over scenarios instead of NumPy arrays.
