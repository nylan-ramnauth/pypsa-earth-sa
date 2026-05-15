---
date: 2026-05-15
time: "13:03"
actor: nylan-ramnauth
workstream: pypsa-earth-rsa-validation
related_codebases: [pypsa-earth, pypsa-rsa]
related_modules: [12_dispatch_calibration, 13d_PyPSA-RSA_run]
status: findings — handoff to Sonnet for module design
---

# PyPSA-RSA (RSA-BM) vs PyPSA-Earth (EAF-OPC-CAP) — 2023 dispatch calibration findings

## Purpose

Capture all findings from the three-way comparison between the PyPSA-Earth calibrated dispatch model (5 scenarios) and the PyPSA-RSA `Benchmark_2023 / S_2023BM` solve, both validated against Eskom 2023 actuals. Output of Module 13 (Earth calibration) + Module 13d (RSA benchmark run) + this analytical pass. Findings inform the next module: targeted improvements to bring PyPSA-Earth's 2023 calibration closer to RSA's accuracy while preserving Earth's multi-year and expansion-modelling capabilities.

The comparison was driven by integrating the RSA solve as a sixth series throughout `pypsa-earth/notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` (133 cells; integration in cells 4–6 + carrier metrics tables + scorecard cell 131). All quantitative results below come from that notebook's re-executed outputs and direct inspection of the two solved `.nc` files.

## Section 1 — Context-parity audit (verified directly from solved networks)

| Dimension | Earth EAF-OPC-CAP | RSA S_2023BM | Match |
|---|---|---|---|
| Calendar year | 2023 hourly | 2023 hourly (MultiIndex `(2023, ts)`) | yes (snapshot grid) |
| Snapshots | 8 760 | 8 760 | yes |
| First / last | 2023-01-01 00:00 → 2023-12-31 23:00 | same | yes |
| Total load | **222.35 TWh** | **225.87 TWh** | **no — 1.6% scaling gap** |
| Load shape | Eskom 2023 hourly contracted | Eskom 2023 hourly contracted | yes (Pearson r = 1.000 hour-by-hour) |
| Spatial resolution | 34 nodes / 68 buses | single region (1) | no — structural |
| Storage units | battery, hydro, PHS | battery_4h, phs | partial (hydro is a Generator in RSA, StorageUnit in Earth) |

**Demand finding (important).** Earth's input load is the Eskom 2023 hourly profile scaled by 0.984. The shape is identical to RSA's input (Pearson r = 1.000 against `za_2023_demand_profile.csv`). The 1.6% loss is introduced inside `pypsa-earth`'s demand-build path (`build_demand_profiles` or `add_electricity`) — likely a sent-out-vs-contracted conversion or losses-adjustment factor that should not be applied for the Eskom-MLR comparison. This is a one-line fix, not a swap-the-source job.

## Section 2 — Carrier scorecard (vs Eskom 2023 MLR)

All values from the re-executed notebook. RSA-BM column added to every scorecard via the Module 13d integration. Pearson r is hourly correlation against Eskom 2023 carrier dispatch.

| Carrier | Eskom GWh | Earth-CAP GWh / Δ% / Pearson_h | RSA-BM GWh / Δ% / Pearson_h |
|---|---:|---:|---:|
| coal | 165 627 | 184 406 / +11.3% / **0.332** | 177 927 / **+7.4%** / **0.585** |
| nuclear | 8 127 | 8 673 / +6.7% / 0.612 | 8 255 / **+1.6%** / 0.612 |
| ocgt | 5 243 | 5 500 / +4.9% / 0.388 | 10 292 / +96.3% / 0.309 |
| hydro | 1 992 | 1 398 / −29.8% / 0.312 | 11 938 / +499% / 0.295 |
| wind | 11 613 | 7 312 / −37.0% / **0.864** | 11 063 / **−4.7%** / 0.094 |
| solar_pv | 5 015 | 3 557 / −29.1% / 0.928 | 5 168 / **+3.1%** / **0.960** |
| csp | 1 375 | 806 / −41.4% / 0.440 | 1 655 / +20.4% / **0.726** |
| load shedding | 16 755 | 10 748 / −35.9% / 0.477 | 138 / −99.2% / 0.218 |

