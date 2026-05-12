# Module 12 Implementation Review Findings

**Date:** 2026-05-12  
**Reviewer:** Codex  
**Scope:** Review of the Module 12 structural baseline implementation and validation notebook after GPT-5.5 High implementation. No files were edited during the review.

## Summary

The Module 12 implementation has several correct structural changes, but the current solved network should not be accepted as the fixed-grid calibration baseline.

Accepted directionally:

- Sasol rows are removed upstream before `custom_powerplants.csv` generation.
- `other_re` is removed from the active local-carrier hook.
- The canonical target is moved away from `Co2L` to `NoCO2-1H`.
- PHS `Duration = StorageCapacity_MWh / Capacity` is written into the custom fleet path.
- Hydro/PHS validation reads StorageUnit dispatch through `storage_units_t.p`.

Blocking issues remain before EAF calibration should proceed.

## Findings

### 1. Transmission expansion is active in the structural baseline

`configs/za/za_2023_fixed_validation.yaml` uses:

```yaml
scenario:
  ll: ["copt"]
```

In `scripts/prepare_network.py`, `ll == copt` is parsed as `ll_type = "c"`, `factor = "opt"`, which sets:

```python
n.lines["s_nom_extendable"] = True
```

Direct inspection of `results/za_2023_fixed_validation/networks/elec_s_34_ec_lcopt_NoCO2-1H.nc` showed:

- `82 / 82` lines are extendable.
- Total optimized line expansion is about `+220.4 MW`.
- The dominant expansion is `ZA_custom_Nigel_Welkom_275kV`, about `+219.2 MW`.

This is not acceptable for a real-grid fixed calibration baseline. The baseline should calibrate dispatch against the existing 2023 grid, not optimize new grid capacity.

Required correction:

- Use a fixed-grid target such as `lc1` or the project-approved non-expansion equivalent.
- Rerun prepare/solve with a fixed-grid `NoCO2` label.
- Treat any line expansion as a failing validation check.

### 2. Other expandable capacity remains in the solved network

The notebook checks only non-extendable generators. It does not check lines, links, stores, or storage units.

Direct inspection of the solved network showed:

- Generators: no extendable generators.
- StorageUnits: no extendable storage units.
- Lines: `82` extendable.
- Links: `34` extendable CSP links.
- Stores: `34` extendable CSP stores.

This violates the “no unintended extendable capacity” acceptance gate. The validation notebook should fail if any of these components are extendable:

- `Generator.p_nom_extendable`
- `StorageUnit.p_nom_extendable`
- `Store.e_nom_extendable`
- `Link.p_nom_extendable`
- `Line.s_nom_extendable`

### 3. CSP dispatch remains badly wrong

The Module 12 before/after CSV reports:

| Window | Metric | Model | Eskom | Gap |
|---|---:|---:|---:|---:|
| Annual | CSP generation | `14.6 GWh` | `1375.3 GWh` | `-98.9%` |
| July | CSP generation | `1.1 GWh` | `41.7 GWh` | `-97.3%` |

The retagging step appears to put the `500 MW` CSP capacity onto the CSP generators, but the CSP dispatch is still near zero. The solved network also has extendable CSP `Link` and `Store` components with tiny optimized capacity, so the CSP representation is not yet a credible fixed 2023 fleet representation.

Required correction:

- Diagnose the CSP generator/link/store representation after `retag_csp_from_solar`.
- Ensure the fixed 500 MW CSP fleet can dispatch against the intended 2023 CSP profile/storage model.
- Do not accept a calibrated baseline while CSP is near zero.

### 4. EAF provenance is incomplete, not blocked

GPT-5.5 High correctly noted that `data/za_validation/eskom_2023_hourly_clean.csv` only contains system-wide `Total PCLF`, `Total UCLF`, `Total OCLF`, and `Total UCLF+OCLF` fields. Those fields are not defensible as coal-station or coal-carrier EAF by themselves.

However, `pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx` does contain station/week outage information:

- Sheet `annual_availability`: annual EAF rows by scenario and station.
- Sheet `outage_profiles`: weekly planned and unplanned outage profiles by station.
- Coal station columns include `Arnot`, `Camden`, `Duvha`, `Grootvlei`, `Hendrina`, `Kendal`, `Komati`, `Kriel`, `Kusile`, `Lethabo`, `Majuba`, `Matimba`, `Matla`, `Medupi`, and `Tutuka`.
- The `BASE` profile has weekly station availability averaging about `0.6506`, with meaningful station/week variation.

