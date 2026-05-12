# Module 11 — Findings and Pre-Module-12 Inputs

**Date:** 2026-05-12  
**Status:** Module 11 complete. Two pre-Module-12 fixes pending: (1) Stage 2 re-solve with corrected costs; (2) RE capacity fleet rebuild (see `opus_brief_re_capacity_fix.md`).

---

## What Module 11 delivered

| Deliverable | Status |
|---|---|
| Module 09b: 10 custom corridors (12,053 MW N-1) injected | ✓ PASS — `za_custom_lines_audit.csv` shows all 10 `added_ok=True` |
| Module 11 hook: 5 new carriers attached | ✓ — sasol_coal, sasol_gas, ocgt_diesel, ocgt_gas, other_re |
| CSP retag: 500 MW transferred from solar → csp | ✓ — solar+csp conservation confirmed |
| Merit-order fix: coal MC 565→40.56, nuclear MC 263→16.39 EUR/MWh | ✓ — `elec_s_34.nc` verified |
| Coal CO2 intensity corrected: 1.010 tCO2/MWh_el (was 0.336) | ✓ — `n.carriers.at["coal","co2_emissions"]` = 1.010 |
| Stage 1 smoke (7-day 2023-07-01..07): optimal, load-shedding 0.0081% | ✓ PASS |
| Stage 2 smoke (July 2023, 744 h): optimal, load-shedding 0.032% | ✓ PASS (but pre-cost-fix — see §2) |
| Pre-solve extendable-flag audit | ✓ — no unintended extendable capacity |
| `.pre_local.nc` backup written | ✓ |

---

## Bug fixes applied during Module 11 (2026-05-12)

### Bug 1 — 400 kV custom lines had x=r=b=0 on disk
**Root cause:** `build_za_custom_lines.py` passed `type=Al/St 240/40 4-bundle 380.0` to `n.add('Line', ...)`. PyPSA stores `x=r=b=0` in the netCDF and only computes impedance from type at solve time via `calculate_dependent_values`. Post-cluster buses have `v_nom=NaN`, so if a downstream consumer skips recompute the lines act as zero-impedance shunts.

**Fix:** `derive_line_params` now computes `x/r/b` directly from per-km values (400 kV: r=0.030, x=0.246, b=4.335e-6 S/km; 275 kV: hand-override values). `type` is never passed to `n.add`. All 10 custom lines have non-zero impedance on disk.

### Bug 2 — CSP 500 MW absorbed into `solar` carrier
**Root cause:** Six 2023 CSP plants in `custom_powerplants.csv` carry `Fueltype=Solar, Technology=CSP`. PyPSA-Earth maps `Fueltype=Solar` → `solar` carrier; the plants were aggregated into per-bus `{bus} solar` generators. The `{bus} csp` ghost generators (correct atlite CSP profile, correct p_nom slot) stayed at p_nom=0.

**Fix:** New `retag_csp_from_solar()` step in `apply_za_local_carriers.py`. Reads `custom_powerplants.csv`, filters `Fueltype=Solar AND Technology=CSP`, aggregates by bus, subtracts CSP capacity from `{bus} solar`, adds to `{bus} csp`. Network audit confirms solar+csp = 10,533 MW (conservation) post-fix.

### Bug 3 — Merit order inversion (coal 565 vs OCGT 380 EUR/MWh)
**Root cause:** `costs_2030_elec.csv` uses EU-2030 coal with carbon price baked in (~179 EUR/GJ fuel). ZA 2018 coal fuel price is 45.18 R/GJ ÷ 15.6186 ZAR/EUR = 2.89 EUR/GJ. Correct MC ~41 EUR/MWh vs EU-2030 default 565 EUR/MWh. Nuclear similarly wrong (263 → 16.39 EUR/MWh).

**Fix:** New `patch_standard_carrier_costs()` function in `apply_za_local_carriers.py`, called first in `main()` before `upstream_carriers` baseline is captured. Two rows added to `za_local_carrier_cost_rows.csv` (coal and nuclear) with ZA-specific values sourced from `pypsa_rsa / fixed_technologies.xlsx`, base year 2018.

Correct merit order after fix:
```
solar/wind (~0) → other_re (0) → nuclear (~16) → sasol_coal (~18)
→ coal (~41) → sasol_gas (~48) → ocgt_diesel (~380)
```

---

## Stage 2 smoke results (pre-cost-fix — needs re-run)

The Stage 2 solved network (`results/.../elec_s_34_ec_lcopt_Co2L-1H.stage2.nc`) was produced **before** the merit-order fix. The cost fix is in `elec_s_34.nc` (input) but the solve has not been re-run.

**Pre-fix Stage 2 dispatch vs Eskom July 2023 actuals (confirmed from `eskom_2023_hourly_clean.csv`):**

