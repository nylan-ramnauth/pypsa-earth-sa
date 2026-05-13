# Module 13b — Stock Baseline Comparison: Opus Implementation Prompt

## Purpose

This prompt instructs an agent to implement Module 13b: a clean stock-vs-calibrated
comparison that shows what PyPSA-Earth produces for South Africa out of the box,
versus what the fully calibrated Module 12 model produces.

This is **not a correction to Module 13**. Module 13 is correct and complete. Module
13b adds one new solve (`STOCK`) and one new comparison panel (§6b) to the validation
evidence package.

---

## Repo location

All work is in the PyPSA-Earth repository:

```
6-codebases/repos/pypsa-earth/
```

All paths below are relative to that root unless stated otherwise.

---

## Background: what the current before/after shows vs what we need

**Current §6 in `doc/za_2023_validation_report.md`:**
Compares `elec_s_34_ec_lc1_NoCO2-1H.nc` (Module 10 structural baseline — already has
the full ZA fleet, ZA costs, Eskom demand, custom busmap, transmission calibration)
against `elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` (accepted Module 12 solve).
This shows only what EAF+OPC+CAP add over an already well-calibrated fleet.

**What Module 13b adds (§6b):**
Compares a genuine `STOCK` solve (PPM fleet, EUR costs, no dispatch calibration, but
same demand and same regional structure) against the accepted Module 12 solve. This
shows the total value of Modules 01–12 calibration work.

---

## Stock baseline: exact definition

### What is IDENTICAL to the calibrated model

| Component | Kept |
|---|---|
| 34-region busmap (`data/custom_busmap_elec_s_34.csv`) | YES — same regional structure |
| Eskom 2023 hourly demand + regional allocation | YES — `weather_year: 2023_custom` |
| Exogenous imports/exports timeseries | YES — same IE |
| 2023 ERA5 cutout (`cutout-2023-era5.nc`) | YES — same weather year |
| `scenario.clusters: [34]`, `ll: ["c1"]`, `opts: ["NoCO2-1H"]` | YES — same resolution and solve mode |
| No CO₂ cap, no expansion, same Gurobi solver | YES |
| 220 kV line voltage floor (same set of OSM lines included) | YES |

### What is STOCK (not calibrated)

| Component | Stock baseline uses |
|---|---|
| Fleet | PowerplantMatching (PPM) — `electricity.custom_powerplants: false` |
| Costs | EUR upstream defaults — `costs.output_currency: EUR`, `electricity_grid_connection` default |
| Local carriers | Standard PyPSA-Earth carriers only (`OCGT`, not `ocgt_diesel`/`ocgt_gas`) |
| CSP topology | NOT fixed — `za_fix_csp_links_stores` NOT applied; CSP may dispatch incorrectly or at zero. **This is accepted.** |
| Coal availability | Flat 100 % `p_max_pu` — no EAF overlay |
| OCGT constraints | None — no OPC weekly cap, no annual CAP |
| Custom missing transmission lines | NOT injected — `apply_za_custom_lines` NOT applied |
| PHS storage hours | PyPSA-Earth default (6 h) |
| Hydro multiplier | PyPSA-Earth default (1.1) |

### What this comparison shows

The delta between §6b STOCK and §6 (Module 10) isolates dispatch calibration alone
(EAF+OPC+CAP). The delta between §6b STOCK and the accepted CAP solve shows the full
calibration contribution (fleet + costs + transmission + dispatch). This is the
thesis-relevant figure.

---

## Implementation tasks

### Task 1 — New config overlay

Create `configs/za/za_2023_stock_baseline.yaml`.

This file must:
- Set `run.name: "za_2023_stock_baseline"` so all intermediate and result files land
  in a separate directory and never overwrite the calibrated run.
- Set `za_stock_baseline: true` (new top-level flag used to gate marker functions in
  Task 2).
- Override `electricity.custom_powerplants: false`.
- Override `costs.output_currency: EUR`.
- Remove or omit `costs.electricity_grid_connection` (revert to upstream default).
- Remove or set `za.operational_constraints.enable: false`.
- Keep all topology/demand keys identical to `configs/za/za_2023_fixed_validation.yaml`:
  - `countries: ["ZA"]`
  - `enable.custom_busmap: true`
  - `enable.retrieve_cutout: false`
  - `scenario.clusters: [34]`, `ll: ["c1"]`, `opts: ["NoCO2-1H"]`
  - `snapshots.start/end: 2023/2024`
  - `atlite.default: cutout-2023-era5` and the cutout definition block
  - `load_options.weather_year: 2023_custom`
  - `za_grid_spatial` config block (needed if `build_za_grid_spatial` is referenced,
    even if not re-run)
  - `run.shared_cutouts: true`
  - `electricity.extendable_carriers: all empty`
  - `electricity.co2limit: null`
  - `solving` block (same Gurobi settings)