`operational_constraints.xlsx` appears less useful for coal EAF calibration; it mainly contains scenario constraints/reserves and Sasol-related operational constraints.

Required correction:

- Inspect `plant_availability.xlsx` before declaring EAF provenance blocked.
- Decide whether to use:
  - station-level weekly availability directly, or
  - station-level weekly availability aggregated to monthly carrier-level coal `p_max_pu`.
- Document the source, sheet names, fields, transformation, and station mapping to PyPSA-Earth generators.

### 5. PHS pumping comparison has a sign bug

The notebook converts model PHS charging to positive consumption:

```python
return (-p.clip(upper=0))
```

But it compares this to Eskom `Pumped Water SCO Pumping`, which is negative in the cleaned hourly CSV. As a result, the output compares positive model pumping to negative Eskom pumping. The annual table shows:

- Model PHS pumping: `+482.4 GWh`
- Eskom PHS pumping: `-5657.9 GWh`

That delta is not meaningful.

Required correction:

- Convert Eskom pumping to positive consumption before comparison, or convert both sides to the same signed convention.
- Label the convention explicitly in the notebook output.

### 6. The notebook file is not saved as executed

`notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb` has:

- `execution_count: null`
- no saved cell outputs

The HTML export exists, but the notebook artifact itself is not an executed notebook. For a validation artifact, the notebook should either be saved executed or the handoff should explicitly state that only the HTML export is the executed artifact.

### 7. Carrier taxonomy documentation is stale

`data/za_audit/za_carrier_taxonomy.csv` reflects the new Module 12 carrier set, but `doc/za_carrier_taxonomy.md` still lists:

- `sasol_coal`
- `sasol_gas`
- `other_re`

as active V1 carriers. This conflicts with the Module 12 implementation and should be updated or clearly marked as superseded.

## Recommendation

Do not proceed to the EAF-calibrated solve until the structural baseline is corrected.

Minimum next plan:

1. Convert the Module 12 structural solve to a fixed-grid, non-CO2 target.
2. Add validation gates for all extendable component classes.
3. Fix or explain the CSP representation so 2023 CSP dispatch is credible.
4. Fix the PHS pumping sign convention in the notebook.
5. Inspect `plant_availability.xlsx` and decide the EAF source transformation before applying coal `p_max_pu`.
6. Rerun the structural baseline and validation notebook.
7. Only then run the EAF-calibrated solve.

---

## Follow-up — 2026-05-13

| # | Finding | Status | Resolution |
|---|---|---|---|
| 1 | Convert structural solve to fixed-grid target | **Done** | `configs/za/za_2023_fixed_validation.yaml:58` set `ll: ["c1"]`; filename derives to `elec_s_34_ec_lc1_NoCO2-1H.nc`. Verified via `snakemake --dry-run` that `lc1` resolves through `prepare_network`. |
| 2 | Add validation gates for all extendable component classes | **Done** | Notebook cell `module12-09` extended with `no_extendable_storage_units`, `no_extendable_stores`, `no_extendable_links`, `no_extendable_lines`. `scripts/build_za_fixed_network_audit.py` now writes `za_fixed_network_extendable_audit.csv` with per-class extendable counts and fails the gate when any are non-zero. |
| 3 | Fix CSP representation | **Done** | New `scripts/za_fleet/fix_csp_links_stores.py` post-processes the network after `add_extra_components` to set fixed `Link.p_nom` (bus-level CSP nameplate) and `Store.e_nom` (`p_nom × weighted storage hours` from `za_named_plant_inventory.csv`), and flips both to non-extendable. Wired via new Snakefile rule `za_fix_csp_links_stores` and `_za_csp_fix_marker` injected into `prepare_network` input. |
| 4 | Fix PHS pumping sign | **Done** | Notebook `storage_dispatch(..., mode="pumping")` returns positive consumption (`-p.clip(upper=0)`); Eskom Pumped Water SCO Pumping is forced through `.abs()` for the comparison. |
| 5 | Inspect `plant_availability.xlsx` and decide EAF source | **Done — provenance only** | `doc/active/calibration-plan/12_availability_provenance.md` documents the workbook path, sheet structure, BASE formula, station list, and the station-weekly → bus-coal mapping plan. No EAF solve attempted yet. |
| 6 | Rerun structural baseline and validation notebook | **Gated on verification suite** (see `12_dispatch_calibration_and_availability.md` pre-solve fixes section). |
| 7 | Run EAF-calibrated solve | **Deferred** until structural `lc1` baseline passes all gates. |