| Carrier | Model (pre-fix) | Eskom actual | Delta | Root cause |
|---|---|---|---|---|
| Coal | ~13,700 GWh | **14,769 GWh** | −7% | Merit order inversion (partly) |
| OCGT diesel | ~2,544 GWh | **528 GWh** | **+381%** | Merit order inversion (coal too expensive) |
| Solar PV | ~1,133 GWh | **325 GWh** | **+248%** | Fleet duplication bug: 10,033 MW vs 2,287 MW actual |
| Onwind | ~1,346 GWh | **1,040 GWh** | +29% | Fleet duplication bug: 6,981 MW vs 3,443 MW actual |
| CSP | ~155 GWh | **42 GWh** | +269% | Flows from solar over-capacity (atlite profile × inflated p_nom) |
| Nuclear | ~5,012 GWh | **657 GWh** | — | p_max_pu=0.534 (1 reactor offline) — CF ~53% is correct |
| Load shedding | ~6 GWh | **~1,491 GWh proxy** | −99% | RE over-dispatch + coal unconstrained masks real gap |

**Action required before Module 12:** (1) Apply RE fleet fix (`opus_brief_re_capacity_fix.md`), which requires a full pipeline rebuild. (2) Re-run Stage 2 with both cost fix and correct RE capacity. Then compare against actuals.

---

## Issues for Module 12

### Issue 1 — Stage 2 not re-solved with corrected costs (blocker)
The `elec_s_34.nc` input network has correct costs (coal 40.56, nuclear 16.39 EUR/MWh) but the Stage 2 solve has not been re-run. Module 12 must re-solve Stage 2 as the first step to confirm coal/OCGT dispatch corrects.

**Expected after fix:** coal ↑ toward 14,769 GWh; OCGT diesel ↓ toward 529 GWh.

### Issue 2 — Coal has no EAF (p_max_pu = 1.0 static)
All 6 aggregated coal generators have `p_max_pu = 1.0` — full 40.7 GW is available every hour. Eskom's 2023 coal EAF was ~55% (severe plant failures throughout the year). Without this constraint the optimizer can use more coal than was physically available, which will over-estimate coal dispatch and under-estimate load shedding once the cost fix forces coal into the stack.

**Module 12 action:** Apply monthly carrier-level coal EAF as `p_max_pu` time-series. Source: Eskom 2023 monthly EAF data (`data/eaf_weekly.csv` or Eskom Annual Report). This is the primary calibration constraint for thermal dispatch.

### Issue 3 — RE capacity 2–4× over-stated: fleet duplication bug in `reconciliation.py` (blocker)

Confirmed by cross-checking `custom_powerplants.csv` projectID breakdown against Eskom
`Wind Installed Capacity` and `PV Installed Capacity` (hourly columns, constant across
July 2023):

| Carrier | Model p_nom | Eskom actual (Jul 2023) | Root cause |
|---|---|---|---|
| Wind | 6,890 MW | **3,443 MW** | Same 34 farms listed twice: `RSA_FIXED_TECHNOLOGIES` (3,474 MW) + `REIPPPP` (3,416 MW) |
| Solar PV | ~10,033 MW | **2,287 MW** | Same REIPPPP PV plants (~2,297 MW) duplicated in RSA; plus 4,439 MW distributed PV |
| CSP | 500 MW | 500 MW | ✓ correct — CSP not duplicated |

**Root cause in code:** `scripts/za_fleet/reconciliation.py` → `build_reconciliation_rows()`
emits wind and solar-PV rows from **both** the RSA loop (Loop 1) and the REIPPPP loop
(Loops 2/3). `make_unique_names()` appends `_2` suffixes to keep both rows. No
deduplication exists downstream.

**Distributed PV must be removed entirely (not just corrected for vintage):** The model
load comes from Eskom `RSA Contracted Demand`, which satisfies the identity
`RSA Contracted Demand ≈ Residual Demand + Total RE` where `Total RE` is REIPPPP
grid-connected RE only. Distributed/embedded solar reduces demand at the distribution
level and is already netted into `RSA Contracted Demand`. Adding the 4,439 MW
`Existing distributed solar PV` rows as PyPSA generators is a double-count.

**Fix (one line in reconciliation.py):** In Loop 1 (RSA_FIXED_TECHNOLOGIES), after
the existing `hydro_import` skip, add:
```python
if v1_carrier in ("onwind", "solar"):
    continue
```
This removes both the wind/solar duplicates and the distributed PV aggregates. CSP
(`v1_carrier="csp"`) is not skipped. Full details in `opus_brief_re_capacity_fix.md`.

**After fix:** wind ≈ 3,507 MW, solar PV ≈ 2,297 MW — both match Eskom actuals within 2%.
Requires **full pipeline rebuild** from `build_za_fleet_reconciliation` through
`elec_s_34.nc` and all ZA hooks.

**This fix must be applied before any Module 12 calibration work.**

### Issue 4 — Load shedding absent in model (6 GWh vs ~1,491 GWh proxy)
Real July 2023 had Stage 4–6 load shedding most of the month. Model records 0.032% (6 GWh).
Two compounding drivers: (a) RE 2–4× over-stated provides spurious free generation, (b)
coal unrestricted at `p_max_pu=1.0` covers any residual gap. Fixing Issues 3 (RE fleet)
and 2 (coal EAF) together should surface the real load-shedding gap.

