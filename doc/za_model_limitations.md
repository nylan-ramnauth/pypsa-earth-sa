# South Africa 2023 Baseline — Model Limitations

**Module:** 12 (dispatch calibration) / Pre-Module 13 acceptance boundary
**Accepted solve:** EAF-OPC-CAP
**Network:** `results/za_2023_fixed_validation/networks/elec_s_34_ec_lc1_NoCO2-1H-EAF-OPC-CAP.nc`
**Date accepted:** 2026-05-13

This document records the known, accepted residual errors in the South Africa 2023
dispatch calibration. Each section names the symptom, the diagnosed root cause, the
quantitative evidence, and whether the limitation is portable into capacity-expansion
or future-year runs (Module 14+). A reader who has never seen the codebase should be
able to use this document to decide whether the baseline is fit for their downstream
purpose.

The accepted solve is the fourth in a four-solve chain (`Structural` → `EAF` → `EAF+OPC`
→ `EAF+OPC+CAP`). The OCGT-diesel annual output cap of 5.5 TWh is applied through the
`pypsa-rsa` operational-constraints overlay (`HIGH_GAS` row). All 12 structural
acceptance gates pass on the accepted solve; the annual carrier-subtotal gate
(≤0.5% under `TOTAL_PHYSICAL_GENERATION`) fails at +4.19% and the residual drivers
are documented below.

---

## 1. PHS Dispatch (−96.6%)

**Symptom.** Pumped-hydro storage generates **147.15 GWh/year** in the accepted solve
versus Eskom 2023 actual **4,294 GWh/year**. Pumping is 196 GWh/year versus Eskom
~5,658 GWh/year. Implied annual cycle count ≈ 3.2 versus Eskom's ≈ 93.

**Diagnosis (A-III modified).** PHS is fully and correctly parameterized in the
network: 2,904 MW total p_nom (Drakensberg 1,000 + Ingula 1,324 + Palmiet 400 +
Steenbras 180), 60,700 MWh total energy capacity (max_hours ≈ 20–21 h),
marginal_cost = 0, cyclic_state_of_charge = True, round-trip efficiency = 0.866² ≈ 0.75.
SOC cycles the full 0 → 60,700 MWh range across the year. The cause is not a
parameter error.

The cause is structural to the LP formulation. The model dispatches PHS only on
energy arbitrage, and a coal-dominated flat-price stack does not generate price
spreads wide enough often enough to recover the 25% round-trip energy loss. Eskom in
practice dispatches PHS for reserves, frequency regulation, and ramping — services
that are not represented in the LP.

**Module 14 fix path.** Add an operating-reserves constraint to the LP, or replace
the PHS storage_unit with a deterministic operating profile derived from Eskom
hourly data. Both are model-design changes, not parameter calibrations.

**Expansion warning.** Capacity-expansion runs that build on this baseline will
systematically under-build VRE (and over-build mid-merit coal/gas) because the LP
sees no value in PHS-VRE pairing — the existing PHS is already nearly idle. Until
the reserves constraint or operating profile is added, this baseline is **not
suitable for storage-investment expansion runs**.

---

## 2. Wind Generation (−37.0%)

**Symptom.** Onshore wind generates **7,312 GWh/year** versus Eskom 2023 actual
**11,613 GWh/year**. Installed capacity matches: model 3,373 MW versus Eskom
anchor 3,400 MW.

**Diagnosis (B-II).** Capacity is correct; the gap is in realised capacity factor.
Model annual CF = **24.7%** versus Eskom realised CF = **39.0%**. This is a
systematic underperformance of the ERA5 cutout used to build the wind p_max_pu
profile, not a fleet error.

**Module 14 fix path.** Either (a) bias-correct the ERA5 cutout with measured
wind speeds, or (b) apply the documented annual scaling factor **1.58×** to the
wind p_max_pu profile as a calibration coefficient. Option (b) is the
quickest fix but is a calibration approximation: it will propagate into any
expansion run as a fixed multiplier and should be revisited if Atlite or a
bias-corrected cutout becomes available.

