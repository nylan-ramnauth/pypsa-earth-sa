# ZA V1 System Boundary And Carrier Taxonomy (Module 05)

| field | value |
|---|---|
| status | canonical |
| date | 2026-05-08 |
| author | Claude (Opus 4.7) |
| pypsa-earth HEAD | `f5422d8f384a86117bbc18b3048784e265808669` |
| pypsa-rsa pin | `89872c1ea703af3d8a3f198706d1ab7958f50a5f` (HEAD = origin/main) |
| source plan | `doc/active/calibration-plan/05_system_boundary_and_carrier_taxonomy.md` |
| machine mirror | `data/za_audit/za_carrier_taxonomy.csv` |
| crosscheck | `data/za_audit/za_carrier_taxonomy_crosscheck.csv` |
| smoke test | `scripts/za_validation/smoke_carrier_taxonomy.py` |

This document is the locked V1 modeling boundary and carrier taxonomy. It is
read by modules 06 (demand and import/export), 07 (costs and emissions),
08 (final fleet reconciliation), 09 (grid topology), 10 (local-carrier hook),
11 (dispatch). No downstream module may pick a different boundary or different
carrier mapping without re-opening this lock.

---

## 1. System boundary

| lock | value |
|---|---|
| scope | national South Africa 2023 electricity system |
| demand target | RSA Contracted Demand |
| load shedding target | MLR + ILS + IOS |
| imports / exports | exogenous time series owned by module 06 |
| embedded / rooftop PV | excluded as explicit plant capacity in V1 unless already in Eskom reported PV and reconciled as grid-facing capacity; possible residual effect documented as a demand/accounting issue |
| IPP utility wind / PV / CSP | included when present in Eskom reported generation and 2023 plant reconciliation |

The locks are mirrored in `configs/za/za_2023_fixed_validation.yaml` under
`za_system_boundary:`.

---

## 2. RSA → V1 carrier taxonomy

| RSA concept | V1 PyPSA-Earth carrier | type | notes |
|---|---|---|---|
| coal | `coal` | upstream conventional | Eskom large coal fleet |
| sasol_coal | excluded from Module 12 structural baseline onward | out of boundary | captive industrial generation; removed before fixed-grid baseline because no Eskom hourly validation column exists |
| nuclear | `nuclear` | upstream conventional | Koeberg |
| ocgt_diesel / diesel peakers | `ocgt_diesel` | local | explicit cost / emissions row |
| ocgt_avf / gas OCGT | `ocgt_gas` | local | explicit cost / emissions row |
| sasol_gas | excluded from Module 12 structural baseline onward | out of boundary | Sasol gas turbines are self-dispatched industrial assets, not Eskom National Control OCGT dispatch |
| wind | `onwind` | upstream renewable | atlite profile |
| solar PV | `solar` | upstream renewable | atlite profile |
| solar_csp / csp | `csp` | upstream renewable | atlite profile, never mapped to PV |
| reservoir hydro | hydro / reservoir-compatible | upstream | PyPSA-Earth native treatment |
| run-of-river hydro | `ror` / hydro-compatible | upstream | PyPSA-Earth native treatment |
| pumped storage | PHS-compatible | upstream | PyPSA-Earth storage; PHS energy checked |
| battery | `battery` | upstream store | only 2023-active batteries that pass normalization smoke; otherwise excluded with audit record |
| hydro_import | exogenous import | not domestic | owned by module 06 |
| biomass | excluded unless explicitly represented later | upstream candidate | biomass is canonical name; `bioenergy` normalizes to `biomass`, but no separate 2023 biomass generator is active in the Module 12 baseline |
| Other RE | excluded from Module 12 structural baseline onward | accounting category | aggregate Eskom 8760 "Other RE" series is omitted from the dispatchable model; omission is quantified separately |

**Total V1 carrier set:** `coal`, `nuclear`, `solar`, `onwind`, `hydro`, `ror`,
`csp`, `battery` if present, `ocgt_diesel`, and reserved `ocgt_gas`. Pumped
storage and `hydro_import` are treated through PyPSA storage /
exogenous-load mechanisms rather than named generator carriers. `sasol_coal`,
`sasol_gas`, `other_re`, and `biomass` are excluded from the Module 12
structural baseline unless a later module explicitly re-opens the boundary
with source-backed representation.

---

## 3. Carrier registration contract

- This module owns: canonical carrier names, profile intent, emissions intent,
  reporting metadata (color, nice_name), validation target, availability
  treatment.
- Module 07 owns: numeric cost / fuel / emissions rows in
  `data/za_audit/za_local_carrier_cost_rows.csv`.
- Module 08 owns: the active-2023 biomass decision and final fleet
  reconciliation.
- Module 10 owns: the `apply_za_local_carriers` hook that writes local
  carrier rows to the network **after** `add_electricity`. The hook must not
  mutate upstream Carrier rows; it may add only the local ZA carrier rows and
  the local generator / reporting metadata defined here.

