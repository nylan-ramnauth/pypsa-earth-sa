# South Africa Clean Rebuild Roadmap

This roadmap assumes the repository starts as a fresh clone of upstream PyPSA-Earth. The implementer should not see or copy the previous South Africa implementation. The old work is treated only as a source of lessons: what concepts mattered, what should be rebuilt cleanly, and what should be discarded.

The objective is a credible South Africa PyPSA-Earth baseline for thesis work. Reliability-aware planning comes later, after the baseline can be explained, validated, and shared with collaborators.

## Clean-Room Rule

Future implementation should follow current upstream PyPSA-Earth patterns and APIs. Do not port previous code, do not copy old configs, and do not revive old solver patches. Rebuild each useful concept from first principles with a small interface, clear assumptions, and a testable output.

Use this rule when assigning work to another agent:

> Start from upstream PyPSA-Earth. Implement only the concept described in the roadmap. Do not inspect or reuse the previous South Africa code. If a design choice is needed, prefer current upstream conventions and document the South Africa-specific assumption.

## Priority System

- `P0_BASELINE_FOUNDATION`: required before any serious South Africa thesis work.
- `P1_VALIDATION_AND_REALISM`: high-value additions after a minimal baseline run works.
- `P2_CALIBRATION_EXPERIMENTS`: useful optional validation modes, not default planning behavior.
- `P3_REFERENCE_ONLY`: preserve as lessons or analysis patterns, but do not rebuild now.
- `P4_DISCARD`: do not rebuild.

## P0: Baseline Foundation

### Clean South Africa Baseline Config

Build a new South Africa config from current upstream defaults. It should be boring on purpose: South Africa only, short snapshots, a manageable cluster count, Gurobi as the preferred solver, and clear scenario naming. It should not contain reliability-index logic, FBE policy logic, demand elasticity, fixed renewables, fixed trade, or EAF derating.

Acceptance criteria:

- A short-snapshot South Africa run can be launched from the config.
- Every departure from upstream defaults is documented in the config or companion notes.
- The config is small enough that a teammate can understand its purpose in one reading.

### South Africa External Data Contract

Create a public schema document for non-upstream inputs. The data itself may be shared outside GitHub, but the repo must define expected columns, units, timezones, date coverage, and validation checks.

Required data families:

- Eskom demand.
- Eskom generation by carrier or technology.
- Eskom availability, outage, or EAF data.
- Installed-capacity reference data.
- Currency, exchange-rate, and cost-assumption sources.
- Future electricity reliability index input.

Acceptance criteria:

- A teammate can prepare compatible data without reading code.
- Missing or private data can be replaced by documented placeholders for smoke tests.
- The schema distinguishes mandatory baseline inputs from optional validation inputs.

### Eskom Demand Preprocessing

Rebuild a standalone preprocessing tool that converts Eskom demand data into a PyPSA-Earth-compatible demand input. This should be an explicit data-preparation step, not hidden solver behavior.

Acceptance criteria:

- Validates timestamp uniqueness, hourly completeness, timezone, units, and date coverage.
- Reports annual energy, peak load, minimum load, and missing or duplicated hours.
- Produces a deterministic output file and a small validation summary.

### Eskom Generation Validation

Rebuild a standalone validation utility that compares solved PyPSA-Earth networks to Eskom observed generation. This is central to making the South Africa model defensible.

Acceptance criteria:

- Aggregates model generation by carrier using a documented carrier mapping.
- Compares model output with observed Eskom time series over matching timestamps.
- Reports energy totals, bias, MAE, RMSE, and residual time series where meaningful.
- Fails clearly when required carriers or timestamps are missing.

## P1: Validation And Realism

### Installed-Capacity Comparison

Rebuild a capacity diagnostic that compares model capacity by carrier to official South Africa or Eskom reference values. This should diagnose mismatch before attempting calibration.

Acceptance criteria:

- Uses current upstream powerplant and network schemas.
- Produces carrier-level model capacity, reference capacity, absolute error, and percentage error.
- Separates conventional generation, renewables, storage, and imports where data supports it.

### EAF Preprocessing

Rebuild availability preprocessing before changing optimisation behavior. The first tool should only convert Eskom outage or availability data into transparent hourly availability factors.

Acceptance criteria:

- Validates all availability factors are bounded between 0 and 1.
- Documents whether values are plant-level, carrier-level, fleet-level, weekly, or hourly.
- Produces summary statistics by carrier and period.
- Does not modify solver behavior.

### Scenario-Local Capacity Assumptions

Represent South Africa capacity constraints as scenario-local inputs or config overlays, not as edits to global PyPSA-Earth defaults.

Acceptance criteria:

- Source and year are documented for every capacity assumption.
- Capacity limits can be disabled without editing global files.
- Planning and validation scenarios use separate assumptions where needed.

### Currency And Cost Assumptions

Define how local currency outputs, exchange rates, and South Africa-specific cost assumptions are handled. Do not replace global upstream cost tables.

Acceptance criteria:

- Global cost data remains upstream-compatible.
- Any South Africa-specific override has a source, year, currency, and sensitivity label.
- Reports state whether values are in EUR, ZAR, or another unit.

### Generic Robustness Fixes

Rebuild only if current upstream still needs them. These are not South Africa features, but they can prevent bad runs.

Candidate fixes:

- Clear error when requested clusters exceed available buses.
- Safe handling of multiple loads on one bus.
- Robust component-index handling for optional technologies.
- CSP power-block cost fallback.
- Pumped-storage duration validation.

Acceptance criteria:

- Each fix is separate, small, and upstream-style.
- Each has a focused test, smoke check, or reproducible failure case.

## P2: Calibration Experiments

### Historical Validation Config

After the baseline works, create a separate 2023 historical validation config. It may use Eskom demand and validation outputs. It must be labelled as validation, not planning.

Acceptance criteria:

- It can run a short period before any full-year run is attempted.
- It keeps validation switches separate from the clean planning baseline.

### EAF Model Integration

Only after EAF preprocessing is validated, design how availability affects PyPSA components.

Open modelling choices to resolve then:

- Carrier-level, plant-level, or unit-level availability.
- Whether EAF affects dispatch availability, capacity credit, or both.
- Whether availability is used for historical validation only or future planning.

### Fixed Demand, Renewables, And Trade

These are useful calibration ideas but should not become the default planning baseline. Rebuild them only as explicit historical-validation switches.

Acceptance criteria:

- Each switch is independently enabled.
- Reports make clear when observed data is being imposed rather than predicted.
- Planning scenarios default to endogenous model behavior unless the scenario says otherwise.

### Hydro And Pumped-Storage Calibration

Revisit only after checking current upstream hydro and storage treatment. South Africa pumped storage is important, but corrections need careful unit and operational validation.

Acceptance criteria:

- Historical hydro and pumped-storage behavior is compared against reference data.
- Any correction is scenario-local or narrowly targeted.

### Demand Elasticity

Defer until the physical and validation baseline is credible. Demand elasticity may become useful for reliability or welfare analysis, but it should not be mixed into the first rebuild.

Acceptance criteria:

- There is a documented economic interpretation.
- Elasticity assumptions are tested as sensitivities, not defaults.

### Reliability-Index Spatial Allocation

Rebuild spatial allocation from scratch for the thesis reliability index. The relevant idea is mapping external spatial indicators to model buses or demand zones.

Acceptance criteria:

- Inputs, spatial joins, aggregation method, and bus-level outputs are documented.
- Results preserve national/provincial totals where applicable.
- The output can be joined to model demand or investment zones without FBE-specific concepts.

## P3: Reference Only

Keep these only as lessons, not implementation targets:

- FBE policy-scenario design.
- Household eligibility, receiving-household, and subsidy concepts.
- Bus-level population allocation as a policy-analysis artifact.
- Scenario sweep habits and naming conventions from class-project work.
- Diagnostic notebook ideas such as acceptance checks, topology comparison, and system-realism checks.
- Rendered class-project reports as historical narrative.

If any notebook or report idea becomes useful, rebuild it as a new reproducible analysis notebook with parameterized inputs and no local path assumptions.

## P4: Discard

Do not rebuild these:

- Wholesale replacement of global cost tables.
- Global default weather or cutout-year changes.
- FBE load splitting in core model code.
- FBE subsidy accounting in solver outputs.
- Temporary generated configs.
- Scratch scripts.
- Empty temporary files.
- Any all-in-one patch that mixes FBE, EAF, fixed demand, fixed renewables, fixed trade, and demand elasticity.

## Implementation Milestones

### Milestone 1: Clean Baseline Skeleton

Deliver:

- South Africa baseline config.
- South Africa data-contract document.
- Short-snapshot smoke-test command documented.

Exit criteria:

- The model can start from a clean upstream clone.
- A teammate can identify required data and run intent without old project history.

### Milestone 2: Demand And Validation

Deliver:

- Eskom demand preprocessing tool.
- Eskom generation validation utility.
- Minimal sample or schema-only test fixtures.

Exit criteria:

- Demand input passes completeness checks.
- A solved network can be compared to observed generation with clear diagnostics.

### Milestone 3: Capacity And Availability Realism

Deliver:

- Installed-capacity comparison.
- EAF preprocessing.
- Scenario-local capacity and cost assumption handling.

Exit criteria:

- The baseline can be assessed against capacity and availability evidence.
- EAF exists as validated input data, not yet as an opaque solver patch.

### Milestone 4: Historical Validation Mode

Deliver:

- Separate historical validation config.
- Optional fixed-demand, fixed-renewable, fixed-trade, and EAF integration choices if justified.

Exit criteria:

- Historical matching experiments are clearly separated from planning runs.
- Calibration settings are documented and reversible.

### Milestone 5: Reliability-Aware Planning

Deliver:

- Reliability-index data contract.
- Spatial allocation from reliability input to model buses or demand zones.
- Scenario design comparing reliability-neutral and reliability-aware planning.

Exit criteria:

- Reliability-aware results can be interpreted against a validated South Africa baseline.
- Investment shifts are attributable to explicit reliability assumptions, not hidden calibration artifacts.

## Agent Brief For Future Implementation

Give future agents this brief:

> You are starting from a clean upstream PyPSA-Earth clone. Do not inspect previous South Africa code. Use only the clean rebuild roadmap and current upstream conventions. Implement one milestone at a time. Keep every South Africa-specific assumption local, documented, and testable. Do not modify global defaults unless the change is a small generic fix that would be acceptable upstream.

## First Recommended Next Step

Build Milestone 1 first: the clean South Africa baseline config and data-contract document. Then immediately build demand preprocessing and Eskom validation. Do not start reliability-index implementation until those pieces exist.