---

## 3. Solar PV Generation (−29.1%)

**Symptom.** Solar PV generates **3,557 GWh/year** versus Eskom 2023 actual
**5,015 GWh/year**. Installed capacity matches: model 2,288 MW versus Eskom
anchor 2,287 MW.

**Diagnosis (B-II).** Capacity correct; ERA5 cutout CF gap. Model CF = **17.8%**
versus Eskom realised CF = **25.0%**.

**Module 14 fix path.** Documented scaling factor **1.40×** on the solar p_max_pu
profile, or cutout bias-correction.

---

## 4. CSP Generation (−41.4%)

**Symptom.** CSP generates **806 GWh/year** versus Eskom 2023 actual **1,375 GWh/year**.
Installed capacity matches: model 500 MW versus Eskom anchor 500 MW (Kalahari 100 +
Kimberley 200 + Namaqualand 200).

**Diagnosis (B-II).** Capacity correct; CSP cutout CF gap is the largest of the
three VRE carriers. Model CF = **18.4%** versus Eskom realised CF = **31.4%**.
The 13-point gap likely reflects both DNI cutout quality and the TES (thermal
storage) operating heuristic, which is fixed in this baseline.

**Module 14 fix path.** Documented scaling factor **1.71×** on the CSP p_max_pu
profile. A more principled fix would re-derive DNI from a bias-corrected cutout and
re-tune the TES dispatch logic; this is deferred to a CSP-specific module.

---

## 5. Coal Over-dispatch (+11.3%)

**Symptom.** Coal generates **184,406 GWh/year** versus Eskom 2023 actual
**165,627 GWh/year** — an over-dispatch of **18,779 GWh** (+11.3%).

**Diagnosis (sensitivity decomposition).** The coal over-dispatch splits cleanly
into two components:

| Component | Magnitude | Share of coal over |
|---|---:|---:|
| Substitution artifact — coal filling PHS + VRE gaps | 10,475 GWh | ~56% |
| Genuine over-dispatch — EAF margin and merit-order ordering | 8,304 GWh | ~44% (≈ +5.0% of Eskom coal) |

The 10,475 GWh figure is the sum of the PHS gap (4,147 GWh) plus the wind
(4,301), solar (1,458), and CSP (570) gaps. If PHS and VRE were each at their
Eskom levels, coal would fall by approximately this amount and the residual
over-dispatch would be ≈ 8,304 GWh, or about +5.0% of Eskom coal annual.

**Module 14 fix path.** The substitution component closes automatically once PHS
and VRE are fixed (sections 1–4). The residual ~5% likely reflects EAF
availability slack and the LP marginal-cost ordering between coal units; addressing
it would require finer-grained EAF derate provenance and possibly a
unit-commitment formulation. Not separately fixable inside the calibration-plan
scope.

---

## 6. Hydro Annual Level and Seasonality (−29.8%)

**Symptom.** Reservoir hydro generates **1,398 GWh/year** versus Eskom 2023 actual
**1,992 GWh/year**. The seasonal profile is inverted relative to Eskom: model
peaks in winter, Eskom peaks in summer.

**Diagnosis.** The binding constraint is the ERA5 runoff inflow timeseries. Annual
modelled inflow is **1,649 GWh** versus Eskom annual hydro generation **1,992 GWh** —
ERA5 under-represents inflow by ~17%, which the inflow-limited LP propagates into
the dispatch output. The seasonal inversion reflects the same regional-rainfall
mismatch: South African hydro catchments are summer-rainfall regions, while ERA5
runoff over the relevant pixels skews to winter.

**Module 14 fix path.** Replace the inflow timeseries with a hydrology-based
product (e.g. WaterCROP) or with DWS gauging-station data aggregated to the model
buses. Not a parameter calibration — requires an input-data swap.