---

## 4. CSP lock

```text
installed capacity = 500 MW
generation = 1.375 TWh
```

- Redstone CSP is excluded from the 2023 baseline (commissioned 2024+).
- V1 preferred profile route: native atlite / PyPSA-Earth `profile_csp.nc`.
- If native CSP profile generation fails, a documented temporary simplified
  CSP profile fallback is allowed. It must be isolated, reported, and
  revisited before final thesis claims.
- Mapping CSP to PV is forbidden — CSP and solar must remain distinct
  non-zero carriers.
- CSP storage-hour metadata is preserved in the source registry for later
  explicit thermal-storage CSP modelling.

The lock is mirrored in `configs/za/za_2023_fixed_validation.yaml` under
`za_system_boundary.csp_2023_anchors`.

---

## 5. Biomass policy

Module 08 owns the active-2023 biomass decision and must use:

- module 04 fixed-technology candidates
  (`data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv`)
- REIPPPP / source registry
  (`data/za_audit/pypsa_rsa_source_registry.csv`)
- Eskom "Other RE" audit evidence
  (Module 02 outputs and `pypsa_rsa_eskom_pu_profiles_audit.csv`)

If no separately validated 2023 biomass plant exists, no `biomass` generator
is added. From Module 12 onward, the aggregate `other_re` accounting category
is also excluded from the dispatchable structural baseline; its omitted energy
is tracked as a validation/reporting gap rather than modeled as a carrier.

---

## 6. Carrier case policy

- Local ZA carriers are lowercase snake_case. The active Module 12 local set is
  `ocgt_diesel`, with `ocgt_gas` reserved for a source-backed AVF gas OCGT row.
  `sasol_coal`, `sasol_gas`, and `other_re` are historical taxonomy labels now
  marked excluded by boundary.
- Upstream PyPSA-Earth carriers retain upstream casing and names: `OCGT`,
  `CCGT`, `H2`, `biomass`, `solar`, `onwind`, `csp`, `coal`, `nuclear`,
  `hydro`, `ror`, `battery`.
- `biomass` is canonical. `bioenergy` is only a secondary-source label and
  must normalize to `biomass` before entering PyPSA-Earth.

---

## 6b. Crosscheck statuses

The crosscheck CSV uses four status values:

| status | meaning |
|---|---|
| `resolved` | RSA carrier maps to one V1 carrier; consume in modules 06–10 |
| `excluded_by_boundary` | RSA carrier excluded by `za_system_boundary` (e.g. `solar_pv_rooftop` — embedded PV) |
| `pending_module_08` | RSA label is a procurement program, not a carrier (e.g. `rmippp`); module 08 reconciles per-plant carrier during fleet build |
| `unresolved` | mapping missing; gate fails |

Module 05 is complete only when no `unresolved` rows remain in
`za_carrier_taxonomy_crosscheck.csv`.

---

## 7. Cross-references

- Config locks: `configs/za/za_2023_fixed_validation.yaml`
  (`za_system_boundary`, `za_local_carriers`, `electricity.conventional_carriers`,
  `electricity.renewable_carriers`, `electricity.extendable_carriers`).
- Machine mirror: `data/za_audit/za_carrier_taxonomy.csv`.
- Resolution check: `data/za_audit/za_carrier_taxonomy_crosscheck.csv`.
- Module 04 audit inputs that justify each row:
  - `data/za_audit/pypsa_rsa_fixed_technologies_2023_candidates.csv`
  - `data/za_audit/reipppp_solar_2023_candidates.csv`
  - `data/za_audit/reipppp_wind_2023_candidates.csv`
  - `data/za_audit/pypsa_rsa_eskom_pu_profiles_audit.csv`
  - `data/za_audit/pypsa_rsa_cost_fuel_emissions_audit.csv`
- Notebook: `notebooks/za_validation/05_carrier_taxonomy/carrier_taxonomy_overview.ipynb`.
- HTML: `doc/za_validation/figures/05_carrier_taxonomy/carrier_taxonomy_overview.html`.

---

## 8. Acceptance smoke test

The acceptance gate from
`doc/active/calibration-plan/05_system_boundary_and_carrier_taxonomy.md`
lines 96–101:

```python
assert "csp" in n.carriers.index
assert n.generators.query("carrier=='csp'").p_nom.sum() > 400  # MW, lower bound
assert "solar" in n.carriers.index
assert n.generators.query("carrier=='solar'").p_nom.sum() > 5000  # MW, SA PV lower bound
# CSP and solar must be distinct non-zero carriers; CSP must never merge into solar.
```

This assertion fires once module 10's `apply_za_local_carriers` hook produces
a network. The deferred runner is
`scripts/za_validation/smoke_carrier_taxonomy.py`.

Status as of module 05 completion: **pending module 10**.
