# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module 05 — System Boundary And Carrier Taxonomy.

Reads `za_local_carriers` and `za_system_boundary` from the active configfile,
emits the canonical machine-readable taxonomy CSV, and cross-checks every
distinct RSA carrier value present in the Module 04 fixed-tech audit against
the V1 mapping defined here.

Usage:
    snakemake --configfile configs/za/za_2023_fixed_validation.yaml build_za_carrier_taxonomy
or directly:
    python scripts/build_za_carrier_taxonomy.py --configfile configs/za/za_2023_fixed_validation.yaml
"""

import argparse
import csv
import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from za_audits.io import sha256_of_file  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("build_za_carrier_taxonomy")

DATA_AUDIT = Path("data/za_audit")
TAXONOMY_CSV = DATA_AUDIT / "za_carrier_taxonomy.csv"
CROSSCHECK_CSV = DATA_AUDIT / "za_carrier_taxonomy_crosscheck.csv"
FIXED_TECH_CSV = DATA_AUDIT / "pypsa_rsa_fixed_technologies_2023_candidates.csv"
SOURCE_HASHES = DATA_AUDIT / "source_hashes.csv"
INPUT_MANIFEST = DATA_AUDIT / "input_file_manifest.csv"
TAXONOMY_DOC = Path("doc/za_carrier_taxonomy.md")
SMOKE_SCRIPT = Path("scripts/za_validation/smoke_carrier_taxonomy.py")

# RSA → V1 carrier mapping. The mapping itself is the lock; module 05 owns
# this table and downstream modules consume it via the generated CSV. Module 12
# removes Sasol and the aggregate `other_re` artifact from the active baseline.
TAXONOMY_ROWS: list[dict] = [
    {"carrier_name": "coal",         "source_concept": "coal",                       "treatment": "upstream conventional generator", "component": "Generator",   "is_local": False, "owning_modules": "05|07|08", "notes": "Eskom coal fleet"},
    {"carrier_name": "nuclear",      "source_concept": "nuclear",                    "treatment": "upstream conventional generator", "component": "Generator",   "is_local": False, "owning_modules": "05|07|08", "notes": "Koeberg"},
    {"carrier_name": "ocgt_diesel",  "source_concept": "ocgt_diesel / diesel peaker","treatment": "local generator with explicit cost/emissions", "component": "Generator", "is_local": True,  "owning_modules": "05|07|08|10", "notes": "Ankerlig/Gourikwa diesel peakers"},
    {"carrier_name": "ocgt_gas",     "source_concept": "ocgt_avf / gas OCGT",        "treatment": "local generator with explicit cost/emissions", "component": "Generator", "is_local": True,  "owning_modules": "05|07|08|10", "notes": "AVF gas OCGT"},
    {"carrier_name": "onwind",       "source_concept": "wind",                       "treatment": "upstream renewable generator (atlite profile)", "component": "Generator", "is_local": False, "owning_modules": "05|03|08", "notes": "REIPPPP wind fleet"},
    {"carrier_name": "solar",        "source_concept": "solar PV",                   "treatment": "upstream renewable generator (atlite profile)", "component": "Generator", "is_local": False, "owning_modules": "05|03|08", "notes": "REIPPPP utility PV"},
    {"carrier_name": "csp",          "source_concept": "solar_csp / csp",            "treatment": "upstream renewable generator (atlite profile)", "component": "Generator", "is_local": False, "owning_modules": "05|03|08", "notes": "500 MW / 1.375 TWh anchor; never mapped to PV"},
    {"carrier_name": "hydro",        "source_concept": "reservoir hydro",            "treatment": "PyPSA-Earth hydro/reservoir-compatible", "component": "StorageUnit", "is_local": False, "owning_modules": "05|08", "notes": "Gariep / Vanderkloof"},
    {"carrier_name": "ror",          "source_concept": "run-of-river hydro",         "treatment": "PyPSA-Earth ror/hydro-compatible", "component": "Generator",   "is_local": False, "owning_modules": "05|08", "notes": "small RoR plants"},
    {"carrier_name": "PHS",          "source_concept": "pumped storage",             "treatment": "PyPSA-Earth storage-compatible PHS", "component": "StorageUnit", "is_local": False, "owning_modules": "05|08", "notes": "Drakensberg / Ingula; PHS energy checked"},
    {"carrier_name": "battery",      "source_concept": "battery",                    "treatment": "upstream Store; only 2023-active batteries that pass normalization", "component": "Store", "is_local": False, "owning_modules": "05|08", "notes": "include only after Module 08 reconciliation"},
    {"carrier_name": "biomass",      "source_concept": "biomass",                    "treatment": "excluded from V1 baseline until explicit expansion-compatible rows are sourced", "component": "Generator", "is_local": False, "owning_modules": "05|08|12", "notes": "bioenergy stays excluded; Eskom Other RE omission is quantified separately"},
]

# Optional V1 carriers handled outside the Generator carrier set:
# - hydro_import: exogenous load/import owned by module 06, not a domestic generator
# (kept as a row with is_local=False for documentation but excluded from
#  Generator-carrier crosscheck mapping).
SUPPLEMENTAL_ROWS: list[dict] = [
    {"carrier_name": "hydro_import", "source_concept": "hydro_import",               "treatment": "exogenous import time series, owned by module 06", "component": "Load", "is_local": False, "owning_modules": "05|06", "notes": "not a domestic hydro generator"},
]

# Map RSA-carrier strings (as found in pypsa-rsa scenario workbooks) to V1
# carrier names. Used by the crosscheck stage. Casing follows pypsa-rsa
# scenario workbook conventions.
RSA_TO_V1: dict[str, str] = {
    "coal":          "coal",
    "nuclear":       "nuclear",
    "ocgt_diesel":   "ocgt_diesel",
    "ocgt_avf":      "ocgt_gas",
    "ocgt_gas":      "ocgt_gas",
    "wind":          "onwind",
    "onwind":        "onwind",
    "solar":         "solar",
    "solar_pv":      "solar",
    "pv":            "solar",
    "solar_csp":     "csp",
    "csp":           "csp",
    "hydro":         "hydro",
    "ror":           "ror",
    "phs":           "PHS",
    "pumped_storage": "PHS",
    "battery":       "battery",
    "battery_4h":    "battery",
    "biomass":       "biomass",
    "bioenergy":     "biomass",
    "hydro_import":  "hydro_import",
}

# RSA-side labels that are NOT carriers in the V1 taxonomy. The crosscheck
# emits an explicit non-`resolved` status for these so they remain visible but
# do not violate the gate.
RSA_EXCLUDED_BY_BOUNDARY: set[str] = {
    "solar_pv_rooftop",  # embedded/rooftop PV excluded by za_system_boundary
    "sasol_coal",        # captive industrial generation removed before Module 12 baseline
    "sasol_gas",         # captive industrial generation removed before Module 12 baseline
    "other_re",          # aggregate accounting artifact removed; 238 GWh/yr omission logged
}
RSA_PENDING_MODULE_08: set[str] = {
    "rmippp",            # Risk Mitigation IPP procurement program — module 08 reconciles per-plant carrier
}


def _load_config(configfile: Path) -> dict:
    with open(configfile, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _local_metadata(config: dict, carrier_name: str) -> dict:
    blk = (config.get("za_local_carriers") or {}).get(carrier_name) or {}
    return {
        "color":                  blk.get("color", ""),
        "nice_name":              blk.get("nice_name", ""),
        "profile_intent":         blk.get("profile_intent", ""),
        "emissions_intent":       blk.get("emissions_intent", ""),
        "validation_target":      blk.get("validation_target", ""),
        "availability_treatment": blk.get("availability_treatment", ""),
    }


def build_taxonomy_csv(config: dict, out_path: Path) -> int:
    """Write the canonical taxonomy CSV. Returns row count."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "carrier_name", "source_concept", "treatment", "component", "is_local",
        "color", "nice_name", "profile_intent", "emissions_intent",
        "validation_target", "availability_treatment",
        "owning_modules", "notes",
    ]
    rows: list[dict] = []
    for r in TAXONOMY_ROWS + SUPPLEMENTAL_ROWS:
        meta = _local_metadata(config, r["carrier_name"]) if r["is_local"] else {
            "color": "", "nice_name": "", "profile_intent": "",
            "emissions_intent": "", "validation_target": "",
            "availability_treatment": "",
        }
        rows.append({
            "carrier_name":           r["carrier_name"],
            "source_concept":         r["source_concept"],
            "treatment":              r["treatment"],
            "component":              r["component"],
            "is_local":               str(bool(r["is_local"])).lower(),
            "color":                  meta["color"],
            "nice_name":              meta["nice_name"],
            "profile_intent":         meta["profile_intent"],
            "emissions_intent":       meta["emissions_intent"],
            "validation_target":      meta["validation_target"],
            "availability_treatment": meta["availability_treatment"],
            "owning_modules":         r["owning_modules"],
            "notes":                  r["notes"],
        })
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(out_path, index=False)
    return len(df)


