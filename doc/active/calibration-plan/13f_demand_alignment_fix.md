# Module 13f — Demand Alignment Fix

**Target agent:** Claude Opus (standalone — no prior conversation context)
**Working directory:** `/Users/nylan/Documents/BSE/Reliable-Electrification-Planning-SA-Vault/6-codebases/repos/pypsa-earth`
**Conda environment:** `pypsa-earth`
**Solver:** None required (this is a pipeline rebuild, not a re-solve)

---

## Purpose

Fix the 1.56% demand gap between PyPSA-Earth's 2023 solved network (222.35 TWh) and the Eskom 2023 contracted demand target (225.87 TWh). The accepted implementation is a config-controlled Python path in `simplify_network.py`: transfer isolated-bus load to nearest kept buses inside the same 34-region Eskom supply area, then keep the normal isolated-bus drop path.

Once complete, re-run the downstream network build pipeline from `simplify_network` forward and verify the Earth load matches the RSA benchmark demand.

> **Implementation update — 2026-05-15.** The original fetch-based fix
> (`p_threshold_drop_isolated: false`, `s_threshold_fetch_isolated: 1.0`) was
> superseded after it preserved demand but moved load into constrained regions
> and raised `EAF-OPC-CAP` load shedding to 45.09 TWh. The implemented fix now
> follows Option C from the regression diagnosis: transfer isolated-bus loads to
> nearest kept buses inside the same 34-region Eskom supply area, then keep the
> normal `p_threshold_drop_isolated: 20` drop path and disable topology fetching.
> The audit is `data/za_audit/za_isolated_load_transfer.csv`.
>
> Verified result: `elec_s.nc = 225.8749 TWh`, `elec_s_34.nc = 225.8749 TWh`,
> `EAF-OPC-CAP` OCGT dispatch remains capped at `5.500000 TWh`, and final load
> shedding is `2.4969 TWh` instead of the fetch-path `45.0865 TWh`.
> The solved shedding number was an immediate post-fix check and was superseded
> by the later full comparable scenario refresh. Use the 2026-05-15 comparator
> lock in Module 13g for current NoCO2/EAF/OPC/CAP metrics.
>
> **Scenario split update — 2026-05-15.** A follow-up coherence check found that
> the `EAF-OPC` and `EAF-OPC-CAP` rules both applied the annual OCGT cap from the
> same operational-constraints workbook. The rules now pass an explicit scenario
> switch: `EAF-OPC` skips the `global / ocgt_diesel / output_energy / year / max`
> row and `EAF-OPC-CAP` applies it. Fresh validation results are:
> `EAF-OPC` OCGT `8.4336 TWh`, shedding `0.0125 TWh`; `EAF-OPC-CAP` OCGT
> `5.5000 TWh`, shedding `2.4969 TWh`.
> These rule-separation checks are historical; current run-to-run comparison
> should use the final refreshed scenario set.
>
> **Comparator-toggle requirement — 2026-05-15.** Module 13f must remain
> independently switchable from Module 13g. The config must support four
> comparable experiment modes: baseline (`13f=false`, `13g=false`), 13f-only
> (`13f=true`, `13g=false`), 13g-only (`13f=false`, `13g=true`), and combined
> (`13f=true`, `13g=true`). Do not hard-code 13g assumptions into 13f, and do
> not make 13g depend on 13f being enabled.

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

The accepted fix does **not** fetch isolated topology. It transfers the load from droppable isolated buses to kept buses before dropping the isolated islands. This preserves demand without adding disconnected topology to the optimization problem.

### Config structure

Default values live in `config.default.yaml` under:
```yaml
cluster_options:
  simplify_network:
    p_threshold_drop_isolated: 20   # [MW] drops nodes below this mean load
    p_threshold_merge_isolated: 300 # [MW] merges nodes below this mean load
```

The ZA validation config is at `configs/za/za_2023_fixed_validation.yaml`. It already overrides several `cluster_options` settings (e.g., `clusters: [34]`). The fix keeps `p_threshold_drop_isolated: 20`, disables fetch, and controls the load-transfer path through `za.isolated_load_transfer.enable`.

Current implementation must be controlled by an explicit ZA toggle:

```yaml
za:
  isolated_load_transfer:
    enable: true
    audit: data/za_audit/za_isolated_load_transfer.csv
```

