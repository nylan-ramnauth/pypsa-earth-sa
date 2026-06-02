# Rerun ZA 2023 Baseline Scenarios

This manual rebuilds the ZA 2023 network and solves three config-defined
scenario networks from terminal. Snakemake writes neutral solved-network files.
The validation notebook owns presentation labels and comparisons.

Run every command from the `pypsa-earth` repo root.

Recommended order:

1. Run the normal packaged-input workflow first with the tracked clean config.
2. Confirm the three solved-network objective values.
3. Only then run the optional input-regeneration acceptance pass in Section 7.

## 1. Prerequisites

Clone the repo and enter it.

```bash
git clone <pypsa-earth-sa-remote-url> pypsa-earth
cd pypsa-earth
```

Create or activate a PyPSA-Earth environment with Snakemake and Gurobi.

```bash
conda env create -f envs/za_environment.yaml
conda activate pypsa-earth-za
snakemake --version
python -c "import gurobipy as gp; print(gp.gurobi.version())"
gurobi_cl --version
```

Use the tracked clean baseline config as the base config. Do not hand-edit it
for the three scenarios.

```bash
git restore configs/za/za_2023_fixed_validation.yaml
```

That restore command is safe only when the clean baseline config is committed,
or at least staged in the local index. If it is not, commit or stage the clean
baseline before running.

Confirm the packaged ZA reference inputs exist. These files must be tracked in a
fresh clone, or generated before the workflow runs.

```bash
test -f data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/operational_constraints.xlsx
test -f data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/plant_availability.xlsx
test -f data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/fixed_technologies.xlsx
test -f data/za_reference/pypsa_rsa_benchmark_2023/sub_scenarios/fuel_prices.xlsx
test -f data/za_reference/pypsa_rsa_coal_flexibilisation/sub_scenarios/plant_availability.xlsx
test -f data/za_reference/supply_regions/rsa_supply_regions.gpkg
test -f data/za_audit/za_rsa_existing_lines_220kv_plus.geojson
test -f data/za_audit/za_rsa_planned_tdp_lines.geojson
test -f data/za_audit/za_rsa_supply_regions.geojson
```

Normal reruns consume tracked ZA input files directly, including
`data/custom_powerplants.csv`, `data/custom_busmap_elec_s_34.csv`,
`data/za_audit/za_custom_missing_lines.csv`, and the coal EAF CSVs under
`data/za_validation/`. If those packaged inputs need to be regenerated from
source, use the optional regeneration command in Section 7 after the data
bundle and cutout are available.

The scenario overlays are:

```text
configs/za/scenarios/za_2023_coal485_nuclear50_no_vre_no_ocgt_cap.yaml
configs/za/scenarios/za_2023_coal485_nuclear50_vre_only.yaml
configs/za/scenarios/za_2023_coal485_nuclear50_vre_ocgt_cap.yaml
```

## 2. Common Build Commands

Retrieve the normal PyPSA-Earth data bundle.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 retrieve_databundle_light
```

The tracked config expects an existing 2023 ERA5 cutout.

```bash
test -f cutouts/cutout-2023-era5.nc
```

If the cutout is missing and a packaged cutout is available, temporarily edit
only the cutout flags in `configs/za/za_2023_fixed_validation.yaml`:

```yaml
enable:
  retrieve_cutout: true
  build_cutout: false
```

Then run:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 cutouts/cutout-2023-era5.nc
```

If the cutout must be rebuilt from ERA5 instead, use working CDS credentials and
temporarily edit:

```yaml
enable:
  retrieve_cutout: false
  build_cutout: true
```

Then run the same cutout target. After retrieval or build, restore the clean
baseline config.

```bash
git restore configs/za/za_2023_fixed_validation.yaml
```

Build the base network.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 networks/za_2023_fixed_validation/base.nc
```

Build the prepared fixed ZA 2023 network. This consumes packaged fleet,
cost, demand/import/export, custom busmap, and custom-line inputs, then applies
the active ZA network hooks.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.nc
```

Build the coal EAF/UC input network.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

The scenario solve targets below are full-DAG targets. On a fresh clone they can
recreate the upstream network chain automatically; the commands above are useful
checkpoints.

`--rerun-incomplete` is optional recovery after an interrupted run. It is not
part of the normal commands in this manual.

## 3. Scenario A: Coal 48.5 + Nuclear 50, No VRE, No OCGT Cap

Overlay config:

```text
configs/za/scenarios/za_2023_coal485_nuclear50_no_vre_no_ocgt_cap.yaml
```

Effective settings:

```yaml
# baseline-owned source-network setting
za_coal_disaggregation.annual_availability_target_override.coal: 0.485

# scenario overlay settings
za_operational_constraints.enable: true
za_operational_constraints.scenario: LOW_GAS
za_availability_overrides.static_p_max_pu.carriers.nuclear: 0.5
za_profile_scaling.enable: false
za_generation_constraints.annual_generation_caps.carriers.nuclear: 8.127
```