---

## 7. Load Shedding Under-estimate (−35.9%)

**Symptom.** Load shedding totals **10,748 GWh/year** versus Eskom 2023 actual
**16,755 GWh/year** — an under-estimate of **6,007 GWh** (−35.9%).

**Diagnosis.** Load shedding is the LP's last-resort response to insufficient
dispatchable supply. With PHS, wind, solar, and CSP all under-producing, coal
absorbs most of the shortfall, leaving load shedding below Eskom actuals. Load
shedding in the accepted solve is therefore an under-estimate of a system that
already has too much coal headroom; the symptom is downstream of the PHS and VRE
gaps, not an independent driver.

**Module 14 fix path.** Do **not** hard-code load-shedding to Eskom's annual
level. Fix the storage and VRE side first (sections 1–4); load shedding should
self-correct once coal headroom is removed.

---

## 8. Scarcity Timing — Calibration Claim Boundary

The model identifies the *timing* of system stress reasonably well. The weekly
Pearson correlation between model combined scarcity (OCGT + load shedding) and
Eskom combined scarcity is **r ≈ 0.73** (Spearman ρ ≈ 0.77), and the monthly
correlation is **r ≈ 0.85** (Spearman ρ ≈ 0.80). The accepted solve therefore
recovers Eskom's broad stress-period pattern.

The model does **not** recover the annual carrier mix correctly, as sections 1–7
document. The defensible calibration claim is therefore narrow: **the accepted
baseline is a planning model that captures the temporal alignment of system stress
periods within ~weekly resolution, but the annual energy contribution of each
carrier carries the documented errors and must not be quoted as a calibration
result.** Scarcity-timing claims (e.g. when load-shedding pressure peaks) are
defensible from this baseline; per-carrier annual energy claims are not.

---

## 9. Accepted Calibration Errors — Summary Table

| Carrier | Eskom GWh | Solve 4 GWh | Δ% | Diagnosis | Module 14 fix needed? |
|---|---:|---:|---:|---|---|
| Coal | 165,627 | 184,406 | +11.3% | Mostly substitution artifact (~56%); ~5% residual EAF/merit-order | Auto-closes after PHS+VRE fix; ~5% residual is open |
| OCGT | 5,243 | 5,500 | +4.9% | OCGT-diesel cap (5.5 TWh) binds; gap is within source uncertainty | No — accepted |
| PHS generation | 4,294 | 147 | −96.6% | A-III modified: LP energy-only arbitrage at 0.75 RTE; no reserves | **Yes — reserves constraint or operating profile (architectural)** |
| Wind | 11,613 | 7,312 | −37.0% | B-II: ERA5 CF 24.7% vs Eskom 39%; capacity matches | Yes — cutout bias correction or scaling 1.58× |
| Solar PV | 5,015 | 3,557 | −29.1% | B-II: ERA5 CF 17.8% vs 25%; capacity matches | Yes — cutout bias correction or scaling 1.40× |
| CSP | 1,375 | 806 | −41.4% | B-II: ERA5 CF 18.4% vs 31.4%; capacity matches | Yes — cutout + TES dispatch logic; scaling 1.71× as interim |
| Hydro | 1,992 | 1,398 | −29.8% | ERA5 runoff under-represents inflow (1,649 vs ~1,992 GWh); seasonal inversion | Yes — inflow timeseries replacement (input-data swap) |
| Load shedding | 16,755 | 10,748 | −35.9% | Downstream of PHS+VRE shortfall + coal headroom | Auto-closes after PHS+VRE fix |

All figures are annual 2023; Eskom values from `data/za_validation/eskom_2023_hourly_clean.csv`.
Diagnoses A-III-modified, B-II, and the coal sensitivity decomposition are derived
in `notebooks/za_validation/12_dispatch_calibration/pre_module13_investigation.ipynb`
(executed 2026-05-13).