Coal system metrics (cell 26): RSA RMSE = 1 831 MW, MAE = 1 525 MW, weekly Pearson r = 0.952. Earth-CAP RMSE = 2 843 MW, MAE = 2 374 MW, weekly Pearson r = 0.926.

**Scope reminder.** The `hydro` line in this table is inflated for RSA-BM because RSA bundles domestic hydro (~683 MW) with `hydro_import` Cahora Bassa (1 764 MW) under one `hydro` aggregation. Cahora Bassa is **outside** Eskom MLR (international purchase, not Eskom generation), so the +499% delta is an aggregation artifact not a model error. Similarly, RSA's `sasol_coal` (728 MW) and `sasol_gas` (425 MW) are Sasol Synfuels private self-supply, outside MLR — they are correctly absent from Earth's perimeter. Both were excluded by design per the Eskom-glossary scoping work; no action needed.

## Section 3 — Why RSA coal calibration beats Earth (the dominant gap)

Three structural reasons, in order of impact:

### 3.1 Per-plant, time-varying outage profiles
RSA models 15 named coal stations as individual generators (Arnot, Camden, Duvha, Grootvlei, Hendrina, Kelvin, Kendal, Kriel, Kusile, Lethabo, Majuba, Matimba, Matla, Medupi, Tutuka). Each carries its own time-varying `p_max_pu(t)` series — 131 time-varying p_max_pu columns total across the network. Weighted-average coal `p_max_pu` varies by month: **0.452 in January → 0.530 in July**, reproducing the winter-peak availability uptick driven by lower planned-maintenance in winter. Plant-by-plant outage events drive hour-to-hour coal output variation that correlates with the actual fleet — hence Pearson r = 0.585 hourly.

Earth applies a **single uniform `EAF_48` = 0.48 flat** cap to an aggregated `coal` carrier with no plant identity, no seasonal variation, no weekly outage pattern. With a constant cap, coal can only ride load shape, hence Pearson 0.332. The Eskom data portal publishes monthly UCLF/PCLF/OCLF per station back to ~2018 — this data is multi-year-portable and directly ingestible.

### 3.2 Unit commitment + plant-level techno-economics
RSA config: `linearised_unit_committment: ["coal"]`. Scenario S_2023BM applies `override_coal_msl = 0.7` (minimum stable level per plant), `coal_ramp_rate_multiplier = 1.5`, `share_partial_outages.coal = 0.5`. Each of the 15 plants has its own heat rate and fuel cost so older plants (Tutuka, Hendrina) dispatch after newer plants (Medupi, Kusile) when both are available. Earth's coal is fully aggregated — no UC, no MSL, no plant-by-plant merit order.

### 3.3 Topology — individual plants vs aggregated carrier
Each plant in RSA appears as a discrete `Generator` with own `p_nom`, `p_min_pu`, `p_max_pu(t)`, `marginal_cost`, `ramp_limit_up/down`. Earth bundles all coal at each of 34 nodes into a single aggregated coal carrier — losing the structural information needed for plant-resolved dispatch behaviour.

## Section 4 — RE profile provenance findings

Inspected `pypsa-rsa/data/bundle/renewable_profiles_updated.nc` directly via h5py.

| Group | Time-axis units | Length (hours) | Coverage | Is 2023 weather? |
|---|---|---:|---|---|
| `wind_*_wasa` | hours since 2010-01-01 | 87 648 | ~2010–2019 | no |
| `solar_pv_*_sarah` | hours since 2017-01-01 | 52 584 | ~2017–2022 | no (one year picked) |
| solar_csp / bioenergy / hydro / hydro_import | per `config.yaml reference_weather_years` | — | **2021** Eskom historical pu | no |

Consequence: RSA labels snapshots `2023-01-01 .. 2023-12-31` but the underlying RE shapes are a mix of (a) WASA wind climatology, (b) one SARAH year, and (c) 2021 Eskom observed dispatch. The high Pearson r for solar_pv (0.96) reflects the dominance of the diurnal cycle, not 2023-specific weather. The low Pearson r for wind (0.09 hourly, 0.47 weekly) confirms that RSA's wind shape is not 2023 weather — seasonality survives, hourly weather does not. Eskom 2021 pu for CSP still beats Earth's atlite-CSP (0.73 vs 0.44) because the observed profile captures real thermal-storage dispatch that atlite cannot model.

