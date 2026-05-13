# Codex Task — Module 12 Dispatch Calibration Notebook Refactor

## Context

You are working inside the `pypsa-earth` codebase at:
```
/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth
```

The Module 12 calibration has produced **four solved networks** for the South Africa 2023 fixed-fleet dispatch model. The validation notebook exists but is disorganised: it loops over solves and plots each one separately, making cross-scenario comparison nearly impossible for an external reader.

Your task is to **rewrite the notebook in place** so that it becomes a standalone, externally readable comparison report. Do not add new Snakemake rules, do not modify any Python scripts, do not touch any `.nc` network files or CSV outputs. Edit only the notebook.

---

## File to edit

```
notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb
```

After completing the notebook, execute it in place and export HTML:

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth
jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=600 \
  --inplace \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb

jupyter nbconvert --to html \
  notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb \
  --output dispatch_calibration_validation.html
```

---

## Reference style

Read these official PyPSA-Earth notebooks for plotting conventions and DataFrame display patterns:

```
notebooks/notebooks official/validation/capacity_validation.ipynb
notebooks/notebooks official/make_statistics.ipynb
notebooks/notebooks official/network_analysis.ipynb
```

Key conventions to adopt:
- Use `matplotlib` with explicit `fig, axes` layout, tight `figsize`, `dpi=120`
- Use `pd.DataFrame.style` for all summary tables (format precision, thousands separator, highlight extremes with `background_gradient`)
- Use `plt.rcParams` or a style block at the top for consistent fonts and grid
- Section headers as markdown cells with `##` / `###`, numbered sections
- One code cell per logical unit (load, compute, plot are separate cells)
- Suppress all `FutureWarning` and `DeprecationWarning` at the top

---

## The four solves

| Label | Network file | Short name |
|-------|-------------|------------|
| `structural` | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H.nc` | NoCO2 |
| `eaf_calibrated` | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc` | EAF |
| `eaf_opc` | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC.nc` | EAF-OPC |
| `eaf_opc_cap` | `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | EAF-OPC-CAP |

Eskom 2023 hourly reference: `data/za_validation/eskom_2023_hourly_clean.csv`
Eskom carrier targets: `data/za_validation/eskom_2023_targets_by_carrier.csv`

---

## Notebook structure to implement

### Section 0 — Setup and data loading
- Imports, `warnings.filterwarnings`, `plt.rcParams` block
- Define `ROOT`, paths to all four network files, Eskom CSV
- Define `SOLVE_LABELS = {"structural": "NoCO2", "eaf_calibrated": "EAF", "eaf_opc": "EAF-OPC", "eaf_opc_cap": "EAF-OPC-CAP"}`
- Define carrier colour palette (reuse existing `CARRIER_COLORS` dict)
- Load all four networks; load Eskom hourly CSV; load Eskom targets CSV
- For each network extract a model time series DataFrame with columns = carriers + `load_shedding` (same columns as Eskom hourly, aligned to 2023 index)

### Section 1 — System overview table

**1.1 Annual energy balance table**

One styled `pd.DataFrame` with:
- Rows: carriers (coal, nuclear, ocgt, hydro, phs_generation, phs_pumping, wind, solar_pv, csp, load_shedding, TOTAL)
- Columns: Eskom_GWh | NoCO2_GWh | EAF_GWh | EAF-OPC_GWh | EAF-OPC-CAP_GWh | NoCO2_Δ% | EAF_Δ% | EAF-OPC_Δ% | EAF-OPC-CAP_Δ%
- TOTAL row = sum of all rows (include pumping as positive, include load_shedding)
- Apply `background_gradient(cmap="RdYlGn_r", subset=Δ% columns)` — red = large error, green = small
- Format GWh columns with thousands separator, Δ% columns with one decimal and `%` suffix

**1.2 Grouped bar chart — Annual generation by carrier**

- One figure, grouped bars: x-axis = carriers, groups = 5 (Eskom + 4 solves)
- Each group uses a distinct hatch/colour per solve
- Add value labels on bars (GWh / 1000 → TWh, one decimal)
- Exclude phs_pumping from this chart (consumption, not generation)
- Include load_shedding as its own carrier group

### Section 2 — Carrier-by-carrier deep dive

One subsection per carrier:  
`coal`, `nuclear`, `ocgt`, `hydro`, `phs_generation`, `wind`, `solar_pv`, `csp`, `load_shedding`

For each carrier produce exactly the following (in order):

**2.x.1 Hourly dispatch — July 2023 (peak scarcity window)**

- Single figure with 5 subplots stacked vertically (Eskom, NoCO2, EAF, EAF-OPC, EAF-OPC-CAP)
- Each subplot: line plot of hourly MW dispatch, carrier colour, y-axis labelled "MW"
- Shared x-axis (date labels); figure title: `"[Carrier] — Hourly dispatch July 2023"`

**2.x.2 Monthly energy totals**

- Single figure, line plot
- x-axis = months (Jan–Dec 2023), y-axis = GWh
- 5 lines: Eskom + 4 solves, distinct linestyle/marker per solve
- Legend at top-right

**2.x.3 Diurnal profile (annual average)**

- Single figure, line plot
- x-axis = hour of day (0–23), y-axis = average MW
- 5 lines: Eskom + 4 solves

**2.x.4 Carrier metrics table**

Styled one-row DataFrame:
| Solve | Annual GWh | Δ vs Eskom GWh | Δ% | Pearson r (hourly) | Spearman r (hourly) | Pearson r (weekly) | RMSE MW | MAE MW |
|-------|------------|----------------|----|--------------------|---------------------|---------------------|---------|--------|