Run:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml configs/za/scenarios/za_2023_coal485_nuclear50_no_vre_no_ocgt_cap.yaml --cores 4 results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_no_vre_no_ocgt_cap.nc
```

Expected solved network:

```text
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_no_vre_no_ocgt_cap.nc
```

Expected objective:

```text
30326143568.65032
```

## 4. Scenario B: VRE Only

Overlay config:

```text
configs/za/scenarios/za_2023_coal485_nuclear50_vre_only.yaml
```

Effective settings:

```yaml
# baseline-owned source-network setting
za_coal_disaggregation.annual_availability_target_override.coal: 0.485

# scenario overlay settings
za_operational_constraints.enable: true
za_operational_constraints.scenario: LOW_GAS
za_availability_overrides.static_p_max_pu.carriers.nuclear: 0.5
za_profile_scaling.enable: true
za_profile_scaling.carriers.onwind: 1.58
za_profile_scaling.carriers.solar: 1.40
za_generation_constraints.annual_generation_caps.carriers.nuclear: 8.127
```

Run:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml configs/za/scenarios/za_2023_coal485_nuclear50_vre_only.yaml --cores 4 results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_only.nc
```

Expected solved network:

```text
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_only.nc
```

Expected objective:

```text
25449233841.801006
```

## 5. Scenario C: VRE + OCGT Cap

Overlay config:

```text
configs/za/scenarios/za_2023_coal485_nuclear50_vre_ocgt_cap.yaml
```

Effective settings:

```yaml
# baseline-owned source-network setting
za_coal_disaggregation.annual_availability_target_override.coal: 0.485

# scenario overlay settings
za_operational_constraints.enable: true
za_operational_constraints.scenario: LOW_GAS
za_availability_overrides.static_p_max_pu.carriers.nuclear: 0.5
za_profile_scaling.enable: true
za_profile_scaling.carriers.onwind: 1.58
za_profile_scaling.carriers.solar: 1.40
za_generation_constraints.annual_generation_caps.carriers.nuclear: 8.127
za_generation_constraints.annual_generation_caps.carriers.ocgt_diesel: 5.243
```

Run:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml configs/za/scenarios/za_2023_coal485_nuclear50_vre_ocgt_cap.yaml --cores 4 results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_ocgt_cap.nc
```

Expected solved network:

```text
results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_ocgt_cap.nc
```

Expected objective:

```text
31212007124.84154
```

## 6. Objective Check

After the three scenario solves finish, confirm the objectives from the solved
network files.

```bash
python - <<'PY'
import math
import pypsa

expected = {
    "coal485_nuclear50_no_vre_no_ocgt_cap": (
        "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_no_vre_no_ocgt_cap.nc",
        30326143568.65032,
    ),
    "coal485_nuclear50_vre_only": (
        "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_only.nc",
        25449233841.801006,
    ),
    "coal485_nuclear50_vre_ocgt_cap": (
        "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-CONFIG-coal485_nuclear50_vre_ocgt_cap.nc",
        31212007124.84154,
    ),
}

for label, (path, target) in expected.items():
    value = float(pypsa.Network(path).objective)
    print(f"{label}: {value:.12f}")
    if not math.isclose(value, target, rel_tol=0, abs_tol=1e-5):
        raise SystemExit(f"{label} objective changed: {value} != {target}")
PY
```

## 7. Optional Input-Regeneration Acceptance Pass

Skip this section for a normal rerun. Use it only to prove that the packaged ZA
inputs can be regenerated and still reproduce the same three solved networks.
The target rewrites tracked input/audit files, so start from a committed or
staged clean baseline state.

Temporarily set:

```yaml
enable:
  za_input_data_regeneration: true
```

Run the single regeneration target.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 prepare_za_input_data
```

Restore the clean baseline config before solving scenarios.

```bash
git restore configs/za/za_2023_fixed_validation.yaml
```

Rebuild the EAF source network and rerun the three scenario commands from
Sections 3-5.

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml --cores 4 networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc
```

Run the objective check in Section 6 again. The objective values must remain:

```text
30326143568.65032
25449233841.801006
31212007124.84154
```

Inspect the regenerated inputs before committing them.

```bash
git status --short
```

## 8. Validation Notebook

After all three solved networks exist, open the validation notebook.

```bash
jupyter lab notebooks/za_validation/12_dispatch_calibration/dispatch_calibration_validation_calibrated_demand.ipynb
```

Restart the kernel and run all cells.

Confirm the notebook loads these three neutral solved-network suffixes and maps
them to presentation labels inside the notebook:

```text
EAF-CONFIG-coal485_nuclear50_no_vre_no_ocgt_cap
EAF-CONFIG-coal485_nuclear50_vre_only
EAF-CONFIG-coal485_nuclear50_vre_ocgt_cap
```

Compare the notebook outputs against last week's presentation values. Keep any
presentation-specific naming, ordering, and chart labels inside the notebook;
do not add presentation labels to Snakemake targets.