- Omit `za_cols_policy`, `za_local_carriers`, `za_system_boundary`, and other
  ZA-specific top-level keys that are only relevant to the calibrated pipeline.
- Keep `pypsa_rsa_root` and `pypsa_rsa_pinned_commit` because some audit rules
  reference them (even if not re-run for the stock baseline).

### Task 2 — Gate marker functions in Snakefile

The three marker functions in `Snakefile` force ZA mutation rules to run before their
consuming rules. For the stock baseline they must return `[]` (no dependency).

Modify each function to check `config.get("za_stock_baseline", False)`:

```python
def _za_custom_lines_marker(wildcards):
    if config.get("za_stock_baseline", False):
        return []
    if wildcards.simpl == "" and wildcards.clusters == "34":
        return ["networks/" + RDIR + "elec_s_34.pre_custom.nc"]
    return []


def _za_local_carriers_marker(wildcards):
    if config.get("za_stock_baseline", False):
        return []
    if wildcards.simpl == "" and wildcards.clusters == "34":
        return ["networks/" + RDIR + "elec_s_34.pre_local.nc"]
    return []


def _za_csp_fix_marker(wildcards):
    if config.get("za_stock_baseline", False):
        return []
    if wildcards.simpl == "" and wildcards.clusters == "34":
        return ["networks/" + RDIR + "elec_s_34_ec.pre_csp.nc"]
    return []
```

This means the stock baseline run will flow through the standard pipeline
(`cluster_network` → `add_extra_components` → `prepare_network` → `solve_network`)
without any of the ZA mutation rules triggering.

### Task 3 — Share base network to avoid OSM re-download

The `za_2023_stock_baseline` run needs early pipeline files (`base.nc`,
`elec_s.nc`, resources such as shapes and OSM clean data). Downloading OSM data
again is unnecessary since the same ZA country selection produces the same result.

Add a Snakemake rule `share_za_base_network` that copies or symlinks the early
pipeline artefacts from the calibrated run into the stock baseline run directory:

```
networks/za_2023_stock_baseline/base.nc
  ← networks/za_2023_fixed_validation/base.nc

networks/za_2023_stock_baseline/elec_s.nc
  ← networks/za_2023_fixed_validation/elec_s.nc

resources/za_2023_stock_baseline/
  ← copy (or symlink) relevant subdirs from resources/za_2023_fixed_validation/
    that cluster_network and add_electricity need (shapes, renewable profiles, etc.)
```

If symlinking is cleaner, create the target directory and symlink the whole
`resources/za_2023_fixed_validation/` subtree entries that are needed. If copying
is simpler, copy only the files that `cluster_network`, `add_electricity`, and
`add_extra_components` declare as inputs.

The goal: `snakemake --configfile configs/za/za_2023_stock_baseline.yaml
elec_s_34_ec_lc1_NoCO2-1H.nc` should proceed directly to `cluster_network`
without re-downloading or re-running `base_network` or `simplify_network`.

Make `share_za_base_network` a prerequisite of `cluster_network` when
`za_stock_baseline: true`. Gate it the same way as the marker functions.

### Task 4 — Add `solve_network_stock_baseline` Snakemake rule

Add a dedicated rule so the stock baseline solve is explicitly named and does not
conflict with the calibrated run's `solve_network`:

```python
rule solve_network_stock_baseline:
    """Stock PyPSA-Earth ZA baseline: PPM fleet, EUR costs, no dispatch calibration.
    Same demand (Eskom 2023) and same 34-region busmap as the calibrated run.
    Used for Module 13b stock-vs-calibrated comparison.
    """
    params:
        solving=config["solving"],
        augmented_line_connection=config["augmented_line_connection"],
        policy_config=config["policy_config"],
    input:
        network="networks/" + RDIR + "elec_s_34_ec_lc1_NoCO2-1H.nc",
        agg_p_nom_minmax=config["electricity"]["agg_p_nom_limits"]["file"],
    output:
        "results/" + RDIR + "networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc",
    log:
        solver="logs/" + RDIR + "solve_network/stock_solver.log",
        python="logs/" + RDIR + "solve_network/stock_python.log",
    benchmark:
        "benchmarks/" + RDIR + "solve_network/stock"
    threads: 20
    resources:
        mem=memory,
    shadow:
        "copy-minimal" if os.name == "nt" else "shallow"
    script:
        "scripts/solve_network.py"
```