Compute Pearson and Spearman r using `scipy.stats.pearsonr` / `spearmanr` on the hourly time series (drop NaN before computing). Weekly Pearson: resample to `"W"`, sum, then correlate.

### Section 3 — Scarcity proxy analysis

Scarcity proxy = `ocgt + load_shedding` (combined signal, both model and Eskom).

**3.1 Weekly scarcity correlation table**

Styled DataFrame — rows = 4 solves, columns = Pearson r (weekly), Spearman r (weekly), Pearson r (monthly), Spearman r (monthly), MAE (GWh/week).

Load from `data/za_validation/za_2023_dispatch_pearson.csv` and `za_2023_dispatch_pearson_monthly.csv` if they exist; otherwise compute inline.

**3.2 Weekly scarcity time series — all 4 solves vs Eskom**

Single figure, 5 lines (weekly GWh each), shared x-axis (week number), legend.

**3.3 Monthly scarcity bar chart**

Grouped bar chart, x-axis = months, groups = Eskom + 4 solves.

### Section 4 — Capacity factor summary

Styled DataFrame:
- Rows: carriers where capacity factor is meaningful (coal, nuclear, ocgt, hydro, wind, solar_pv, csp)
- Columns: Eskom CF | NoCO2 CF | EAF CF | EAF-OPC CF | EAF-OPC-CAP CF
- CF = annual_GWh / (nameplate_MW × 8760)
- Use nameplate capacity from network `n.generators.p_nom` for model CF
- Use Eskom installed capacity from `data/za_audit/za_eskom_2023_capacity_anchors.csv` for Eskom CF

### Section 5 — Load shedding deep dive

**5.1 Hourly load shedding — full year**

Single figure, 5 subplots stacked, hourly MW, shared x-axis.

**5.2 Load shedding seasonality — monthly GWh**

Grouped bar chart, x-axis = months.

**5.3 Stage-proxy histogram**

For each solve: histogram of hourly load-shedding MW (bin width = 500 MW). Overlay Eskom MLR histogram. Title: "Load shedding MW distribution".

**5.4 Duration curve**

Single figure, 5 lines: sorted descending hourly load-shedding MW (load duration curve style), x-axis = hours/year.

### Section 6 — PHS deep dive

PHS is the largest absolute calibration gap (-97% generation in solve 4). Give it its own section.

**6.1 Monthly PHS generation and pumping**

Two-panel figure: top = PHS generation (monthly GWh), bottom = PHS pumping (monthly GWh absolute value). 5 lines each.

**6.2 PHS net energy (generation − pumping) by month**

Bar chart, grouped by solve.

**6.3 PHS round-trip efficiency proxy**

For each solve: `annual_generation_GWh / annual_pumping_GWh`. Styled table. Note: Eskom expected ~0.75–0.80.

### Section 7 — Summary scorecard

One master styled DataFrame — all carriers, all solves — with colour-coded Δ% cells. This is the single-page reference an external reviewer can use to assess calibration status.

Columns: `carrier | eskom_GWh | NoCO2_GWh | EAF_GWh | EAF-OPC_GWh | CAP_GWh | NoCO2_Δ% | EAF_Δ% | OPC_Δ% | CAP_Δ% | CAP_Pearson_r_hourly | CAP_Pearson_r_weekly`

Add a footer row: `TOTAL` = sum of all generation carriers (exclude pumping).

Apply `background_gradient` on all Δ% columns. Bold the CAP columns (they are the current best solve).

---

## Metrics reference

All correlations must drop NaN and use aligned indices. Use `scipy.stats.pearsonr` and `spearmanr`. Weekly = `resample("W").sum()`. Monthly = `resample("ME").sum()`.

RMSE and MAE in MW (not GWh):
```python
rmse = np.sqrt(((model_mw - eskom_mw) ** 2).mean())
mae = (model_mw - eskom_mw).abs().mean()
```

Annual GWh from hourly MW:
```python
annual_gwh = series_mw.sum() / 1e3  # MW·h → GWh (hourly resolution)
```

---

## Constraints

- Edit only `notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation.ipynb`
- Do not overwrite any `.nc` network files
- Do not modify any CSV in `data/`
- Do not modify any Python script in `scripts/`
- Preserve the existing `load_network()` helper (cell 03) — refactor around it
- All matplotlib figures must call `plt.tight_layout()` and `plt.show()` at the end
- Keep cell outputs clean: suppress progress bars, solver output, and debug prints
- If a network file is missing, skip that solve gracefully (print a warning, continue)
- The notebook must execute top-to-bottom without error after your edits

---

## Acceptance gates

- [ ] Notebook executes without errors (`jupyter nbconvert --execute` exits 0)
- [ ] HTML export written to same directory as notebook
- [ ] Section 1 annual table present with all 4 solves + Eskom + Δ% columns
- [ ] Section 2 has one subsection per carrier (9 carriers)
- [ ] Each carrier subsection has: July hourly, monthly, diurnal, metrics table
- [ ] Section 3 scarcity proxy table present with weekly + monthly Pearson/Spearman
- [ ] Section 5 load shedding has duration curve
- [ ] Section 6 PHS has round-trip efficiency proxy table
- [ ] Section 7 master scorecard present
- [ ] No cell contains raw loop output dumped as text — all outputs are styled DataFrames or matplotlib figures

---

## Do not implement

- No new Snakemake rules
- No changes to `scripts/`
- No network re-solves
- No modifications to `data/` CSVs
- No grid map / Folium / Cartopy cells (keep existing map cells as-is if they work; do not add new ones)