**This is why RSA's RE shapes are not multi-year-portable.** Eskom pu profiles are observed plant output / installed capacity for one observed year — they mix resource + outages + curtailment + grid effects, and they only cover the years Eskom has published. They cannot be replayed at hypothetical new sites or for arbitrary future years.

## Section 5 — Strategic recommendation: weather-input stack for multi-year & expansion modelling

For a PyPSA-Earth ZA model intended to run reliability sweeps across multiple weather years (e.g., 2019–2024) and capacity expansion at greenfield sites, the right weather stack is:

| Carrier | Source | Rationale |
|---|---|---|
| Wind | **ERA5** (with bias correction against met masts / WASA where overlap exists) | WASA stops March 2023, unusable for 2024+ sweep. ERA5 covers 1940–present, biases ~5–15% closeable via linear scaling. Standard practice (Staffell & Pfenninger 2016; Olauson 2018). |
| Solar PV | **ERA5** (SARAH-3 optional upgrade) | ERA5 GHI is ~5% RMSE vs ground; SARAH-3 marginally better but adds a manual CM-SAF download step. Skip unless thesis requires the extra fidelity. |
| CSP | **atlite-CSP** for greenfield expansion; Eskom pu anchor for 2023 validation only | atlite CSP module is basic (no SAM integration in pypsa-earth) but suffices for capacity-mix studies. Keep observed Eskom pu as an anchor in validation years where it exists. |
| Domestic hydro | atlite hydro module scaled by ZAF runoff anomaly | Small carrier (~600 MW ROR/storage). Crude but multi-year. |
| Cahora Bassa import | observed contractual dispatch pattern, scaled per-year | Take-or-pay contract, not weather. Year-portable because the contract is. |
| Biomass | flat must-run at observed CF (~0.57) | 177 MW, 0.4% of energy. Set and forget. |

WASA was considered but rejected: coverage stops March 2023, hybrid logic to splice ERA5 onto WASA for 2024+ is more engineering effort than it saves. Solar SARAH-3 is optional — keep on the deferred-improvement list.

## Section 6 — Scope-correction acknowledgement

Earlier analytical drafts recommended adding `sasol_coal`, `sasol_gas` and `hydro_import` as separate carriers in Earth to mirror RSA. **These recommendations are withdrawn.** Per the Eskom-MLR glossary scoping work (Module 12/13), the calibration perimeter is Eskom-utility + Eskom-contracted IPPs only. Sasol Synfuels cogen is private self-supply outside MLR. Cahora Bassa is international purchase reported separately. Both correctly excluded from Earth's scope. No action needed on these.

Inside the Eskom-MLR perimeter at 2023, OCGT is essentially all diesel (Ankerlig, Gourikwa, Avon, Dedisa) — Karpowership / LNG-OCGT plants are post-2025. So the diesel/gas OCGT split has near-zero merit-order value for 2023 validation. Revisit when gas-to-power IPPs enter the build set for 2030+ expansion scenarios.

## Section 7 — Two tasks remaining (handoff to Sonnet for module design)

### Task A — Demand input alignment (small)

**Problem.** Earth's solved load = 222.35 TWh vs Eskom 2023 contracted = 225.87 TWh. Hour-by-hour Pearson r = 1.000, ratio = 0.984. The shape is already correct; a 1.6% scaling factor is being applied somewhere in the demand-build path.

**Action.**
- Locate the 0.984 multiplier inside `pypsa-earth/scripts/build_demand_profiles.py` and/or `add_electricity.py`.
- Decide whether to drop it (recommended for Eskom-MLR-perimeter calibration) or document it as a deliberate sent-out-vs-contracted conversion.
- Re-run the `za_2023_fixed_validation` snakemake target.
- Re-run notebook; verify Earth total load = 225.87 ± 0.05 TWh.

**Effort.** ~30 min investigation + ~30 min rebuild + notebook refresh. Single-file change.

**Acceptance.** Loaded-status table in notebook shows Earth load matching Eskom contracted ± 0.1 TWh.