The output file is named `NoCO2-1H-STOCK.nc` to distinguish it clearly.
It is written to `results/za_2023_stock_baseline/networks/`.

Add to the ruleorder block:

```python
ruleorder: solve_network_stock_baseline > solve_network
```

(when `za_stock_baseline: true` is set this rule is the only one that fires anyway,
but the ruleorder prevents wildcard ambiguity.)

### Task 5 — Update `scripts/za_validation/build_module13_validation.py`

**5a. Add STOCK network constant:**

```python
STOCK_NETWORK = (
    REPO_ROOT
    / "results/za_2023_stock_baseline/networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc"
)
```

**5b. Add builder function `build_stock_vs_calibrated`:**

This function has the same structure as the existing `build_uncalibrated_vs_calibrated`
(which compares Module 10 vs CAP) but uses `n_stock` (the PPM baseline) instead of
`n_base` (the Module 10 baseline):

```python
def build_stock_vs_calibrated(
    n_stock: pypsa.Network,
    n_cap: pypsa.Network,
    eskom_h: pd.DataFrame,
) -> pd.DataFrame:
    """Stock PyPSA-Earth ZA (PPM fleet, EUR costs, no EAF/OPC/CAP)
    vs accepted Module 12 calibrated solve (EAF-OPC-CAP).

    Rows: per-carrier generation GWh, capacity MW, annual demand TWh,
    load-shedding TWh, hourly RMSE total dispatch, monthly dispatch R².
    Columns: stock_value, calibrated_value, unit, delta_pct.
    """
```

Implement using the same helper functions already in the script
(`carrier_dispatch_hourly`, `model_p_nom_by_carrier`, etc.).

**5c. Add to `main()`:**

Load `n_stock` with a guard — if `STOCK_NETWORK` does not exist, skip the stock
comparison and print a warning rather than failing:

```python
if STOCK_NETWORK.exists():
    print(f"Loading stock baseline network: {STOCK_NETWORK.name}")
    n_stock = pypsa.Network(str(STOCK_NETWORK))
    artifacts["za_2023_stock_vs_calibrated.csv"] = build_stock_vs_calibrated(
        n_stock, n_cap, eskom_h
    )
else:
    print(f"WARNING: {STOCK_NETWORK} not found — skipping stock comparison.")
```

This keeps the existing script idempotent for the current 10-artifact run and
adds the 11th artifact when the stock solve is available.

**5d. Update the manifest** to include `za_2023_stock_vs_calibrated.csv` when
produced.

### Task 6 — Update `doc/za_2023_validation_report.md`

Add section `## 6b. Stock baseline vs calibrated (Module 13b)` immediately after
the existing `## 6. Before/after comparison` section. Do **not** modify §6.

Content of §6b:

1. **One-paragraph framing** explaining the two comparisons:
   - §6 shows what dispatch calibration (EAF+OPC+CAP) adds over an already
     well-calibrated fleet (Module 10 baseline).
   - §6b shows what the full calibration stack (fleet + costs + dispatch calibration)
     adds over a stock PyPSA-Earth baseline with the same demand and regional structure.

2. **Stock baseline definition table** (inline, compact):
   same format as the toggle map rows in `model_data_sources.md` — what is shared,
   what is stock. One row per toggled component.

3. **Key delta table** (stock vs calibrated) for the following metrics:
   - Per-carrier annual GWh (coal, nuclear, OCGT, onwind, solar, CSP, hydro, PHS, load shedding)
   - National annual demand TWh (should be identical — validation check)
   - Total hourly RMSE vs Eskom (MW)
   - Monthly dispatch R²

   Source: `data/za_validation/za_2023_stock_vs_calibrated.csv`.
   Note clearly: "Numerical values will be populated when the stock baseline solve
   completes." if the CSV is not yet available. Leave placeholder rows.

4. **Limitations note**: Stock baseline CSP may dispatch incorrectly (topology unfixed);
   PHS uses default 6 h storage duration; hydro multiplier is 1.1 not 1.20. These are
   accepted as part of the "stock pypsa-earth" definition.

5. **Wikilink cross-references**:
   - `[[za_model_limitations]]`
   - `[[active/calibration-plan/model_data_sources]]` (toggle map for the stock baseline)

### Task 7 — Update provenance and implementation log

**`doc/za_data_provenance.md`**: Add a brief entry noting the stock baseline solve
as a new artifact with its source (PPM fleet, EUR costs, za_2023_stock_baseline run).

