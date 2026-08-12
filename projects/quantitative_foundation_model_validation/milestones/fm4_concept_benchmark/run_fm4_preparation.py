#!/usr/bin/env python3
"""Prepare, but do not execute, the scope-capped FM4 concept benchmark."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist


ROOT = Path(__file__).resolve().parents[4]
STUDY = ROOT / "projects/quantitative_foundation_model_validation"
PRE = STUDY / "preexperiment"
RECORDS = PRE / "governance_records"
FM2 = STUDY / "milestones/fm2_paired_manifest/outputs"
FM3 = STUDY / "milestones/fm3_paired_embeddings/outputs"
OUT = Path(__file__).resolve().parent / "outputs"

SEED = 20260811
PRIMARY_FAMILY_ALPHA = 0.05
PRIMARY_TESTS = 2
BOOTSTRAP_REPLICATES = 2000
PERMUTATION_REPLICATES = 2000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def approximate_power(n_subjects: int, rho: float, per_test_alpha: float) -> float:
    """Two-sided Fisher-z planning approximation for a correlation test."""
    normal = NormalDist()
    z_critical = normal.inv_cdf(1 - per_test_alpha / 2)
    noncentrality = math.atanh(rho) * math.sqrt(n_subjects - 3)
    return 1 - normal.cdf(z_critical - noncentrality) + normal.cdf(-z_critical - noncentrality)


def minimum_detectable_rho(n_subjects: int, per_test_alpha: float, power: float = 0.80) -> float:
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - per_test_alpha / 2)
    z_power = normal.inv_cdf(power)
    return math.tanh((z_alpha + z_power) / math.sqrt(n_subjects - 3))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    g9 = json.loads((RECORDS / "g9_handoff_manifest.json").read_text(encoding="utf-8"))
    if g9.get("status") != "pass_clean_rerun_handoff":
        raise RuntimeError("P0-G9 clean rerun handoff has not passed")

    fm2_rows = read_csv(FM2 / "paired_sample_manifest.csv")
    fm3_rows = read_csv(FM3 / "embedding_row_manifest.csv")
    if len(fm2_rows) != 1218 or len(fm3_rows) != 1218:
        raise RuntimeError("FM2/FM3 paired row count is not 1,218")
    if [row["sample_id"] for row in fm2_rows] != [row["sample_id"] for row in fm3_rows]:
        raise RuntimeError("FM2/FM3 sample order mismatch")

    subjects = sorted({row["subject_id"] for row in fm2_rows})
    if len(subjects) != 25:
        raise RuntimeError("FM4 preparation requires the frozen 25-subject cohort")

    fold_source = read_csv(PRE / "fold_assignments.csv")
    fold_by_subject = {row["subject_id"]: row for row in fold_source}
    if set(subjects) != set(fold_by_subject):
        raise RuntimeError("frozen fold subjects do not match FM2")
    tile_counts = {subject: 0 for subject in subjects}
    nonzero_counts = {subject: 0 for subject in subjects}
    for row in fm2_rows:
        subject = row["subject_id"]
        tile_counts[subject] += 1
        nonzero_counts[subject] += float(row["tumor_fraction"]) > 0
        if str(row["fold"]) != str(fold_by_subject[subject]["fold"]):
            raise RuntimeError(f"fold mismatch for {subject}")

    fold_manifest = [
        {
            "subject_id": subject,
            "outer_fold": int(fold_by_subject[subject]["fold"]),
            "assignment_seed": SEED,
            "assignment_method": fold_by_subject[subject]["assignment_method"],
            "paired_tiles": tile_counts[subject],
            "nonzero_truth_tiles": nonzero_counts[subject],
            "shared_by_encoders": True,
            "status": "frozen_pre_outcome_reuse_from_P0",
        }
        for subject in subjects
    ]
    write_csv(OUT / "fm4_shared_fold_manifest.csv", fold_manifest)

    family_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        family_rows.append(
            {
                "family_id": "FM4-H1-TUMOR-SHARED",
                "target": "tumor_fraction",
                "target_role": "T2_descriptive_only_not_confirmatory",
                "encoder": encoder,
                "physical_fov_um": 394.24,
                "analysis_unit": "subject_mean",
                "estimand": "Spearman(truth_subject_mean, OOF_prediction_subject_mean)",
                "outcome_role": "primary_exploratory",
                "reference_null": "subject_label_permutation",
                "family_multiplicity": "BH_FDR_across_two_encoder_associations",
                "family_alpha": PRIMARY_FAMILY_ALPHA,
                "bootstrap_unit": "subject",
                "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                "permutation_replicates": PERMUTATION_REPLICATES,
                "claim_ceiling": "internal_descriptive_recoverability_only",
            }
        )
    for encoder in ("CONCH", "Virchow"):
        for estimand, unit in (
            ("MAE(truth, OOF_prediction)", "subject_mean"),
            ("R2(truth, OOF_prediction)", "subject_mean"),
            ("Spearman(truth, OOF_prediction)", "tile_clustered_by_subject"),
        ):
            family_rows.append(
                {
                    "family_id": "FM4-H1-TUMOR-SHARED-SECONDARY",
                    "target": "tumor_fraction",
                    "target_role": "T2_descriptive_only_not_confirmatory",
                    "encoder": encoder,
                    "physical_fov_um": 394.24,
                    "analysis_unit": unit,
                    "estimand": estimand,
                    "outcome_role": "secondary_descriptive",
                    "reference_null": "none" if not estimand.startswith("Spearman") else "within_subject_coordinate_permutation",
                    "family_multiplicity": "not_used_for_gate",
                    "family_alpha": "",
                    "bootstrap_unit": "subject",
                    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                    "permutation_replicates": PERMUTATION_REPLICATES if estimand.startswith("Spearman") else 0,
                    "claim_ceiling": "internal_descriptive_recoverability_only",
                }
            )
    write_csv(OUT / "analysis_family.csv", family_rows)

    per_test_alpha = PRIMARY_FAMILY_ALPHA / PRIMARY_TESTS
    power_rows = []
    for n_subjects in (25, 40, 60, 100):
        power_rows.append(
            {
                "scenario": "available" if n_subjects == 25 else "planning_reference",
                "n_subjects": n_subjects,
                "family_tests": PRIMARY_TESTS,
                "family_alpha": PRIMARY_FAMILY_ALPHA,
                "planning_correction": "Bonferroni_conservative_approximation_for_BH_FDR_family",
                "per_test_alpha": per_test_alpha,
                "minimum_detectable_abs_rho_80pct_power": round(minimum_detectable_rho(n_subjects, per_test_alpha), 4),
                "power_if_abs_rho_0_3": round(approximate_power(n_subjects, 0.3, per_test_alpha), 4),
                "power_if_abs_rho_0_4": round(approximate_power(n_subjects, 0.4, per_test_alpha), 4),
                "power_if_abs_rho_0_5": round(approximate_power(n_subjects, 0.5, per_test_alpha), 4),
                "power_if_abs_rho_0_6": round(approximate_power(n_subjects, 0.6, per_test_alpha), 4),
                "interpretation": "feasibility_only_large_effects" if n_subjects == 25 else "future_cohort_reference",
            }
        )
    write_csv(OUT / "power_precision_plan.csv", power_rows)

    checklist = [
        ("P0-G9 clean rerun", "met", "56/56 deterministic artifacts matched"),
        ("FM2 common membership and truth", "met", "1,218 paired tiles; 25 subjects; mismatch 0"),
        ("FM3 paired embedding bundle", "met", "CONCH and Virchow row-aligned clean arrays"),
        ("target/FOV scope", "met", "tumor_fraction; shared 394.24um; descriptive only"),
        ("shared grouped folds", "met", "five subject-grouped folds frozen with seed 20260811"),
        ("analysis family and multiplicity", "prepared", "two primary encoder associations; BH-FDR 0.05"),
        ("power adequacy", "limited", "n=25 detects only large |rho| approximately 0.58 at 80% power"),
        ("measurement repeatability", "not_met", "independent repeat measurement/ICC unavailable"),
        ("independent metric-endpoint pair for H2", "not_met", "PRECISE disease endpoint linkage unavailable"),
        ("research-lead FM4 scope approval", "pending", "required before benchmark execution"),
    ]
    write_csv(
        OUT / "fm4_entry_checklist.csv",
        [{"requirement": a, "status": b, "evidence_or_consequence": c} for a, b, c in checklist],
    )

    available = power_rows[0]
    report = [
        "# FM4 concept benchmark entry decision",
        "",
        "- Status: **PREPARED — research-lead scope approval required before execution**",
        "- Recommendation: **approve a limited exploratory/descriptive FM4 benchmark**",
        "- Target: `T2 tumor_fraction` only",
        "- Encoders: `CONCH` and `Virchow`, paired at shared `394.24 µm` FOV",
        "- Cohort: 1,218 tiles from 25 subjects; five shared subject-grouped folds",
        "- Primary estimand: subject-mean OOF Spearman for each encoder",
        "- Primary family: two encoder associations, grouped permutations, BH-FDR 0.05",
        "- Uncertainty: 2,000 subject bootstraps; undefined replicates retained",
        "",
        "## Power/precision interpretation",
        "",
        f"With 25 subjects, a conservative two-test planning approximation gives an 80% power minimum detectable |rho| of about **{available['minimum_detectable_abs_rho_80pct_power']:.2f}**. The available cohort is therefore a feasibility sample for large effects, not a confirmatory sample for moderate effects or small encoder differences.",
        "",
        "## What approval would unlock",
        "",
        "- One locked exploratory H1 benchmark using the frozen FM2/FM3 samples, folds and embeddings",
        "- Saved tile-level OOF predictions, subject-level aggregation, fold diagnostics, grouped permutation nulls and subject bootstrap replicates",
        "- A descriptive paired cross-encoder delta, explicitly not an encoder-superiority test",
        "",
        "## What remains prohibited",
        "",
        "- confirmatory target designation or measurement-validity claim",
        "- disease prediction, H2 functional-utilization or complementarity analysis",
        "- clinical/whole-slide PNI inference",
        "- scanner/stain robustness or encoder-superiority inference",
        "- external transport claim",
        "",
        "Approval cannot repair the absent repeatability, independent disease endpoint, adequate events or external cohort. A `Revise` decision should specify a changed estimand/family before any benchmark is run.",
    ]
    (OUT / "FM4_ENTRY_DECISION.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    config = {
        "schema_version": "fm4-preparation-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "prepared_pending_research_lead_scope_approval",
        "execution_authorized": False,
        "seed": SEED,
        "counts": {"paired_tiles": 1218, "subjects": 25, "outer_folds": 5, "encoders": 2, "targets": 1},
        "probe": {
            "family": "ridge_linear_probe",
            "outer_split": "five_fold_subject_grouped_shared",
            "inner_tuning": "training_subjects_only",
            "primary_estimand": "subject_mean_oof_spearman",
            "permutation_replicates": PERMUTATION_REPLICATES,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "source_hashes": {
            "g9_handoff_manifest.json": sha256(RECORDS / "g9_handoff_manifest.json"),
            "paired_sample_manifest.csv": sha256(FM2 / "paired_sample_manifest.csv"),
            "embedding_bundle_manifest.csv": sha256(FM3 / "embedding_bundle_manifest.csv"),
            "embedding_row_manifest.csv": sha256(FM3 / "embedding_row_manifest.csv"),
            "fold_assignments.csv": sha256(PRE / "fold_assignments.csv"),
        },
        "output_hashes_excluding_run_config": {
            path.name: sha256(path)
            for path in sorted(OUT.iterdir())
            if path.is_file() and path.name != "run_config.json"
        },
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": config["status"], **config["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
