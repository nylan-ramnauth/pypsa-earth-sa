# Module 13f — Demand Alignment Fix

**Target agent:** Claude Opus (standalone — no prior conversation context)
**Working directory:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Conda environment:** `pypsa-earth`
**Solver:** None required (this is a pipeline rebuild, not a re-solve)

---

## Purpose

Fix the 1.56% demand gap between PyPSA-Earth's 2023 solved network (222.35 TWh) and the Eskom 2023 contracted demand target (225.87 TWh). The fix is a single YAML config change — no Python code modification required.

Once complete, re-run the downstream network build pipeline from `simplify_network` forward and verify the Earth load matches the RSA benchmark demand.

---

## Context

### Root cause (confirmed)

The gap occurs in the `simplify_network` step, between `networks/za_2023_fixed_validation/elec.nc` (225.87 TWh, 1606 buses) and `networks/za_2023_fixed_validation/elec_s.nc` (222.35 TWh, 803 buses).

`simplify_network.py` calls `drop_isolated_networks(n, threshold)` when `p_threshold_drop_isolated` is set to a numeric value. This function finds isolated AC sub-networks whose mean load power is below the threshold and removes them entirely, along with their loads. With the default value of `p_threshold_drop_isolated: 20`, small isolated Eskom-served nodes totalling 3.52 TWh are silently discarded.

These nodes represent real Eskom contracted demand. For the ZA validation calibration run (Eskom MLR perimeter), all contracted demand must be preserved.

The `za_2023_fixed_validation.yaml` config does not override this threshold, so it inherits the default value of 20 MW from `config.default.yaml`.

| File | Total load | Buses |
|---|---|---|
| `elec.nc` (after add_electricity) | **225.87 TWh** | 1606 |
| `elec_s.nc` (after simplify_network) | **222.35 TWh** | 803 |
| `elec_s_34.nc` (after cluster_network) | 222.35 TWh | 34 |
| `solved.nc` (EAF-OPC-CAP) | 222.35 TWh | 34 |

The fix disables isolated-network dropping and merging in the simplify step for the ZA validation run.

### Config structure

Default values live in `config.default.yaml` under:
```yaml
cluster_options:
  simplify_network:
    p_threshold_drop_isolated: 20   # [MW] drops nodes below this mean load
    p_threshold_merge_isolated: 300 # [MW] merges nodes below this mean load
```

The ZA validation config is at `configs/za/za_2023_fixed_validation.yaml`. It already overrides several `cluster_options` settings (e.g., `clusters: [34]`). The fix adds two overrides to the `cluster_options.simplify_network` block.

### Three-step execution order in simplify_network.py

```python
if p_threshold_drop_isolated:
    n = drop_isolated_networks(n, threshold=p_threshold_drop_isolated)
    # → removes isolated sub-networks; demand lost permanently

if p_threshold_merge_isolated:
    n = merge_isolated_networks(n, threshold=p_threshold_merge_isolated)
    # → consolidates small islands into a single isolated bus per country
    # → demand preserved, but buses still have NO lines to the backbone

if s_threshold_fetch_isolated:
    n = merge_into_network(n, threshold=s_threshold_fetch_isolated)
    # → spatially re-attaches isolated buses to nearest backbone bus
    # → demand finally becomes serviceable
```

Simply disabling both drop and merge still leaves isolated buses as powerless islands — the load cannot be served because there are no lines to them. Setting `p_threshold_merge_isolated: false` without `s_threshold_fetch_isolated` would move the demand gap into spurious load shedding instead of fixing it.

The correct fix is:
- `p_threshold_drop_isolated: false` — stop discarding demand
- `s_threshold_fetch_isolated: 1.0` — attach all isolated buses to their nearest backbone bus

`s_threshold_fetch_isolated` takes a **share of national load** as threshold. Setting it to `1.0` (100%) means: fetch any isolated sub-network whose load share is below 100% of national load — which catches every isolated node by definition.

---

## Implementation Steps

### Step 1 — Inspect the current config

Read `configs/za/za_2023_fixed_validation.yaml`. Locate the `cluster_options:` block (if it exists) or the correct location to add it. Do not modify any settings other than the two specified.

---

### Step 2 — Add the overrides

In `configs/za/za_2023_fixed_validation.yaml`, add or extend the `cluster_options.simplify_network` block:

```yaml
cluster_options:
  simplify_network:
    p_threshold_drop_isolated: false  # stop discarding isolated nodes
    s_threshold_fetch_isolated: 1.0   # re-attach all isolated buses to nearest backbone bus
```

If `cluster_options:` already exists in the file, add the two lines inside the existing `simplify_network:` sub-block. Do not duplicate top-level keys. Do not touch any other cluster settings (e.g., `clusters`, `algorithm`).

`p_threshold_merge_isolated` is left at its default (300 MW) — consolidating small islands before fetching does no harm and slightly reduces bus count before the spatial join.

---

### Step 3 — Verify the demand in elec.nc is correct

Before rebuilding, confirm that `elec.nc` has the correct pre-simplify demand:

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth
conda run -n pypsa-earth python - << 'EOF'
import pypsa
n = pypsa.Network("networks/za_2023_fixed_validation/elec.nc")
total = n.loads_t.p_set.sum().sum() / 1e6
print(f"elec.nc total load: {total:.4f} TWh  (expected 225.87 TWh)")
EOF
```

If `elec.nc` does not exist or shows a value significantly different from 225.87 TWh, stop and report — the issue is upstream of `simplify_network` and requires further investigation.

---

### Step 4 — Rebuild from simplify_network

Delete or force-rebuild the stale downstream networks so Snakemake re-runs from `simplify_network` forward:

```bash
cd /Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth

# Touch the config file to mark it as newer (triggers Snakemake rebuild)
touch configs/za/za_2023_fixed_validation.yaml

# Dry run first — verify target is correct
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 --dryrun \
  "networks/za_2023_fixed_validation/elec_s_34_ec_lc1.nc"

# If dry run looks correct, run
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 \
  "networks/za_2023_fixed_validation/elec_s_34_ec_lc1.nc"
```

This will re-run `simplify_network`, `cluster_network`, `add_extra_components`, and `prepare_network`. It will NOT re-run `add_electricity` (which already produced the correct `elec.nc` at 225.87 TWh).

> **Note:** If Snakemake does not detect the rebuild automatically, delete the stale files and re-run:
> ```bash
> rm -f networks/za_2023_fixed_validation/elec_s*.nc
> rm -f networks/za_2023_fixed_validation/elec_s.nc
> ```

---

### Step 5 — Verify intermediate demand

After `simplify_network` completes, check `elec_s.nc`:

```bash
conda run -n pypsa-earth python - << 'EOF'
import pypsa
n = pypsa.Network("networks/za_2023_fixed_validation/elec_s.nc")
total = n.loads_t.p_set.sum().sum() / 1e6
print(f"elec_s.nc total load: {total:.4f} TWh  (expected ≈225.87 TWh)")
print(f"Buses: {len(n.buses)}")
EOF
```

**Expected result:** 225.87 TWh (or very close — floating point loss during aggregation should be < 0.01 TWh).

---

### Step 6 — Re-run the validation solve

Once the prepare step finishes, re-run the full solve for the EAF-OPC-CAP scenario:

```bash
snakemake --configfile configs/za/za_2023_fixed_validation.yaml \
  --cores 4 \
  "results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
```

---

## Acceptance Gates

After the solve completes, run this verification script and paste the output:

```python
import pypsa

n = pypsa.Network(
    "results/za_2023_fixed_validation/networks/"
    "elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc"
)

load_total = n.loads_t.p_set.sum().sum() / 1e6
gen_total = n.generators_t.p.sum().sum() / 1e6
shed = n.generators_t.p.filter(regex="[Ll]oad.shed|[Cc]urtail").sum().sum() / 1e6

print(f"Total load (TWh):        {load_total:.4f}")
print(f"Total generation (TWh):  {gen_total:.4f}")
print(f"Load shedding (TWh):     {shed:.4f}")
print(f"Buses:                   {len(n.buses)}")
print(f"Snapshots:               {n.snapshots[0]} → {n.snapshots[-1]}")
```

**Pass criteria:**

| Check | Expected | Action if wrong |
|---|---|---|
| Total load | ≥ 225.70 TWh (≤ 0.07% below 225.87) | Fail — config change did not take effect; check YAML syntax |
| Total load (was) | 222.35 TWh (the pre-fix value) | If still 222.35 TWh, touch + rebuild did not propagate |
| Buses | 34 | Expected — clustering target unchanged |
| Snapshots | 2023-01-01 → 2023-12-31 | Expected |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `elec_s.nc` still shows 222.35 TWh | YAML not picked up / Snakemake used cached output | Delete `elec_s.nc` manually, re-run |
| `elec_s.nc` shows 225.87 TWh but load shedding is very high | `s_threshold_fetch_isolated` not set; isolated buses preserved but unserveable | Confirm `s_threshold_fetch_isolated: 1.0` is in config and took effect |
| Snakemake errors on duplicate key | `cluster_options:` block appears twice in config | Remove duplicate, keep only one |
| `elec.nc` load ≠ 225.87 TWh | Upstream issue in `add_electricity` or demand pipeline | Stop — do not continue; report exact value |
| `prepare_network` fails | Missing intermediate file | Run each step separately: `simplify_network`, then `cluster_network`, then the rest |

---

## Files Created or Modified

| File | Action |
|---|---|
| `configs/za/za_2023_fixed_validation.yaml` | Modified — two lines added under `cluster_options.simplify_network` |
| `networks/za_2023_fixed_validation/elec_s.nc` | Rebuilt by Snakemake |
| `networks/za_2023_fixed_validation/elec_s_34.nc` | Rebuilt by Snakemake |
| `networks/za_2023_fixed_validation/elec_s_34_ec.nc` | Rebuilt by Snakemake |
| `networks/za_2023_fixed_validation/elec_s_34_ec_lc1.nc` | Rebuilt by Snakemake |
| `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc` | Re-solved |

---

## Hard Constraints

- Do **not** modify `config.default.yaml` — change only `configs/za/za_2023_fixed_validation.yaml`
- Do **not** re-run `add_electricity` or any rule that touches `elec.nc` unless you have confirmed it is broken
- Do **not** change the clustering target (34 nodes) or any other cluster settings
- Do **not** change any solver settings
- Do **not** set `p_threshold_merge_isolated: false` — leaving it at the default (300 MW) is correct; consolidating islands before fetching is harmless and slightly cleaner
- If `elec.nc` load ≠ 225.87 TWh, **stop and report** — do not proceed with the rebuild