**`doc/za_implementation_log.md`**: Append a Module 13b entry with:
- What changed
- Inputs consumed (list)
- Outputs produced (list)
- Gate outcomes (see acceptance gates below)
- Any deviations from this spec

---

## Acceptance gates

| Gate | Criterion |
|---|---|
| Stock solve completes | `results/za_2023_stock_baseline/networks/elec_s_34_ec_lc1_NoCO2-1H-STOCK.nc` exists and is a valid PyPSA network (no infeasibility error) |
| Stock solve uses PPM fleet | `n_stock.generators` contains no generators with names matching `custom_powerplants.csv` station names; PPM-derived generators present |
| Demand is Eskom-anchored | `n_stock.loads_t.p_set.sum().sum() / 1e6` is within 1 % of calibrated model's annual demand (they share the same demand profile) |
| Comparison CSV produced | `data/za_validation/za_2023_stock_vs_calibrated.csv` exists with ≥ 20 rows covering all carriers |
| §6b added to report | `doc/za_2023_validation_report.md` contains `## 6b` section with framing paragraph, definition table, and delta table |
| Implementation log updated | Module 13b entry in `doc/za_implementation_log.md` |
| Module 13 untouched | All 10 existing `data/za_validation/za_2023_validation_*.csv` files unchanged; `doc/za_2023_validation_report.md` §1–§6 and §7–§12 unchanged |
| No new acceptance failure | The STOCK solve being far from Eskom 2023 is **expected and not a gate failure**. The gate is solve completion, not dispatch accuracy. |

---

## What NOT to do

- Do **not** modify any existing Module 13 CSV artifacts.
- Do **not** modify §1–§6 or §7–§12 of `doc/za_2023_validation_report.md`.
- Do **not** modify `doc/za_model_limitations.md`.
- Do **not** re-run `build_za_grid_spatial`, `build_za_source_audits`, or
  `build_za_eskom_validation_data`. Their outputs already exist in `data/za_audit/`
  and are shared across runs.
- Do **not** re-run the calibrated solve chain (NoCO2-1H, EAF, EAF-OPC, EAF-OPC-CAP).
- Do **not** apply `apply_za_coal_eaf`, `apply_za_local_carriers`,
  `za_fix_csp_links_stores`, or `apply_za_custom_lines` to the stock baseline network.
  The `za_stock_baseline: true` flag in Task 2 gates all of these out automatically.
- Do **not** treat CSP dispatching at zero or incorrectly as a bug to fix. It is an
  accepted limitation of the stock baseline by design.
- Do **not** set `za_stock_baseline: true` in `configs/za/za_2023_fixed_validation.yaml`.
  That flag lives only in the stock baseline config.

---

## Key file paths summary

| File | Action |
|---|---|
| `configs/za/za_2023_stock_baseline.yaml` | CREATE |
| `Snakefile` (marker functions L1148–L1169) | MODIFY (add `za_stock_baseline` gate) |
| `Snakefile` (new `share_za_base_network` rule) | ADD |
| `Snakefile` (new `solve_network_stock_baseline` rule) | ADD |
| `Snakefile` (ruleorder block) | MODIFY (add stock baseline rule) |
| `scripts/za_validation/build_module13_validation.py` | MODIFY (add STOCK_NETWORK constant, builder, main guard) |
| `doc/za_2023_validation_report.md` | MODIFY (add §6b after §6) |
| `doc/za_data_provenance.md` | MODIFY (append stock baseline entry) |
| `doc/za_implementation_log.md` | MODIFY (append Module 13b entry) |

---

## Notes for implementation

- The stock solve will likely produce very different dispatch from Eskom 2023 because
  PPM misses ~13 GW of RE and may mis-attribute coal capacity. Large load shedding or
  extreme coal over-dispatch in the stock solve is **expected**. Do not interpret it as
  a bug.
- The demand identity check (acceptance gate row 3) is the key verification that the
  stock and calibrated models share the same demand — if they don't, something is wrong
  with the demand injection for the stock run.
- If the `share_za_base_network` rule is complex to implement cleanly, a simpler
  alternative is to hardcode a Snakemake `ancient()` wrapper around the base network
  path, telling Snakemake to treat it as always up-to-date: this avoids the copy/symlink
  logic entirely.
- The `solve_network_stock_baseline` rule uses the same `scripts/solve_network.py` as
  all other solves — no new solve script is needed.
- If `n_stock` has no `load shedding` generator (PPM fleet may not include it),
  `build_stock_vs_calibrated` must handle the missing carrier gracefully (return 0 GWh,
  not crash).
