## Context

  Module 13g has been structurally implemented in `pypsa-
  earth`:

  - 15 named Eskom coal plants are injected at the
  existing `apply_za_coal_eaf` slot.
  - The EAF network solves optimal.
  - Structural checks pass: 15 coal generators, 41.419 GW
  coal, preserved 225.874862 TWh load, 8760x15
  `p_max_pu`, no UC flags.
  - Current diagnostic solve with normalized EAF_48
  gives:
    - coal: 111.391 TWh
    - load shedding: 62.721 TWh
    - coal Pearson r vs Eskom thermal: 0.560

  Do not accept this result as calibration. It is
  diagnostic.

  ## Key Finding

  The current 13g implementation does **not** match
  PyPSA-RSA’s EAF_48 semantics.

  Current 13g does simple normalization:

  ```text
  raw_availability = 1 - planned - unplanned
  scaled_availability = raw_availability * (0.48 /
  mean(raw_availability))

  PyPSA-RSA does something different:

  planned outages stay fixed
  unplanned outages are scaled so annual mean EAF hits
  0.48

  target_unplanned = 1 - mean(planned) - projected_eaf
  scale = target_unplanned / mean(raw_unplanned)
  p_max_pu = 1 - planned - scale * raw_unplanned

  Grounding in RSA:

  - 6-codebases/repos/pypsa-rsa/scenarios/Benchmark_2023/
    scenarios_to_run.xlsx
      - scenario = S_2023BM
      - outage_profiles = BASE
      - annual_availability = EAF_48
      - unit_committment = True
      - override_coal_msl = 0.7
      - coal_ramp_rate_multiplier = 1.5
  - 6-codebases/repos/pypsa-rsa/scripts/
    add_electricity.py
      - get_eaf_profiles() around line 415 reads planned/
        unplanned outage profiles.
      - proj_eaf_override() around line 450 keeps planned
        fixed and scales unplanned.
      - adjust_com_msl() around line 1401 sets time-
        varying MSL as p_min_pu * p_max_pu.

  ## Important Interpretation

  EAF_48 is still the RSA-parity target, but it should be
  judged with 13h UC enabled.

  The failed 13g no-UC EAF_48 result means:

  EAF_48 without RSA-style UC/MSL/ramp behavior is not an
  accepted calibration candidate.

  It does not mean EAF_48 should be abandoned.

  Raw BASE availability should be used as a 13g no-UC
  control, not as final model semantics.

  ## Files to Inspect First

  Read these before editing:

  - PROJECT_AGENT.md
  - _status.md
  - _todo.md
  - 5-logs/shared/2026-05-15-1756-module-13g-coal-
    disaggregation-implementation.md
  - 6-codebases/repos/pypsa-earth/doc/active/calibration-
    plan/13g_coal_disaggregation.md
  - 6-codebases/repos/pypsa-earth/doc/active/calibration-
    plan/13h_coal_uc.md
  - 6-codebases/repos/pypsa-earth/scripts/
    build_za_coal_plants.py
  - 6-codebases/repos/pypsa-earth/scripts/za_fleet/
    build_za_coal_plants_network.py
  - 6-codebases/repos/pypsa-earth/configs/za/
    za_2023_fixed_validation.yaml
  - 6-codebases/repos/pypsa-rsa/scripts/
    add_electricity.py

  ## Required Work

  ### 1. Fix Bus Assignment Parity

  The current build_bus_assignment() uses nearest-bus
  KDTree assignment. This appears to move some coal
  plants away from the buses used in
  custom_powerplants.csv.

  Do not rely on KDTree as the primary mapping.

  Implement bus assignment using the existing coal
  mapping from:

  6-codebases/repos/pypsa-earth/data/
  custom_powerplants.csv

  Preferred approach:

  - Group coal rows by station base name.
  - Use their existing bus values as the canonical 13g
    bus mapping.
  - If a station has split rows but the same bus, assign
    that bus.
  - If a station has split rows across multiple buses,
    either:
      - split that station into multiple generator rows,
        or
      - fail fast and document the ambiguity.
  - Keep KDTree only as an explicit fallback with an
    audit flag, not as default.

  Add audit fields showing:

  - bus_assignment_source
  - fallback_used
  - any ambiguous station mappings

  ### 2. Add Availability Mode Toggle

  Add config under za_coal_disaggregation, for example:

  za_coal_disaggregation:
    enable: true
    availability_mode: rsa_eaf_projected  # raw_base |
  rsa_eaf_projected
    annual_availability_scenario: EAF_48
    outage_profiles_scenario: BASE
    plants_csv: data/za_validation/
  za_coal_plants_2023.csv
    eaf_hourly_csv: data/za_validation/
  za_coal_eaf_hourly_2023.csv
    bus_assignment_csv: data/za_validation/
  za_coal_bus_assignment.csv
    uc:
      enable: false

  Behavior:

  - raw_base: use 1 - planned - unplanned, clipped to [0,
    1].
  - rsa_eaf_projected: match RSA’s proj_eaf_override()
    semantics exactly:
      - keep planned outages fixed
      - scale unplanned outages to hit annual EAF target
      - output p_max_pu = 1 - planned -
        adjusted_unplanned

  ### 3. Implement RSA-Style EAF Projection

  Patch scripts/build_za_coal_plants.py.

  The current function uses only the Arnot column and
  simple normalization.

  Replace or extend it so it can:

  - read outage_profiles
  - read annual_availability
  - build profiles per station
  - support both raw_base and rsa_eaf_projected
  - use plant-specific columns where present, e.g. Arnot,
    Camden, Duvha, etc.
  - map annual availability rows like Arnot_EAF to plant
    Arnot
  - fall back to coal group rows only if plant-specific
    rows are missing and document that in audit/output

  Expected local sanity values for Arnot under RSA-style
  EAF_48:

  - raw BASE weekly availability mean: about 0.590
  - projected annual mean: 0.480
  - January mean: about 0.448
  - July mean: about 0.524

  Do not require the old plan value January ≈ 0.402; it
  is stale for the current workbook.

  ### 4. Update Audit Output

  Ensure za_coal_eaf_audit.csv records:

  - availability_mode
  - outage_profiles_scenario
  - annual_availability_scenario
  - mean_fleet_availability
  - per-plant mean_p_max_pu
  - bus_assignment_source
  - disaggregation_active
  - uc_enabled

  The audit must make it obvious whether a run is:

  - raw BASE no-UC
  - RSA EAF_48 projected no-UC
  - RSA EAF_48 projected + UC

  ### 5. Keep 13g and 13h Separate

  For this pass, preserve:

  za_coal_disaggregation.uc.enable: false

  Do not accidentally enable UC in 13g.

  But make sure the code path remains compatible with
  13h, where UC will be enabled later.

  13h should use:

  - rsa_eaf_projected
  - uc.enable: true
  - RSA-style p_min_pu(t) = 0.7 * p_max_pu(t)
  - ramp scaling as documented in 13h_coal_uc.md
  - LP relaxation, not MILP

  ## Validation Runs

  Run these in order.

  ### A. Rebuild Inputs

  From 6-codebases/repos/pypsa-earth:

  python scripts/build_za_coal_plants.py \
    --rsa-scenarios ../pypsa-rsa/scenarios/
  Benchmark_2023/sub_scenarios \
    --network networks/za_2023_fixed_validation/
  elec_s_34_ec_lc1_NoCO2-1H.nc \
    --plants-out data/za_validation/
  za_coal_plants_2023.csv \
    --eaf-out data/za_validation/
  za_coal_eaf_hourly_2023.csv \
    --bus-out data/za_validation/
  za_coal_bus_assignment.csv

  Adjust arguments if you add explicit CLI flags for
  availability_mode.

  ### B. Validate Generated CSVs

  Check:

  - 15 plants present.
  - total coal capacity remains about 41.419 GW.
  - bus mapping matches custom_powerplants.csv unless
    explicitly split/flagged.
  - rsa_eaf_projected annual mean is about 0.48.
  - Arnot January mean is about 0.448.
  - July mean is about 0.524.

  ### C. Rebuild 13g Network

  Run scoped Snakemake target for apply_za_coal_eaf, not
  a broad full rebuild.

  Expected:

  - 15 coal generators.
  - disaggregation_active = True.
  - no UC flags.
  - preserved load.
  - correct availability_mode in audit.

  ### D. Solve 13g No-UC

  Run the scoped EAF solve.

  Interpretation:

  - raw_base no-UC is the 13g control and should pass
    magnitude sanity.
  - rsa_eaf_projected no-UC is diagnostic only. Do not
    reject EAF_48 solely because no-UC magnitude is poor.

  ## Acceptance Criteria

  ### 13g Structural Acceptance

  13g is acceptable when:

  - 15 named coal generators exist.
  - total coal p_nom is about 41.419 GW.
  - bus assignments are parity-preserving or explicitly
    audited.
  - load is preserved in 13f-enabled mode.
  - no coal generator has committable=True.
  - generators_t.p_max_pu has 8760 rows and 15 coal
    columns.
  - audit records availability mode and bus mapping
    provenance.
  - non-coal p_max_pu is unchanged.

  ### 13g Calibration Interpretation

  - raw_base no-UC: use as no-UC control.
  - rsa_eaf_projected no-UC: diagnostic only.
  - Do not refresh final validation exports until 13h is
    accepted or explicitly rejected.

  ### 13h Readiness

  Proceed to 13h only after:

  - bus parity is fixed.
  - RSA-style EAF projection is implemented and audited.
  - 13g no-UC structural gates pass.
  - no-UC diagnostics are recorded.

  ## Expected Final Report Back

  Report:

  - files changed
  - exact availability modes implemented
  - bus assignment method and any fallback/ambiguity
  - generated EAF stats:
      - annual mean
      - January mean
      - July mean
  - solve status
  - coal TWh
  - OCGT TWh
  - load shedding TWh
  - coal Pearson r
  - whether result is accepted control or diagnostic

  ## Do Not Do

  - Do not treat the current normalized EAF_48 no-UC
    result as accepted.
  - Do not abandon EAF_48 as the RSA-parity target.
  - Do not enable UC silently in 13g.
  - Do not use KDTree bus assignment as default if
    custom_powerplants.csv provides a bus mapping.
  - Do not refresh final notebook/HTML validation
    artifacts until Module 13g/13h is resolved.