When `za.isolated_load_transfer.enable: false`, the pipeline must behave like the pre-13f baseline: isolated load is not transferred and the normal `p_threshold_drop_isolated: 20` drop path determines the lower post-simplify demand. This is required so 13g-only and baseline runs remain comparable.

### Module comparison modes

Use this matrix when isolating module impact:

| Mode | `za.isolated_load_transfer.enable` | `za_coal_disaggregation.enable` | Expected purpose |
|---|---:|---:|---|
| Baseline / Module 12 | `false` | `false` | Original demand-drop and aggregated coal EAF overlay |
| 13f-only | `true` | `false` | Demand alignment impact only |
| 13g-only | `false` | `true` | Coal disaggregation impact only, on the lower-demand baseline |
| 13f + 13g | `true` | `true` | Combined candidate for accepted calibration path |

Acceptance gates must be mode-aware. A 13g-only run is allowed to retain the pre-13f lower demand; that is the point of the isolation test. Only 13f-enabled modes should be required to preserve ≥ 225.70 TWh.

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

Simply disabling both drop and merge still leaves isolated buses as powerless islands — the load cannot be served because there are no lines to them. The rejected fetch-based path (`p_threshold_drop_isolated: false`, `s_threshold_fetch_isolated: 1.0`) preserved demand but changed topology and caused the Module 13f load-shedding regression.

The correct accepted fix is:
- `za.isolated_load_transfer.enable: true` — transfer load from droppable isolated buses before dropping them
- `cluster_options.simplify_network.p_threshold_drop_isolated: 20` — keep the normal drop path after load transfer
- `cluster_options.simplify_network.s_threshold_fetch_isolated: false` — do not use spatial topology fetching

When `za.isolated_load_transfer.enable: false`, the transfer step must be skipped and the run should reproduce the pre-13f demand-drop behavior.

---

## Implementation Steps

### Step 1 — Inspect the current config

Read `configs/za/za_2023_fixed_validation.yaml`. Locate the `cluster_options:` block (if it exists) or the correct location to add it. Do not modify any settings other than the two specified.

---

### Step 2 — Add the toggle and simplify settings

In `configs/za/za_2023_fixed_validation.yaml`, add or verify:

```yaml
za:
  isolated_load_transfer:
    enable: true
    audit: data/za_audit/za_isolated_load_transfer.csv

cluster_options:
  simplify_network:
    p_threshold_drop_isolated: 20     # drop isolated nodes after load transfer
    s_threshold_fetch_isolated: false # do not fetch isolated topology
```

If `cluster_options:` or `za:` already exists in the file, extend the existing blocks. Do not duplicate top-level keys. Do not touch unrelated cluster settings (e.g., `clusters`, `algorithm`).

`p_threshold_merge_isolated` is left at its default unless the current implemented code path explicitly bypasses it for transferred islands. The critical invariant is: transfer load first, then drop the now-zeroed isolated buses; do not fetch isolated buses into the backbone.

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
| `elec_s.nc` shows 225.87 TWh but load shedding is very high | Rejected fetch/topology path may be active, or load was transferred into constrained buses incorrectly | Confirm `za.isolated_load_transfer.enable: true`, `p_threshold_drop_isolated: 20`, and `s_threshold_fetch_isolated: false`; inspect `data/za_audit/za_isolated_load_transfer.csv` |
| Snakemake errors on duplicate key | `cluster_options:` block appears twice in config | Remove duplicate, keep only one |
| `elec.nc` load ≠ 225.87 TWh | Upstream issue in `add_electricity` or demand pipeline | Stop — do not continue; report exact value |
| `prepare_network` fails | Missing intermediate file | Run each step separately: `simplify_network`, then `cluster_network`, then the rest |

---

## Files Created or Modified

| File | Action |
|---|---|
| `scripts/simplify_network.py` | Modified — config-controlled isolated-load transfer before isolated-bus dropping |
| `configs/za/za_2023_fixed_validation.yaml` | Modified — `za.isolated_load_transfer` block plus simplify settings |
| `data/za_audit/za_isolated_load_transfer.csv` | Created — audit of transferred isolated-bus loads |
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
- Do **not** re-enable `s_threshold_fetch_isolated: 1.0` for the accepted path — that was the regression path
- Do **not** make Module 13g depend on `za.isolated_load_transfer.enable: true`; the toggles must remain independent for attribution runs
- If `elec.nc` load ≠ 225.87 TWh, **stop and report** — do not proceed with the rebuild
