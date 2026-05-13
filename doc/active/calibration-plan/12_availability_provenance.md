# Module 12 — Availability Source Provenance

**Status:** implemented and solved (2026-05-12). `lc1_NoCO2-1H` structural
baseline passed all 12 acceptance gates, then the coal-only station-weekly EAF
overlay was applied to `lc1_NoCO2-1H-EAF`. The solved EAF network is optimal and
the Module 12 validation notebook reports 12/12 PASS for `eaf_calibrated`.

## Primary source

- **Workbook:** `6-codebases/repos/pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/plant_availability.xlsx`
- **Sheets:**
  - `annual_availability` — annual mean availability per station / scenario.
  - `outage_profiles` — weekly outage rows; columns include scenario (`BASE`,
    `BASE_FLAT`), `planned`, `unplanned`, week index 1–53, and per-station
    columns for Arnot, Camden, Duvha, Grootvlei, Hendrina, Kendal, Komati,
    Kriel, Kusile, Lethabo, Majuba, Matimba, Matla, Medupi, Tutuka.
- **Formula (BASE scenario):** `availability_weekly = 1 - planned - unplanned`.
- **Expected magnitudes:** fleet mean availability ≈ 0.656; per-station means
  range ≈ 0.498–0.875.

## Out-of-scope companion workbook

- **Workbook:** `6-codebases/repos/pypsa-rsa/scenarios/Coal_Flexibilisation/sub_scenarios/operational_constraints.xlsx`
- **Sheets:** `operational_constraints`, `operational_reserves`.
- **Role:** scenario constraints for gas, reserves, Sasol, nuclear, renewables.
  **Not** the primary coal availability source — do not consume here.

## Cross-references already in the vault

- `data/za_audit/za_named_plant_inventory.csv` — station name, lat/lon,
  nameplate, and `csp_storage_hours` notes for CSP plants. Used by
  `scripts/za_fleet/fix_csp_links_stores.py` for CSP Store sizing.
- `data/custom_powerplants.csv` — per-plant `bus` assignment used during
  station→bus mapping in this provenance plan.
- `data/za_audit/pypsa_rsa_availability_audit.csv` — discovery sweep that
  located the workbook in the pypsa-rsa source registry.

## EAF mapping implementation

Implemented in `scripts/za_fleet/apply_coal_eaf.py` and wired through
`apply_za_coal_eaf` / `solve_network_eaf` in `Snakefile`.

1. Parse `plant_availability.xlsx:outage_profiles`. Filter `scenario == "BASE"`.
2. For each (station, week): `avail = clip(1 - planned - unplanned, 0, 1)`.
3. Map station → bus via inner join on station name against
   `custom_powerplants.csv` (Fueltype=Coal). Capacity-weight when multiple
   stations land on one bus: `avail_bus = Σ(cap_i * avail_i) / Σ(cap_i)`.
4. Expand weekly availability to hourly snapshots by ISO week (broadcast across
   168 hours per week; week 53 handled as overlap with week 52).
5. Write hourly coal `p_max_pu` per generator. Stations without a weekly
   match fall back to fleet capacity-weighted mean availability; unmatched MW
   is logged in the audit CSV.
6. Audit columns include `source_workbook`, `sheet`, `scenario`, `outage_types`,
   `station_to_bus_mapping_rule`, `fallback_used`, `unmatched_mw`,
   `coal_generators_overlaid`, `n_snapshots`, `mean_fleet_availability`, and
   `non_coal_p_max_pu_changed`.

## Generated artifacts

- Prepared EAF network:
  `networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc`
- Pre-EAF backup:
  `networks/za_2023_fixed_validation/elec_s_34_ec_lc1_NoCO2-1H.pre_eaf.nc`
- Solved EAF network:
  `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF.nc`
- Audit:
  `data/za_audit/za_coal_eaf_audit.csv`

Audit summary: `unmatched_mw = 160` (Kelvin only), `any_fallback_used = True`,
`non_coal_p_max_pu_changed = False`, and `mean_fleet_availability = 0.635`.
Only coal `generators_t.p_max_pu` columns differ between the `.pre_eaf.nc`
backup and the prepared EAF network.

## Decisions

- **Granularity:** station-level weekly mapped to bus-level coal generators
  (user-confirmed default). Preserves more provenance than monthly carrier-level
  `p_max_pu`, and the workbook supports it directly.
- **Sequencing:** structural `lc1_NoCO2-1H` baseline must pass all expansion +
  CSP/PHS gates before EAF is wired. No calibrated solve attempted until the
  Module 12 fixed-grid acceptance checks all flip to PASS.