### Task B — Coal dispatch realism port (large)

**Problem.** Earth's flat `EAF_48 = 0.48` cap on aggregated coal carrier gives Pearson r = 0.332 hourly vs Eskom 2023 coal dispatch. RSA's per-plant time-varying outage profiles + linearised UC + plant-level techno-economics give Pearson r = 0.585. Coal is 78% of Eskom energy, so this gap dominates total system error.

**Action — three sub-tasks.**

1. **Disaggregate coal carrier into individual plants.**
   - Replace aggregated `coal` carrier in Earth with 15 named stations matching RSA's list (Arnot, Camden, Duvha, Grootvlei, Hendrina, Kelvin, Kendal, Kriel, Kusile, Lethabo, Majuba, Matimba, Matla, Medupi, Tutuka).
   - Assign each plant to its nearest of the 34 nodes based on geographic coordinates.
   - Source per-plant `p_nom`, `heat_rate`, `marginal_cost`, `ramp_limit_up/down` from RSA's plant database (`pypsa-rsa/data/bundle/conventional_plants.xlsx` or equivalent) or Eskom-published station specs.

2. **Ingest plant-level monthly EAF time series.**
   - Pull Eskom data portal monthly UCLF/PCLF/OCLF per station for 2023 (and 2019–2024 for multi-year reuse). Available at https://www.eskom.co.za/dataportal/ under `unit_capability_factors`.
   - Construct hourly `p_max_pu(t)` per plant by repeating monthly EAF values across all hours of the month (matches RSA's approach).
   - Write as a time-series asset under `pypsa-earth/data/za_validation/coal_eaf_monthly_2023.csv` (or netCDF) and wire into `add_electricity` so each plant generator picks up its own series.

3. **Enable linearised unit commitment for coal.**
   - Set `coal` carrier as `committable=True` with relaxed (linearised) UC: `min_up_time`, `min_down_time`, `start_up_cost` per plant.
   - Plant-level `p_min_pu` (MSL) — use 0.7 for newer wet-cooled plants, lower for older dry-cooled, sourced from RSA's `MOD_CNST` parameter set.
   - Verify solver tractability — coal-only UC should not blow up problem size.

**Effort.** ~3–5 days of engineering. Touches `add_electricity.py`, `prepare_network.py`, possibly `solve_network.py`. Adds 1–2 new data files. Re-runs full snakemake pipeline.

**Acceptance.**
- Coal carrier metrics show Pearson r ≥ 0.55 hourly (target = RSA's 0.585 ± 5%).
- Coal Δ% vs Eskom ≤ +8% (target = RSA's +7.4% ± 1%).
- Plant-by-plant capacity factors are within ±5 pp of Eskom-published 2023 station CFs.
- Full notebook re-runs without errors; scorecard cell 131 shows Earth's RSA-class coal correlation.

## References

- Notebook: `6-codebases/repos/pypsa-earth/notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` (133 cells, re-executed 2026-05-15)
- RSA solved network: `6-codebases/repos/pypsa-rsa/results/Benchmark_2023/S_2023BM/networks/solved.nc` (23.2 MB, Gurobi optimal, objective 1.26e+08)
- Earth solved network: `6-codebases/repos/pypsa-earth/results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc`
- Eskom 2023 carrier targets: `6-codebases/repos/pypsa-earth/data/za_validation/eskom_2023_targets_by_carrier.csv`
- Eskom 2023 hourly demand: `6-codebases/repos/pypsa-earth/data/za_validation/za_2023_demand_profile.csv`
- Plan source: `6-codebases/repos/pypsa-earth/doc/active/calibration-plan/13d_PyPSA-RSA_run.md`
- Earlier rationale page: [[3-wiki/concepts/pypsa-earth-rsa-porting-rationale]]
- Related decisions: [[3-wiki/decisions/]] (Module 12/13 Eskom-MLR scope definition)
- Related logs: `5-logs/shared/2026-05-15-0017-restore-pypsa-rsa-runnability-and-prepare-a-future-2023-benchmark-against-pypsa-earth.md`, `5-logs/shared/2026-05-15-0030-pypsa-rsa-2023-benchmark-idea.md`