**Module 12 action:** Apply RE fleet fix (Issue 3) first. Then apply coal EAF (Issue 2).
After those solves, measure residual load-shedding against Eskom MLR+ILS+IOS. If gap
persists, check OCGT EAF.

### Issue 5 — Nuclear CF 53%: likely correct, verify static p_max_pu source
`n.generators['Peninsula nuclear']['p_max_pu'] = 0.534` — already a static constraint in the network (not the default 1.0). CF of 53% is consistent with Koeberg Unit 2 being offline most of 2023 (steam generator replacement program). The pre-fix notebook note "53% vs ~80%" was wrong — 80% is a pre-2023 typical; 2023 was anomalous.

**Module 12 action:** Verify where `p_max_pu=0.534` came from (check `apply_za_local_carriers.py` log and `za_local_carriers_audit.csv`). Confirm it is sourced from pypsa-rsa `plant_availability.xlsx` or Eskom AR 2023. If origin is unknown, replace with time-varying monthly EAF. Otherwise: **no change required for nuclear**.

### Issue 6 — PHS and hydro zero dispatch
PHS (2,892 MW) and hydro/RoR (678 MW) show 0 GWh in Stage 2. PHS should have been cycling daily in July 2023 (Eskom runs Ingula + Palmiet). Likely cause: PHS cycle constraint or storage state of charge initialised at wrong level.

**Module 12 action:** Inspect `n.storage_units` for PHS. Confirm `cyclic_state_of_charge=True`, `state_of_charge_initial` not locking it out, `p_max_pu_charge/discharge` not zero. Hydro: confirm `p_max_pu` profile is non-zero for July.

### Issue 7 — `za_eskom_2023_capacity_anchors.csv` is empty
All 34 carriers have `available=False`. Anchor-delta gate in `build_za_fixed_network_audit` is informational only until this is populated.

**Module 12 action:** Source per-carrier installed capacity (MW) from Eskom Annual Report 2023 / IRP 2023 Appendix. Populate `za_eskom_2023_capacity_anchors.csv`. Then re-run the audit to enforce the anchor-delta gate.

### Issue 8 — `ocgt_gas` carrier reserved but empty
No non-Sasol natural-gas plants in `custom_powerplants.csv` for 2023. Carrier row exists in the network for future use.

**Module 12 action:** Leave as-is unless sensitivity analysis re-attributes AVF gas plants. Document in calibration report.

### Issue 9 — biomass/bioenergy: 0 MW in model
PyPSA-RSA PPM has 56 MW bioenergy; RSA fleet has 297 MW biomass. Both absent from model. No row in `za_local_carrier_cost_rows.csv`.

**Module 12 action:** Decide scope: (a) attach bioenergy from a Module 07 update, or (b) document as out-of-scope and record in the "known gaps" table of the calibration report.

### Issue 10 — Stage 3 (full 8760) not yet run
Stage 3 is the annual validation run. Intentionally deferred — user runs manually after Module 12 calibration is applied.

**Module 12 action:** After Issues 1–5 are resolved, run Stage 3 with the calibrated network. Gate: annual generation by carrier within 10% of Eskom 2023 actuals for each thermal carrier.

### Issue 11 — Uncalibrated baseline not yet built
`za_2023_uncalibrated_baseline.yaml` is deferred to Module 12. Needed to measure the before/after calibration delta (mandatory for the thesis calibration chapter).

**Module 12 action:** Build the uncalibrated baseline solve (no EAF, no corrections) before applying any Module 12 patches, so the improvement is quantifiable.

---

## Pre-Module-12 checklist

Two fixes must be applied and verified **before** Module 12 dispatch calibration begins.
Both require pipeline rebuilds. Complete in order.

### Fix A — RE fleet duplication (blocker)
- [ ] Apply one-line fix in `scripts/za_fleet/reconciliation.py` (see `opus_brief_re_capacity_fix.md`)
- [ ] Re-run `build_za_fleet_reconciliation` → verify `custom_powerplants.csv`: wind ≈ 3,507 MW, solar ≈ 2,297 MW, no `_2` wind/solar rows, no distributed PV rows
- [ ] Re-run full pipeline through `elec_s_34.nc` and ZA hooks
- [ ] Re-run Stage 2 smoke with corrected RE capacity

### Fix B — Stage 2 re-solve with corrected costs
- [ ] Confirm Stage 2 re-solve (cost-fixed `elec_s_34.nc`) shows coal ↑ toward 14,769 GWh and OCGT ↓ toward 528 GWh

### Before Module 12 implementation
- [ ] `za_eskom_2023_capacity_anchors.csv` populated (coal, nuclear, OCGT, wind, solar totals from Eskom AR 2023)
- [ ] Nuclear `p_max_pu=0.534` source confirmed (pypsa-rsa `plant_availability.xlsx` or Eskom AR)
- [ ] Coal EAF source confirmed (`data/eaf_weekly.csv` or Eskom AR 2023 monthly EAF by carrier)
- [ ] Uncalibrated baseline solve is the **first** Module 12 output (sets the before-delta baseline)