def build_crosscheck_csv(fixed_tech_csv: Path, out_path: Path) -> int:
    """Cross-check every distinct RSA Carrier in the fixed-tech audit against the V1 mapping."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not fixed_tech_csv.exists():
        logger.warning("fixed-tech audit missing: %s — emitting empty crosscheck", fixed_tech_csv)
        pd.DataFrame(columns=["rsa_carrier", "count_in_audit", "mapped_v1_carrier", "status"]).to_csv(out_path, index=False)
        return 0

    df = pd.read_csv(fixed_tech_csv)
    if "Carrier" not in df.columns:
        logger.warning("'Carrier' column not present in fixed-tech audit — emitting empty crosscheck")
        pd.DataFrame(columns=["rsa_carrier", "count_in_audit", "mapped_v1_carrier", "status"]).to_csv(out_path, index=False)
        return 0

    counts = (
        df["Carrier"].fillna("").astype(str).str.strip().value_counts(dropna=False)
        .rename_axis("rsa_carrier").reset_index(name="count_in_audit")
    )
    counts = counts[counts["rsa_carrier"] != ""]

    rows: list[dict] = []
    for _, rec in counts.iterrows():
        raw = str(rec["rsa_carrier"])
        key = raw.strip().lower().replace("-", "_").replace(" ", "_")
        v1 = RSA_TO_V1.get(key, "")
        if v1:
            status = "resolved"
        elif key in RSA_EXCLUDED_BY_BOUNDARY:
            status = "excluded_by_boundary"
        elif key in RSA_PENDING_MODULE_08:
            status = "pending_module_08"
        else:
            status = "unresolved"
        rows.append({
            "rsa_carrier":         raw,
            "count_in_audit":      int(rec["count_in_audit"]),
            "mapped_v1_carrier":   v1,
            "status":              status,
        })
    out = pd.DataFrame(rows, columns=["rsa_carrier", "count_in_audit", "mapped_v1_carrier", "status"])
    out.to_csv(out_path, index=False)
    unresolved = (out["status"] == "unresolved").sum()
    if unresolved:
        logger.warning("crosscheck: %d unresolved RSA carriers (status='unresolved')", unresolved)
    return len(out)


def _append_provenance(taxonomy_csv: Path, crosscheck_csv: Path) -> None:
    """Append Module 05 outputs to source_hashes.csv and input_file_manifest.csv."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    if not now.endswith("CEST") and not now.endswith("CET"):
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M") + " local"

    artifacts = [
        ("za-carrier-taxonomy-csv",        "csv",      taxonomy_csv),
        ("za-carrier-taxonomy-crosscheck", "csv",      crosscheck_csv),
        ("za-carrier-taxonomy-doc",        "markdown", TAXONOMY_DOC),
        ("za-carrier-taxonomy-smoke",      "python",   SMOKE_SCRIPT),
    ]

    SOURCE_HASHES.parent.mkdir(parents=True, exist_ok=True)

    # source_hashes.csv append
    if SOURCE_HASHES.exists():
        with open(SOURCE_HASHES, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            for sid, stype, path in artifacts:
                h = sha256_of_file(path) if path.exists() else ""
                w.writerow([sid, stype, str(path), "sha256", h, "", now,
                            "Module 05 carrier taxonomy artifact"])

    # input_file_manifest.csv append
    if INPUT_MANIFEST.exists():
        with open(INPUT_MANIFEST, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            for sid, stype, path in artifacts:
                status = "present" if path.exists() else "missing"
                h = sha256_of_file(path) if path.exists() else ""
                w.writerow([sid, stype, str(path), status, h, "", now,
                            "Module 05 carrier taxonomy artifact"])


def _run(config: dict) -> int:
    DATA_AUDIT.mkdir(parents=True, exist_ok=True)
    n_tax = build_taxonomy_csv(config, TAXONOMY_CSV)
    n_x = build_crosscheck_csv(FIXED_TECH_CSV, CROSSCHECK_CSV)
    _append_provenance(TAXONOMY_CSV, CROSSCHECK_CSV)
    logger.info("Module 05 taxonomy: %d rows; crosscheck: %d rows", n_tax, n_x)
    return 0


def _main_from_snakemake() -> int:
    snakemake = globals().get("snakemake", None)
    if snakemake is None:
        return 2
    cfg = dict(snakemake.config)
    return _run(cfg)


if "snakemake" in globals():
    raise SystemExit(_main_from_snakemake())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configfile", required=True, type=Path)
    args = parser.parse_args()
    cfg = _load_config(args.configfile)
    raise SystemExit(_run(cfg))
