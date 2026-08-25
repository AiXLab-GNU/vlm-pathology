#!/usr/bin/env python3
"""Auditable P0 inventory and approved source-control qualification.

The pre-g0 stage reads immutable/local sources and rebuilds the P0-M0--M2
evidence tables. P0-G0 was approved before predictive results were generated.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from importlib.util import find_spec
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage, stats
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, log_loss, mean_absolute_error, r2_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import tifffile


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(os.environ.get("P0_OUTPUT_DIR", Path(__file__).resolve().parent)).resolve()
OUT.mkdir(parents=True, exist_ok=True)
PROTOCOL_ID = "P0-QFMV-2026-08-11-APPROVED-001"
APPROVAL = {
    "status": "approved",
    "approver": "Jin Hyun Kim",
    "role": "PM",
    "timestamp_utc": "2026-08-11T19:17:36Z",
}
SEED = 20260811
EXPECTED_CLINICIAN_SHA256 = (
    "c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3"
)

TABLE_SCHEMAS: dict[str, list[str]] = {
    "source_inventory.csv": [
        "source_id", "cohort", "category", "path", "resolved_path", "exists",
        "size_bytes", "sha256_pre", "sha256_post", "pre_post_match", "immutable",
        "rows", "columns", "array_shape", "array_dtype", "role", "notes",
    ],
    "metric_eligibility.tsv": [
        "metric_id", "metric_name", "metric_role", "analysis_unit", "reference_source",
        "independence_from_model", "measurement_status", "allowed_role", "unit",
        "denominator", "repeatability", "missing_reason", "decision_rationale",
        "required_action",
    ],
    "measurement_provenance.csv": [
        "metric_id", "source_path", "source_type", "source_version_or_hash",
        "measurement_algorithm", "algorithm_version", "fixed_before_outcome_analysis",
        "annotator_or_validator", "validation_evidence", "provenance_status", "notes",
    ],
    "common_sample_manifest.csv": [
        "cohort_id", "endpoint_id", "analysis_unit", "grouping_unit", "sample_id",
        "subject_id", "slide_id", "conch_present", "virchow_present", "conch_truth",
        "virchow_truth", "truth_source_path", "truth_status", "label_match",
        "subject_linkage_status", "eligibility_status", "notes",
    ],
    "membership_mismatch.csv": [
        "cohort_id", "endpoint_id", "sample_id", "conch_present", "virchow_present",
        "membership_status", "conch_exclusion_reason", "virchow_exclusion_reason",
        "truth_value", "truth_source_path", "expected_sampling_universe", "notes",
    ],
    "truth_mismatch.csv": [
        "cohort_id", "endpoint_id", "sample_id", "conch_truth", "virchow_truth",
        "source_truth", "mismatch_type", "resolution_status", "notes",
    ],
    "leakage_audit.csv": [
        "cohort_id", "endpoint_id", "analysis_unit", "grouping_unit", "n_samples",
        "n_groups", "n_duplicate_sample_ids", "n_groups_with_multiple_samples",
        "n_groups_crossing_folds", "serial_section_status", "subject_linkage_status",
        "assessment_status", "predictive_use_allowed", "notes",
    ],
    "exclusion_flow.csv": [
        "cohort_id", "endpoint_id", "stage", "reason_code", "n_samples", "n_groups",
        "retained_for", "notes",
    ],
    "claim_evidence_matrix.csv": [
        "claim_id", "claim", "claim_level", "status", "required_evidence",
        "current_evidence", "allowed_wording", "prohibited_wording", "owner",
    ],
    "deviation_log.csv": [
        "deviation_id", "milestone", "severity", "category", "observed", "expected",
        "impact", "required_action", "status", "evidence",
    ],
    "p0_gate_matrix.csv": [
        "gate_id", "milestone", "gate_question", "status", "draft_decision",
        "entry_condition_met", "direct_evidence", "unresolved_risk", "next_unlocked",
        "still_prohibited", "approver", "approval_timestamp",
    ],
    "main_study_unlock_matrix.csv": [
        "main_stage", "current_status", "required_p0_gate", "additional_requirement",
        "currently_allowed", "currently_prohibited", "evidence",
    ],
}

M3_SCHEMAS: dict[str, list[str]] = {
    "existing_oof_predictions.csv": [
        "endpoint_id", "encoder", "config_id", "sample_id", "group_id", "fold",
        "truth", "outcome_time", "prediction", "prediction_status",
        "selected_hyperparameter", "source_embedding_sha256", "fold_manifest_sha256",
    ],
    "existing_common_sample_results.csv": [
        "endpoint_id", "encoder", "config_id", "analysis_unit", "metric_name",
        "estimate", "ci_low", "ci_high", "n_samples", "n_groups",
        "n_valid_bootstrap", "n_undefined_bootstrap", "permutation_p95",
        "empirical_p", "empirical_q", "gate_exceedance",
    ],
    "existing_paired_deltas.csv": [
        "endpoint_id", "config_id", "metric_name", "conch_estimate",
        "virchow_estimate", "paired_delta", "ci_low", "ci_high", "n_valid",
        "n_undefined",
    ],
    "existing_permutation_null.csv": [
        "endpoint_id", "encoder", "config_id", "replicate_id", "permutation_seed",
        "metric_name", "estimate", "replicate_status", "undefined_reason",
    ],
    "existing_bootstrap_replicates.csv": [
        "endpoint_id", "encoder", "config_id", "replicate_id", "bootstrap_seed",
        "metric_name", "estimate", "replicate_status", "undefined_reason",
    ],
}

M4_SCHEMAS: dict[str, list[str]] = {
    "paired_tile_manifest.csv": [
        "tile_id", "subject_id", "session_id", "image_id", "fold", "he_path",
        "mask_path", "level0_x0", "level0_y0", "level0_x1", "level0_y1",
        "center_x", "center_y", "native_mpp_x", "native_mpp_y", "crop_px",
        "physical_fov_um", "physical_fov_error_um", "target_mask_level",
        "target_level_x0", "target_level_y0", "target_level_x1", "target_level_y1",
        "conch_input_px", "virchow_input_px", "same_boundary_for_both_models",
        "overlaps_locked_pni_focus", "inclusion_status", "exclusion_reason",
    ],
    "quantitative_targets.csv": [
        "tile_id", "subject_id", "image_id", "fold", "n_mask_pixels",
        "n_valid_biological_pixels", "n_tumor_pixels", "n_stroma_pixels",
        "n_artifact_pixels", "valid_biological_fraction", "artifact_fraction",
        "tumor_fraction", "stroma_fraction", "tumor_target_status",
        "stroma_target_status", "missing_reason",
    ],
    "tile_qc.csv": [
        "tile_id", "subject_id", "image_id", "fold", "mask_shape_match",
        "mask_labels_valid", "he_qc_level", "he_qc_width", "he_qc_height",
        "brightness_mean", "grayscale_sd", "laplacian_variance", "saturation_mean",
        "high_saturation_fraction", "dark_fold_fraction", "blue_pen_fraction",
        "green_pen_fraction", "he_qc_status", "qc_exclusion_applied",
    ],
    "fold_assignments.csv": [
        "subject_id", "fold", "assignment_seed", "assignment_method", "n_sessions",
        "n_inventory_tiles", "n_tumor_eligible_tiles",
    ],
    "target_availability.csv": [
        "target_id", "target_role", "scope", "fold", "n_sessions", "n_subjects",
        "n_inventory_tiles", "n_evaluable_tiles", "n_missing_tiles", "minimum",
        "q25", "median", "q75", "maximum", "n_unique_rounded_6dp",
        "subject_floor_met", "fold_floor_met", "variation_present", "gate_relevance",
    ],
    "pni_focus_overlap_audit.csv": [
        "candidate_id", "subject_id", "image_id", "focus_x0", "focus_y0",
        "focus_x1", "focus_y1", "n_overlapping_inventory_tiles",
        "n_overlapping_eligible_before_exclusion", "exclusion_verified",
    ],
}

M5_SCHEMAS: dict[str, list[str]] = {
    "paired_embedding_manifest.csv": [
        "embedding_row", "tile_id", "subject_id", "image_id", "fold",
        "inclusion_status", "level0_x0", "level0_y0", "level0_x1", "level0_y1",
        "physical_fov_um", "same_boundary_for_both_models", "conch_input_px",
        "virchow_input_px", "conch_crop_sha256", "virchow_crop_sha256",
        "crop_hash_match", "conch_embedding_status", "virchow_embedding_status",
    ],
    "embedding_determinism_audit.csv": [
        "encoder", "tile_id", "audit_order", "first_feature_sha256",
        "second_feature_sha256", "exact_equal", "max_abs_difference",
        "all_finite", "deterministic_algorithms_enabled", "batch_size",
    ],
    "embedding_technical_qc.csv": [
        "encoder", "model_id", "model_revision", "weights_sha256", "output_file",
        "output_sha256", "expected_rows", "observed_rows", "expected_dimension",
        "observed_dimension", "dtype", "n_nonfinite_values", "n_zero_norm_rows",
        "norm_min", "norm_median", "norm_max", "n_duplicate_tile_ids",
        "paired_tile_ids_match", "crop_hashes_match", "determinism_exact",
        "technical_status",
    ],
}

M5_BATCH_SIZE = {"conch": 8, "virchow": 8}
M5_DIMENSION = {"conch": 512, "virchow": 2560}
M5_ARRAY_FILE = {
    "conch": "precise_conch_shared_fov_embeddings.npy",
    "virchow": "precise_virchow_shared_fov_embeddings.npy",
}

M6_SCHEMAS: dict[str, list[str]] = {
    "concept_oof_predictions.csv": [
        "target_id", "encoder", "tile_id", "subject_id", "image_id", "fold",
        "embedding_row", "truth", "prediction", "prediction_status",
        "selected_alpha", "source_embedding_file", "source_embedding_sha256",
        "paired_manifest_sha256", "fold_assignment_sha256",
    ],
    "concept_summary.csv": [
        "target_id", "target_role", "encoder", "analysis_unit", "metric_name",
        "estimate", "ci_low", "ci_high", "n_tiles", "n_subjects",
        "n_valid_bootstrap", "n_undefined_bootstrap", "permutation_null_type",
        "permutation_p95", "empirical_p", "empirical_q", "gate_exceedance",
    ],
    "concept_paired_deltas.csv": [
        "target_id", "analysis_unit", "metric_name", "conch_estimate",
        "virchow_estimate", "paired_delta_conch_minus_virchow", "ci_low",
        "ci_high", "n_valid_bootstrap", "n_undefined_bootstrap", "direction_note",
    ],
    "concept_permutation_null.csv": [
        "target_id", "encoder", "null_type", "analysis_unit", "replicate_id",
        "permutation_seed", "metric_name", "estimate", "replicate_status",
        "undefined_reason",
    ],
    "concept_bootstrap_replicates.csv": [
        "target_id", "encoder", "analysis_unit", "replicate_id", "bootstrap_seed",
        "metric_name", "estimate", "replicate_status", "undefined_reason",
    ],
    "concept_fold_diagnostics.csv": [
        "target_id", "encoder", "fold", "selected_alpha", "n_train_tiles",
        "n_test_tiles", "n_train_subjects", "n_test_subjects", "train_target_min",
        "train_target_max", "test_target_min", "test_target_max", "train_mae",
        "test_mae", "train_r2", "test_r2", "train_spearman", "test_spearman",
        "spearman_generalization_gap", "diagnostic_status",
    ],
}

M6_ALPHA_GRID = np.logspace(-4, 4, 17)
M6_N_PERMUTATIONS = 2000
M6_N_BOOTSTRAPS = 2000

M7_SCHEMAS: dict[str, list[str]] = {
    "m7_native_fov_manifest.csv": [
        "embedding_row", "tile_id", "subject_id", "image_id", "fold", "he_path",
        "center_x", "center_y", "native_mpp_x", "native_mpp_y", "level0_x0",
        "level0_y0", "level0_x1", "level0_y1", "crop_px", "physical_fov_um",
        "physical_fov_error_um", "crop_sha256", "embedding_status",
    ],
    "m7_native_embedding_qc.csv": [
        "encoder", "fov_um", "output_file", "output_sha256", "expected_rows",
        "observed_rows", "expected_dimension", "observed_dimension", "dtype",
        "n_nonfinite_values", "n_zero_norm_rows", "determinism_exact",
        "manifest_rows", "unique_tile_ids", "source_hashes_match", "technical_status",
    ],
    "m7_native_determinism_audit.csv": [
        "configuration", "tile_id", "audit_order", "first_feature_sha256",
        "second_feature_sha256", "exact_equal", "max_abs_difference", "all_finite",
        "batch_size",
    ],
    "m7_native_oof_predictions.csv": [
        "configuration", "tile_id", "subject_id", "fold", "truth", "prediction",
        "selected_alpha", "source_embedding_sha256", "prediction_status",
    ],
    "representation_similarity.csv": [
        "representation_a", "representation_b", "analysis_unit", "n_units",
        "metric_name", "estimate", "interpretation_limit",
    ],
    "scale_sampling_sensitivity.csv": [
        "configuration", "encoder", "fov_um", "sensitivity_type", "tile_budget",
        "draw_id", "sampling_seed", "analysis_unit", "metric_name", "estimate",
        "n_tiles", "n_subjects", "direction_positive", "paired_draw_id",
    ],
    "zero_inflation_sensitivity.csv": [
        "configuration", "encoder", "analysis_subset", "analysis_unit",
        "metric_name", "estimate", "ci_low", "ci_high", "n_tiles", "n_subjects",
        "zero_fraction", "interpretation",
    ],
    "qc_sensitivity.csv": [
        "encoder", "qc_variable", "analysis_type", "stratum", "threshold_low",
        "threshold_high", "n_tiles", "n_subjects", "metric_name", "estimate",
        "direction_positive", "qc_dominance_flag", "assessment_status",
    ],
    "discordance_manifest.csv": [
        "tile_id", "subject_id", "image_id", "fold", "truth", "conch_prediction",
        "virchow_prediction", "conch_residual", "virchow_residual",
        "conch_absolute_error", "virchow_absolute_error",
        "absolute_error_delta_conch_minus_virchow", "prediction_difference",
        "discordance_class", "brightness_mean", "grayscale_sd",
        "laplacian_variance", "saturation_mean", "valid_biological_fraction",
        "artifact_fraction", "native_mpp_x",
    ],
    "discordance_qc_associations.csv": [
        "qc_variable", "metric_name", "estimate", "n_tiles", "n_subjects",
        "association_direction", "large_association_flag", "assessment_status",
    ],
}

M7_NATIVE_FOV_UM = 98.56
M7_SAMPLING_BUDGETS = (4, 8, 16, 32)
M7_N_SAMPLING_DRAWS = 20
M7_QC_VARIABLES = (
    "brightness_mean", "grayscale_sd", "laplacian_variance", "saturation_mean",
    "valid_biological_fraction", "artifact_fraction", "native_mpp_x",
)

M8_SCHEMAS: dict[str, list[str]] = {
    "integrated_gate_summary.csv": [
        "gate_id", "milestone", "status", "decision", "entry_condition_met",
        "evidence", "unresolved_risk", "m8_effect",
    ],
    "p0_question_answer_matrix.csv": [
        "question_id", "question", "minimum_answer_form", "integrated_answer",
        "status", "evidence", "claim_limit",
    ],
    "model_target_fov_decision.csv": [
        "combination_id", "model", "target", "input_fov_um", "target_window_fov_um",
        "target_role", "evidence_status", "m8_recommendation", "currently_allowed",
        "currently_prohibited", "unresolved_requirement", "evidence",
    ],
    "unresolved_risk_register.csv": [
        "risk_id", "source_deviation", "severity", "scope", "observed", "impact",
        "required_before_main", "disposition", "owner", "evidence",
    ],
}


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalized_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def normalized_id(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return str(value)


def package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in (
        "numpy", "pandas", "scikit-learn", "scipy", "torch", "torchvision", "timm",
        "tifffile", "Pillow", "openpyxl", "huggingface-hub",
    ):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not_installed"
    return result


def git_context() -> dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status_lines = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {
        "commit": commit,
        "worktree_dirty": bool(status_lines),
        "n_status_lines_at_start": len(status_lines),
        "note": "Pre-existing user changes were preserved; this run writes only the P0 directory.",
    }


def model_snapshot_root(encoder: str) -> Path:
    """Resolve the repository-local reconstruction cache before the historical cache."""
    repository_cache = (
        ROOT
        / "resources/projects/quantitative_foundation_model_validation/model_cache"
        / encoder
    )
    if repository_cache.is_dir():
        return repository_cache
    hf_root = Path.home() / ".cache/huggingface-jhkim/hub"
    if encoder == "conch":
        return hf_root / (
            "models--MahmoodLab--conch/snapshots/"
            "f9ca9f877171a28ade80228fb195ac5d79003357"
        )
    if encoder == "virchow":
        return hf_root / (
            "models--paige-ai--Virchow/snapshots/"
            "19eebc84ae33e79f1b2d866e6ff90ae50e522f9a"
        )
    raise ValueError(f"unknown encoder: {encoder}")


def source_specs() -> list[dict[str, object]]:
    conch_snapshot = model_snapshot_root("conch")
    virchow_snapshot = model_snapshot_root("virchow")
    legacy_conch_code = (
        ROOT
        / "resources/projects/prostate_biomarker_validation/model_workspace/CONCH"
        / "conch/open_clip_custom/model_configs/conch_ViT-B-16.json"
    )
    conch_package = find_spec("conch")
    installed_conch_code = (
        Path(conch_package.origin).parent
        / "open_clip_custom/model_configs/conch_ViT-B-16.json"
        if conch_package and conch_package.origin
        else Path("__conch_package_not_installed__")
    )
    conch_model_config = (
        installed_conch_code if installed_conch_code.is_file() else legacy_conch_code
    )
    specs: list[dict[str, object]] = [
        {"source_id": "nadt_truth", "cohort": "NADT-Prostate", "category": "truth",
         "path": ROOT / "resources/data/shared/opendataset/NADT-Prostate_v1/Biopsy-Clinical-Data.xlsx",
         "immutable": True, "role": "source truth"},
        {"source_id": "nadt_conch_grade_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta.csv", "immutable": True, "role": "CONCH membership/truth cache"},
        {"source_id": "nadt_virchow_grade_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/meta.csv", "immutable": True, "role": "Virchow membership/truth cache"},
        {"source_id": "nadt_conch_phenotype_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta_phenotype.csv", "immutable": True, "role": "CONCH membership/truth cache"},
        {"source_id": "nadt_virchow_phenotype_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/meta_phenotype.csv", "immutable": True, "role": "Virchow membership/truth cache"},
        {"source_id": "nadt_conch_grade_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/X.npy", "immutable": True, "role": "P0-M3 reusable embedding"},
        {"source_id": "nadt_virchow_grade_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/X.npy", "immutable": True, "role": "P0-M3 reusable embedding"},
        {"source_id": "nadt_conch_phenotype_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/X_phenotype.npy", "immutable": True, "role": "P0-M3 reusable embedding"},
        {"source_id": "nadt_virchow_phenotype_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/X_phenotype.npy", "immutable": True, "role": "P0-M3 reusable embedding"},
        {"source_id": "nadt_conch_native_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/meta_s0_mpp0.88.csv", "immutable": True, "role": "P0-M3 fixed native configuration metadata"},
        {"source_id": "nadt_virchow_native_meta", "cohort": "NADT-Prostate", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/meta_s0_mpp0.44.csv", "immutable": True, "role": "P0-M3 fixed native configuration metadata"},
        {"source_id": "nadt_conch_native_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/tile_embeddings_s0_mpp0.88.npy", "immutable": True, "role": "P0-M3 first-16-tile frozen embedding"},
        {"source_id": "nadt_virchow_native_embedding", "cohort": "NADT-Prostate", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/tile_embeddings_s0_mpp0.44.npy", "immutable": True, "role": "P0-M3 first-16-tile frozen embedding"},
        {"source_id": "panda_truth", "cohort": "PANDA", "category": "truth",
         "path": ROOT / "resources/data/shared/opendataset/PANDA_extracted/train.csv", "immutable": True, "role": "source truth"},
        {"source_id": "panda_conch_meta", "cohort": "PANDA", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/meta_panda.csv", "immutable": True, "role": "CONCH membership/truth cache"},
        {"source_id": "panda_virchow_meta", "cohort": "PANDA", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache/meta_panda.csv", "immutable": True, "role": "Virchow membership/truth cache"},
        {"source_id": "panda_conch_embedding", "cohort": "PANDA", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/X_panda.npy", "immutable": True, "role": "existing output"},
        {"source_id": "panda_virchow_embedding", "cohort": "PANDA", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache/X_panda.npy", "immutable": True, "role": "existing output"},
        {"source_id": "tcga_conch_native_meta", "cohort": "TCGA-PRAD", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/meta_s0_mpp0.88.csv", "immutable": True, "role": "P0-M3 CONCH source-control membership/truth"},
        {"source_id": "tcga_virchow_native_meta", "cohort": "TCGA-PRAD", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/meta_s0_mpp0.44.csv", "immutable": True, "role": "P0-M3 Virchow source-control membership/truth"},
        {"source_id": "tcga_conch_native_embedding", "cohort": "TCGA-PRAD", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/tile_embeddings_s0_mpp0.88.npy", "immutable": True, "role": "P0-M3 native-FOV sensitivity embedding"},
        {"source_id": "tcga_virchow_native_embedding", "cohort": "TCGA-PRAD", "category": "embedding_cache",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/tile_embeddings_s0_mpp0.44.npy", "immutable": True, "role": "P0-M3 native-FOV sensitivity embedding"},
        {"source_id": "leopard_conch_recurrence_oof", "cohort": "LEOPARD", "category": "historical_oof",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/direct_recurrence_oof.csv", "immutable": True, "role": "P0-M3 locked recurrence control"},
        {"source_id": "leopard_virchow_recurrence_oof", "cohort": "LEOPARD", "category": "historical_oof",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/direct_recurrence_oof.csv", "immutable": True, "role": "P0-M3 locked recurrence control"},
        {"source_id": "leopard_conch_meta", "cohort": "LEOPARD", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/meta.csv", "immutable": True, "role": "P0-M2 recurrence membership/truth"},
        {"source_id": "leopard_virchow_meta", "cohort": "LEOPARD", "category": "cache_metadata",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/meta.csv", "immutable": True, "role": "P0-M2 recurrence membership/truth"},
        {"source_id": "stability_grid_spec", "cohort": "multi-cohort", "category": "design",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv", "immutable": True, "role": "existing stability design"},
        {"source_id": "stability_cell_results", "cohort": "multi-cohort", "category": "result",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv", "immutable": True, "role": "existing stability result"},
        {"source_id": "stability_fold_results", "cohort": "multi-cohort", "category": "result",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv", "immutable": True, "role": "existing fold result"},
        {"source_id": "stability_fold_assignments", "cohort": "multi-cohort", "category": "design",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv", "immutable": True, "role": "subject/case grouped folds"},
        {"source_id": "stability_coordinate_manifest", "cohort": "multi-cohort", "category": "manifest",
         "path": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv", "immutable": True, "role": "coordinate/hash manifest"},
        {"source_id": "precise_participants", "cohort": "PRECISE", "category": "truth",
         "path": ROOT / "resources/data/shared/opendataset/PRECISE/participants.csv", "immutable": True, "role": "subject/session metadata"},
        {"source_id": "precise_readme", "cohort": "PRECISE", "category": "provenance_metadata",
         "path": ROOT / "resources/data/shared/opendataset/PRECISE/README.md", "immutable": True, "role": "dataset structure and annotator roles"},
        {"source_id": "precise_label_descriptions", "cohort": "PRECISE", "category": "annotation_metadata",
         "path": ROOT / "resources/data/shared/opendataset/PRECISE/label_descriptions.json", "immutable": True, "role": "mask label map"},
        {"source_id": "precise_pni_cross_project_manifest", "cohort": "PRECISE", "category": "governance_manifest",
         "path": ROOT / "resources/data/manifests/precise_pni_cross_project_inputs.yaml", "immutable": True, "role": "explicit hash-locked cross-project dependency contract"},
        {"source_id": "precise_clinician_review", "cohort": "PRECISE", "category": "clinician_source",
         "path": ROOT / "resources/data/precise_pni_candidate_triage/pathologist_reviews/candidate_review/precise_pni_review (1).csv", "immutable": True, "role": "unrelated immutable PNI source boundary"},
        {"source_id": "precise_locked_morphology_review", "cohort": "PRECISE", "category": "exclusion_manifest",
         "path": ROOT / "resources/artifacts/precise_pni_candidate_triage/morphology_rereview/locked/normalized_morphology_review.csv", "immutable": True, "role": "14 locked PNI-focus exclusion rectangles"},
        {"source_id": "conch_weights", "cohort": "model", "category": "model_weight",
         "path": conch_snapshot / "pytorch_model.bin", "immutable": True, "role": "frozen CONCH weights"},
        {"source_id": "conch_metadata", "cohort": "model", "category": "model_metadata",
         "path": conch_snapshot / "meta.yaml", "immutable": True, "role": "CONCH snapshot metadata"},
        {"source_id": "conch_model_config", "cohort": "model", "category": "model_config",
         "path": conch_model_config,
         "immutable": True, "role": "CONCH architecture/input config"},
        {"source_id": "virchow_weights", "cohort": "model", "category": "model_weight",
         "path": virchow_snapshot / "model.safetensors", "immutable": True, "role": "frozen Virchow weights"},
        {"source_id": "virchow_config", "cohort": "model", "category": "model_config",
         "path": virchow_snapshot / "config.json", "immutable": True, "role": "Virchow architecture/preprocessing config"},
    ]
    masks = sorted((ROOT / "resources/data/shared/opendataset/PRECISE/extracted/data").glob(
        "sub-*/ses-*/wsi_h-e/*_mask.ome.tif"
    ))
    for index, mask in enumerate(masks, start=1):
        he = Path(str(mask).replace("_mask.ome.tif", ".ome.tif"))
        specs.append({
            "source_id": f"precise_he_{index:02d}", "cohort": "PRECISE",
            "category": "whole_slide_image", "path": he, "immutable": True,
            "role": "P0-M4 paired physical-boundary and technical-QC source",
        })
        specs.append({
            "source_id": f"precise_mask_{index:02d}", "cohort": "PRECISE",
            "category": "pixel_annotation", "path": mask, "immutable": True,
            "role": "candidate independent quantitative target source",
        })
    return specs


def inspect_source(spec: dict[str, object], pre_hash: str) -> dict[str, object]:
    path = Path(spec["path"])
    rows: object = ""
    columns: object = ""
    array_shape: object = ""
    array_dtype: object = ""
    notes = ""
    if path.exists() and path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
        rows, columns = len(frame), "|".join(frame.columns)
    elif path.exists() and path.suffix.lower() == ".npy":
        array = np.load(path, mmap_mode="r")
        array_shape, array_dtype = json.dumps(list(array.shape)), str(array.dtype)
        rows = int(array.shape[0])
    elif path.exists() and path.suffix.lower() == ".json":
        parsed = json.loads(path.read_text())
        columns = "|".join(map(str, parsed.keys())) if isinstance(parsed, dict) else ""
    elif path.exists() and path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
        rows, columns = len(frame), "|".join(frame.columns.astype(str))
    if spec["source_id"] == "precise_clinician_review":
        notes = (
            "expected immutable hash matched"
            if pre_hash == EXPECTED_CLINICIAN_SHA256
            else "STOP: immutable clinician hash mismatch"
        )
    return {
        "source_id": spec["source_id"], "cohort": spec["cohort"],
        "category": spec["category"], "path": relative_or_absolute(path),
        "resolved_path": str(path.resolve()) if path.exists() else "", "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else "", "sha256_pre": pre_hash,
        "sha256_post": "", "pre_post_match": "", "immutable": spec["immutable"],
        "rows": rows, "columns": columns, "array_shape": array_shape,
        "array_dtype": array_dtype, "role": spec["role"], "notes": notes,
    }


def parse_gleason_total(value: object) -> float:
    match = re.match(r"\s*(\d)\s*\+\s*(\d)\s*=\s*(\d+)", str(value))
    return float(match.group(3)) if match else np.nan


def panda_subsample(frame: pd.DataFrame, cap: int = 100, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    parts = []
    for _, group in frame.groupby(["data_provider", "isup_grade"]):
        if len(group) > cap:
            indices = rng.choice(group.index.to_numpy(), size=cap, replace=False)
            parts.append(frame.loc[indices])
        else:
            parts.append(group)
    return pd.concat(parts, ignore_index=True)


def conch_panda_skip_reasons() -> dict[str, str]:
    path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache_run.log"
    reasons: dict[str, str] = {}
    if not path.exists():
        return reasons
    pattern = re.compile(r"\[skip\]\s+(.+?):\s+([0-9a-f]{32})$")
    for line in path.read_text(errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            reasons[match.group(2)] = match.group(1).strip().replace(" ", "_")
    return reasons


def build_membership_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    common_rows: list[dict[str, object]] = []
    mismatch_rows: list[dict[str, object]] = []
    truth_rows: list[dict[str, object]] = []
    leakage_rows: list[dict[str, object]] = []
    exclusion_rows: list[dict[str, object]] = []

    nadt_source = pd.read_excel(ROOT / "resources/data/shared/opendataset/NADT-Prostate_v1/Biopsy-Clinical-Data.xlsx")
    grade_source = nadt_source[
        (nadt_source["Stain"] == "H&E") & (nadt_source["Phenotype"] == "TUMOR")
    ].copy()
    grade_source["source_truth"] = grade_source["Gleason Score"].map(parse_gleason_total)
    grade_lookup = grade_source.set_index("File Name")
    conch_grade = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta.csv")
    virchow_grade = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/meta.csv")
    merged_grade = conch_grade.merge(
        virchow_grade, on="file_name", suffixes=("_conch", "_virchow"), validate="one_to_one"
    )
    for row in merged_grade.sort_values("file_name").itertuples(index=False):
        source_truth = grade_lookup.loc[row.file_name, "source_truth"]
        source_subject = normalized_id(grade_lookup.loc[row.file_name, "Patient ID"])
        matches = (
            normalized_id(row.patient_id_conch) == normalized_id(row.patient_id_virchow)
            == source_subject
            and float(row.gleason_total_conch) == float(row.gleason_total_virchow) == source_truth
        )
        common_rows.append({
            "cohort_id": "NADT-Prostate", "endpoint_id": "gleason_total",
            "analysis_unit": "slide", "grouping_unit": "subject", "sample_id": row.file_name,
            "subject_id": source_subject, "slide_id": row.file_name, "conch_present": True,
            "virchow_present": True, "conch_truth": row.gleason_total_conch,
            "virchow_truth": row.gleason_total_virchow,
            "truth_source_path": "resources/data/shared/opendataset/NADT-Prostate_v1/Biopsy-Clinical-Data.xlsx",
            "truth_status": "source_reconciled" if matches else "mismatch", "label_match": matches,
            "subject_linkage_status": "verified_from_source", "eligibility_status": "common",
            "notes": "multiple biopsy/core slides remain clustered by subject",
        })
        if not matches:
            truth_rows.append({
                "cohort_id": "NADT-Prostate", "endpoint_id": "gleason_total",
                "sample_id": row.file_name, "conch_truth": row.gleason_total_conch,
                "virchow_truth": row.gleason_total_virchow, "source_truth": source_truth,
                "mismatch_type": "truth_or_subject", "resolution_status": "unresolved", "notes": "",
            })
    exclusion_rows.extend([
        {"cohort_id": "NADT-Prostate", "endpoint_id": "gleason_total", "stage": "source_tumor_h&e",
         "reason_code": "source_universe", "n_samples": len(grade_source),
         "n_groups": grade_source["Patient ID"].nunique(), "retained_for": "eligibility audit", "notes": ""},
        {"cohort_id": "NADT-Prostate", "endpoint_id": "gleason_total", "stage": "excluded",
         "reason_code": "nonparseable_metastatic_gleason", "n_samples": int(grade_source.source_truth.isna().sum()),
         "n_groups": grade_source.loc[grade_source.source_truth.isna(), "Patient ID"].nunique(),
         "retained_for": "exclusion accounting", "notes": "not converted to a numeric or negative label"},
        {"cohort_id": "NADT-Prostate", "endpoint_id": "gleason_total", "stage": "common",
         "reason_code": "included_both_models", "n_samples": len(merged_grade),
         "n_groups": merged_grade.patient_id_conch.nunique(), "retained_for": "P0-M3 source control", "notes": ""},
    ])

    phenotype_source = nadt_source[nadt_source["Stain"] == "H&E"].copy()
    phenotype_source["source_truth"] = phenotype_source["Phenotype"].map({"BENIGN": 0, "TUMOR": 1})
    phenotype_lookup = phenotype_source.set_index("File Name")
    conch_pheno = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta_phenotype.csv")
    virchow_pheno = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/meta_phenotype.csv")
    merged_pheno = conch_pheno.merge(
        virchow_pheno, on="file_name", suffixes=("_conch", "_virchow"), validate="one_to_one"
    )
    for row in merged_pheno.sort_values("file_name").itertuples(index=False):
        source_truth = phenotype_lookup.loc[row.file_name, "source_truth"]
        source_subject = normalized_id(phenotype_lookup.loc[row.file_name, "Patient ID"])
        matches = (
            normalized_id(row.patient_id_conch) == normalized_id(row.patient_id_virchow)
            == source_subject
            and float(row.label_conch) == float(row.label_virchow) == source_truth
        )
        common_rows.append({
            "cohort_id": "NADT-Prostate", "endpoint_id": "tumor_vs_benign",
            "analysis_unit": "slide", "grouping_unit": "subject", "sample_id": row.file_name,
            "subject_id": source_subject, "slide_id": row.file_name, "conch_present": True,
            "virchow_present": True, "conch_truth": row.label_conch,
            "virchow_truth": row.label_virchow,
            "truth_source_path": "resources/data/shared/opendataset/NADT-Prostate_v1/Biopsy-Clinical-Data.xlsx",
            "truth_status": "source_reconciled" if matches else "mismatch", "label_match": matches,
            "subject_linkage_status": "verified_from_source", "eligibility_status": "common",
            "notes": "HGPIN/ATYPICAL/PIN were excluded, not converted to benign",
        })
        if not matches:
            truth_rows.append({
                "cohort_id": "NADT-Prostate", "endpoint_id": "tumor_vs_benign",
                "sample_id": row.file_name, "conch_truth": row.label_conch,
                "virchow_truth": row.label_virchow, "source_truth": source_truth,
                "mismatch_type": "truth_or_subject", "resolution_status": "unresolved", "notes": "",
            })
    for phenotype, count in phenotype_source.loc[phenotype_source.source_truth.isna(), "Phenotype"].value_counts().items():
        excluded = phenotype_source[phenotype_source["Phenotype"] == phenotype]
        exclusion_rows.append({
            "cohort_id": "NADT-Prostate", "endpoint_id": "tumor_vs_benign", "stage": "excluded",
            "reason_code": f"nonbinary_phenotype_{str(phenotype).lower()}", "n_samples": int(count),
            "n_groups": excluded["Patient ID"].nunique(), "retained_for": "exclusion accounting",
            "notes": "not converted to benign/no",
        })
    exclusion_rows.extend([
        {"cohort_id": "NADT-Prostate", "endpoint_id": "tumor_vs_benign", "stage": "source_h&e",
         "reason_code": "source_universe", "n_samples": len(phenotype_source),
         "n_groups": phenotype_source["Patient ID"].nunique(), "retained_for": "eligibility audit", "notes": ""},
        {"cohort_id": "NADT-Prostate", "endpoint_id": "tumor_vs_benign", "stage": "common",
         "reason_code": "included_both_models", "n_samples": len(merged_pheno),
         "n_groups": merged_pheno.patient_id_conch.nunique(), "retained_for": "P0-M3 source control", "notes": ""},
    ])

    panda_truth = pd.read_csv(ROOT / "resources/data/shared/opendataset/PANDA_extracted/train.csv", dtype={"image_id": str})
    expected = panda_subsample(panda_truth, cap=100, seed=0).set_index("image_id")
    conch_panda = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/meta_panda.csv", dtype={"image_id": str})
    virchow_panda = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache/meta_panda.csv", dtype={"image_id": str})
    conch_by_id = conch_panda.set_index("image_id")
    virchow_by_id = virchow_panda.set_index("image_id")
    common_ids = sorted(set(conch_by_id.index) & set(virchow_by_id.index))
    for image_id in common_ids:
        conch_row = conch_by_id.loc[image_id]
        virchow_row = virchow_by_id.loc[image_id]
        source_row = expected.loc[image_id]
        fields_match = all(
            normalized_text(conch_row[field]) == normalized_text(virchow_row[field])
            == normalized_text(source_row[field])
            for field in ("data_provider", "isup_grade", "gleason_score")
        )
        common_rows.append({
            "cohort_id": "PANDA", "endpoint_id": "isup_grade", "analysis_unit": "image/case",
            "grouping_unit": "image/case (subject link unavailable)", "sample_id": image_id,
            "subject_id": "", "slide_id": image_id, "conch_present": True,
            "virchow_present": True, "conch_truth": conch_row.isup_grade,
            "virchow_truth": virchow_row.isup_grade,
            "truth_source_path": "resources/data/shared/opendataset/PANDA_extracted/train.csv",
            "truth_status": "source_reconciled" if fields_match else "mismatch",
            "label_match": fields_match, "subject_linkage_status": "not_available",
            "eligibility_status": "common_membership_only",
            "notes": (
                "tile-count mismatch between encoders"
                if int(conch_row.n_tiles) != int(virchow_row.n_tiles)
                else "tile count matches; coordinates still not recorded"
            ),
        })
        if not fields_match:
            truth_rows.append({
                "cohort_id": "PANDA", "endpoint_id": "isup_grade", "sample_id": image_id,
                "conch_truth": conch_row.isup_grade, "virchow_truth": virchow_row.isup_grade,
                "source_truth": source_row.isup_grade, "mismatch_type": "truth",
                "resolution_status": "unresolved", "notes": "",
            })

    conch_skip = conch_panda_skip_reasons()
    expected_ids = set(expected.index)
    conch_ids, virchow_ids = set(conch_by_id.index), set(virchow_by_id.index)
    for image_id in sorted(expected_ids - set(common_ids)):
        conch_present, virchow_present = image_id in conch_ids, image_id in virchow_ids
        if conch_present and not virchow_present:
            status = "conch_only"
        elif virchow_present and not conch_present:
            status = "virchow_only"
        else:
            status = "neither_model"
        mismatch_rows.append({
            "cohort_id": "PANDA", "endpoint_id": "isup_grade", "sample_id": image_id,
            "conch_present": conch_present, "virchow_present": virchow_present,
            "membership_status": status,
            "conch_exclusion_reason": "" if conch_present else conch_skip.get(image_id, "not_recorded"),
            "virchow_exclusion_reason": "" if virchow_present else "not_recorded_missing_execution_log",
            "truth_value": expected.loc[image_id, "isup_grade"],
            "truth_source_path": "resources/data/shared/opendataset/PANDA_extracted/train.csv",
            "expected_sampling_universe": "deterministic 1,200-image provider×ISUP capped sample",
            "notes": "model-exclusive samples retained; no negative imputation",
        })
    status_counts = pd.Series([row["membership_status"] for row in mismatch_rows]).value_counts()
    exclusion_rows.extend([
        {"cohort_id": "PANDA", "endpoint_id": "isup_grade", "stage": "expected_sample",
         "reason_code": "deterministic_stratified_universe", "n_samples": len(expected),
         "n_groups": "", "retained_for": "membership audit", "notes": "100 per provider×ISUP cell cap, seed 0"},
        {"cohort_id": "PANDA", "endpoint_id": "isup_grade", "stage": "common",
         "reason_code": "included_both_models", "n_samples": len(common_ids), "n_groups": "",
         "retained_for": "image/case-level audit", "notes": "not called patients"},
        {"cohort_id": "PANDA", "endpoint_id": "isup_grade", "stage": "model_specific",
         "reason_code": "conch_only", "n_samples": int(status_counts.get("conch_only", 0)),
         "n_groups": "", "retained_for": "mismatch accounting", "notes": ""},
        {"cohort_id": "PANDA", "endpoint_id": "isup_grade", "stage": "model_specific",
         "reason_code": "virchow_only", "n_samples": int(status_counts.get("virchow_only", 0)),
         "n_groups": "", "retained_for": "mismatch accounting", "notes": ""},
        {"cohort_id": "PANDA", "endpoint_id": "isup_grade", "stage": "excluded_both",
         "reason_code": "neither_model", "n_samples": int(status_counts.get("neither_model", 0)),
         "n_groups": "", "retained_for": "exclusion accounting", "notes": "CONCH reason logged; Virchow reason unavailable"},
    ])

    tcga_conch = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/meta_s0_mpp0.88.csv")
    tcga_virchow = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/meta_s0_mpp0.44.csv")
    tcga = tcga_conch.merge(
        tcga_virchow, on="file_name", suffixes=("_conch", "_virchow"), validate="one_to_one"
    )
    for endpoint in ("pten", "spop", "ar"):
        for row in tcga.sort_values("file_name").itertuples(index=False):
            conch_truth = getattr(row, f"{endpoint}_conch")
            virchow_truth = getattr(row, f"{endpoint}_virchow")
            case_match = normalized_text(row.case_id_conch) == normalized_text(row.case_id_virchow)
            truth_match = (
                (pd.isna(conch_truth) and pd.isna(virchow_truth))
                or normalized_text(conch_truth) == normalized_text(virchow_truth)
            )
            matches = case_match and truth_match
            common_rows.append({
                "cohort_id": "TCGA-PRAD", "endpoint_id": endpoint,
                "analysis_unit": "slide", "grouping_unit": "case",
                "sample_id": row.file_name, "subject_id": row.case_id_conch,
                "slide_id": row.file_name, "conch_present": True, "virchow_present": True,
                "conch_truth": conch_truth, "virchow_truth": virchow_truth,
                "truth_source_path": "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/{encoder}/meta_s0_mpp{native}.csv",
                "truth_status": "cross_cache_reconciled" if matches else "mismatch",
                "label_match": matches, "subject_linkage_status": "case_id_available",
                "eligibility_status": "common" if matches and pd.notna(conch_truth) else "common_missing_truth",
                "notes": "multiple slides grouped by case; encoder-native FOVs differ",
            })
            if not matches:
                truth_rows.append({
                    "cohort_id": "TCGA-PRAD", "endpoint_id": endpoint,
                    "sample_id": row.file_name, "conch_truth": conch_truth,
                    "virchow_truth": virchow_truth, "source_truth": "",
                    "mismatch_type": "truth_or_case", "resolution_status": "unresolved", "notes": "",
                })
        exclusion_rows.append({
            "cohort_id": "TCGA-PRAD", "endpoint_id": endpoint, "stage": "common",
            "reason_code": "included_both_models", "n_samples": len(tcga),
            "n_groups": tcga.case_id_conch.nunique(), "retained_for": "P0-M3 source control",
            "notes": "native FOV sensitivity only",
        })

    leopard_conch = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/direct_recurrence_oof.csv")
    leopard_virchow = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/direct_recurrence_oof.csv")
    leopard = leopard_conch.merge(
        leopard_virchow, on="case_id", suffixes=("_conch", "_virchow"), validate="one_to_one"
    )
    for row in leopard.sort_values("case_id").itertuples(index=False):
        matches = all(
            np.isclose(getattr(row, f"{field}_conch"), getattr(row, f"{field}_virchow"), equal_nan=True)
            for field in ("event", "follow_up_years", "n_tiles")
        )
        truth_text_conch = f"event={row.event_conch};time={row.follow_up_years_conch}"
        truth_text_virchow = f"event={row.event_virchow};time={row.follow_up_years_virchow}"
        common_rows.append({
            "cohort_id": "LEOPARD", "endpoint_id": "recurrence",
            "analysis_unit": "case", "grouping_unit": "case", "sample_id": row.case_id,
            "subject_id": row.case_id, "slide_id": row.case_id, "conch_present": True,
            "virchow_present": True, "conch_truth": truth_text_conch,
            "virchow_truth": truth_text_virchow,
            "truth_source_path": "resources/projects/prostate_biomarker_validation/model_workspace/leopard_{encoder}_cache/meta.csv and direct_recurrence_oof.csv",
            "truth_status": "cross_cache_reconciled" if matches else "mismatch",
            "label_match": matches, "subject_linkage_status": "case_id_available",
            "eligibility_status": "common", "notes": "locked historical OOF risk; 5-fold KFold seed 0",
        })
        if not matches:
            truth_rows.append({
                "cohort_id": "LEOPARD", "endpoint_id": "recurrence", "sample_id": row.case_id,
                "conch_truth": truth_text_conch, "virchow_truth": truth_text_virchow,
                "source_truth": "", "mismatch_type": "survival_truth",
                "resolution_status": "unresolved", "notes": "",
            })
    exclusion_rows.append({
        "cohort_id": "LEOPARD", "endpoint_id": "recurrence", "stage": "common",
        "reason_code": "included_both_models", "n_samples": len(leopard),
        "n_groups": leopard.case_id.nunique(), "retained_for": "P0-M3 source control",
        "notes": "locked historical direct-recurrence OOF",
    })

    for endpoint, frame in (("gleason_total", merged_grade), ("tumor_vs_benign", merged_pheno)):
        patient_col = "patient_id_conch"
        leakage_rows.append({
            "cohort_id": "NADT-Prostate", "endpoint_id": endpoint, "analysis_unit": "slide",
            "grouping_unit": "subject", "n_samples": len(frame), "n_groups": frame[patient_col].nunique(),
            "n_duplicate_sample_ids": int(frame.file_name.duplicated().sum()),
            "n_groups_with_multiple_samples": int((frame.groupby(patient_col).size() > 1).sum()),
            "n_groups_crossing_folds": 0, "serial_section_status": "multiple core/slide records grouped by subject",
            "subject_linkage_status": "verified", "assessment_status": "pass_for_membership_and_existing_folds",
            "predictive_use_allowed": "after P0-G0 and P0-G2 approval",
            "notes": "existing fold assignments are one row per marker-case",
        })
    panda_common = pd.DataFrame([row for row in common_rows if row["cohort_id"] == "PANDA"])
    leakage_rows.append({
        "cohort_id": "PANDA", "endpoint_id": "isup_grade", "analysis_unit": "image/case",
        "grouping_unit": "unknown subject", "n_samples": len(panda_common), "n_groups": "",
        "n_duplicate_sample_ids": int(panda_common.sample_id.duplicated().sum()),
        "n_groups_with_multiple_samples": "", "n_groups_crossing_folds": "",
        "serial_section_status": "not_assessable", "subject_linkage_status": "not_available",
        "assessment_status": "incomplete_subject_leakage_not_assessable",
        "predictive_use_allowed": "no patient-level or split-based claim",
        "notes": "PANDA may be used only as an image/case membership and truth audit until linkage is verified",
    })
    for endpoint in ("pten", "spop", "ar"):
        leakage_rows.append({
            "cohort_id": "TCGA-PRAD", "endpoint_id": endpoint, "analysis_unit": "slide",
            "grouping_unit": "case", "n_samples": len(tcga),
            "n_groups": tcga.case_id_conch.nunique(),
            "n_duplicate_sample_ids": int(tcga.file_name.duplicated().sum()),
            "n_groups_with_multiple_samples": int((tcga.groupby("case_id_conch").size() > 1).sum()),
            "n_groups_crossing_folds": 0, "serial_section_status": "multiple slides grouped by case",
            "subject_linkage_status": "case_id_available", "assessment_status": "pass",
            "predictive_use_allowed": "P0-M3 source control only",
            "notes": "same fixed case fold used for both encoders; native FOVs differ",
        })
    leakage_rows.append({
        "cohort_id": "LEOPARD", "endpoint_id": "recurrence", "analysis_unit": "case",
        "grouping_unit": "case", "n_samples": len(leopard), "n_groups": leopard.case_id.nunique(),
        "n_duplicate_sample_ids": int(leopard.case_id.duplicated().sum()),
        "n_groups_with_multiple_samples": 0, "n_groups_crossing_folds": 0,
        "serial_section_status": "one record per case", "subject_linkage_status": "case_id_available",
        "assessment_status": "pass_historical_locked_oof",
        "predictive_use_allowed": "P0-M3 recurrence control only",
        "notes": "historical KFold n=5, shuffle=True, seed=0 reconstructed from locked row order",
    })

    assignments = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv", dtype={"case_id": str})
    for (marker, cohort), part in assignments.groupby(["marker", "canonical_cohort"], sort=True):
        crossings = int((part.groupby("case_id").fold.nunique() > 1).sum())
        leakage_rows.append({
            "cohort_id": cohort, "endpoint_id": marker, "analysis_unit": "subject/case",
            "grouping_unit": "subject/case", "n_samples": len(part), "n_groups": part.case_id.nunique(),
            "n_duplicate_sample_ids": int(part.duplicated(["case_id"]).sum()),
            "n_groups_with_multiple_samples": 0, "n_groups_crossing_folds": crossings,
            "serial_section_status": "grouped upstream", "subject_linkage_status": "case_id available",
            "assessment_status": "pass" if crossings == 0 else "fail",
            "predictive_use_allowed": "after P0-G0/G2; P0-M3 refit still requires grouped permutation",
            "notes": "fold rows are not independent validation samples",
        })

    return (
        pd.DataFrame(common_rows, columns=TABLE_SCHEMAS["common_sample_manifest.csv"]),
        pd.DataFrame(mismatch_rows, columns=TABLE_SCHEMAS["membership_mismatch.csv"]),
        pd.DataFrame(truth_rows, columns=TABLE_SCHEMAS["truth_mismatch.csv"]),
        pd.DataFrame(leakage_rows, columns=TABLE_SCHEMAS["leakage_audit.csv"]),
        pd.DataFrame(exclusion_rows, columns=TABLE_SCHEMAS["exclusion_flow.csv"]),
    )


def metric_tables(mask_hashes: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask_hash_summary = hashlib.sha256("".join(sorted(mask_hashes)).encode()).hexdigest()
    valid_tissue = "labels {1,2,4,5,6,7}; background 0 and artifact 3 excluded"
    rows = [
        {
            "metric_id": "p0.precise.tumor_fraction", "metric_name": "tumor fraction",
            "metric_role": "biological_feature", "analysis_unit": "tile",
            "reference_source": "PRECISE provided pixel annotation mask, label 1",
            "independence_from_model": "independent_of_CONCH_and_Virchow",
            "measurement_status": "ready_for_descriptive_feasibility_repeatability_not_quantified",
            "allowed_role": "descriptive_primary_candidate_not_confirmatory",
            "unit": "fraction [0,1]", "denominator": valid_tissue,
            "repeatability": "fixed-mask calculation is deterministic; quantitative interobserver/repeatability coefficient not reported",
            "missing_reason": "zero valid-tissue denominator or missing/corrupt mask",
            "decision_rationale": "two expert uropathologists, three-stage consensus, and IHC boundary reference establish independence and QA",
            "required_action": "obtain quantitative repeatability evidence before confirmatory-primary use",
        },
        {
            "metric_id": "p0.precise.nuclear_density_mm2", "metric_name": "nuclear density/mm²",
            "metric_role": "biological_feature", "analysis_unit": "tile",
            "reference_source": "none found", "independence_from_model": "unresolved",
            "measurement_status": "deferred", "allowed_role": "deferred_not_primary",
            "unit": "nuclei/mm²", "denominator": "valid tissue area in mm²",
            "repeatability": "not established", "missing_reason": "no fixed independent detector and no manual validation subset",
            "decision_rationale": "P0 primary eligibility condition is not met",
            "required_action": "lock detector/version and provide manual-count or approved validation evidence",
        },
        {
            "metric_id": "p0.precise.gland_lumen_fraction", "metric_name": "gland/lumen fraction",
            "metric_role": "biological_feature", "analysis_unit": "tile",
            "reference_source": "none found; PRECISE class 2 is benign gland tissue, not a lumen contour",
            "independence_from_model": "unresolved", "measurement_status": "deferred",
            "allowed_role": "deferred_not_primary", "unit": "fraction [0,1]",
            "denominator": "valid tissue pixels after a future locked definition",
            "repeatability": "not established", "missing_reason": "no expert lumen annotation or validated fixed segmentation",
            "decision_rationale": "a tissue-class mask cannot be silently reinterpreted as lumen segmentation",
            "required_action": "provide expert annotation or independent validated segmentation with failure log",
        },
        {
            "metric_id": "p0.precise.stroma_fraction", "metric_name": "stroma fraction",
            "metric_role": "biological_feature", "analysis_unit": "tile",
            "reference_source": "PRECISE provided pixel annotation mask, label 7",
            "independence_from_model": "independent_of_CONCH_and_Virchow",
            "measurement_status": "exploratory_algorithm_assisted_stroma_fill",
            "allowed_role": "exploratory_not_confirmatory_secondary", "unit": "fraction [0,1]",
            "denominator": valid_tissue,
            "repeatability": "fixed-mask calculation is deterministic; public utility documents automatic unlabeled-tissue stroma fill",
            "missing_reason": "zero valid-tissue denominator or missing/corrupt mask",
            "decision_rationale": "class 7 is encoder-independent but algorithm-assisted and lacks separate validation/repeatability evidence",
            "required_action": "validate and version the stroma-fill algorithm before secondary confirmatory use",
        },
        {
            "metric_id": "p0.precise.he_texture", "metric_name": "H&E texture entropy/homogeneity",
            "metric_role": "biological_feature", "analysis_unit": "tile",
            "reference_source": "deterministic H&E image calculation",
            "independence_from_model": "independent_if_algorithm_locked_before analysis",
            "measurement_status": "exploratory_pending_algorithm_lock", "allowed_role": "exploratory_or_secondary_only",
            "unit": "algorithm-specific", "denominator": "valid H&E tissue pixels",
            "repeatability": "requires scanner/stain/MPP and quantization sensitivity audit",
            "missing_reason": "failed image/QC or insufficient valid tissue",
            "decision_rationale": "texture is scale/color sensitive and is not a primary biological truth",
            "required_action": "lock grayscale/color preprocessing, offsets, bins, directions, and aggregation",
        },
        {
            "metric_id": "p0.precise.tissue_valid_fraction", "metric_name": "tissue/valid-pixel fraction",
            "metric_role": "quality_control", "analysis_unit": "tile",
            "reference_source": "PRECISE mask plus image QC", "independence_from_model": "independent",
            "measurement_status": "ready_as_QC_after_denominator_lock", "allowed_role": "QC_only",
            "unit": "fraction [0,1]", "denominator": "all pixels in the fixed physical tile",
            "repeatability": "deterministic from fixed mask/QC implementation",
            "missing_reason": "missing/corrupt mask or image", "decision_rationale": "not a biological endpoint",
            "required_action": "lock tissue labels, artifact handling, and minimum QC threshold",
        },
    ]
    provenance = []
    for row in rows:
        uses_mask = "mask" in row["reference_source"].lower()
        item = {
            "metric_id": row["metric_id"],
            "source_path": (
                "resources/data/shared/opendataset/PRECISE/extracted/data/sub-*/ses-*/wsi_h-e/*_mask.ome.tif"
                if uses_mask else "not_available_or_algorithm_to_be_locked"
            ),
            "source_type": "provided_pixel_annotation" if uses_mask else "algorithm_or_missing",
            "source_version_or_hash": mask_hash_summary if uses_mask else "",
            "measurement_algorithm": "direct label fraction" if uses_mask else "not_locked",
            "algorithm_version": PROTOCOL_ID if uses_mask else "",
            "fixed_before_outcome_analysis": "approved_yes" if uses_mask else "no",
            "annotator_or_validator": "not applicable or not documented",
            "validation_evidence": row["repeatability"],
            "provenance_status": row["measurement_status"], "notes": row["required_action"],
        }
        if row["metric_id"] == "p0.precise.tumor_fraction":
            item["source_path"] += "; https://zenodo.org/records/20721779 (v1)"
            item["annotator_or_validator"] = "two expert uropathologists; structured three-stage consensus"
            item["validation_evidence"] = "IHC used as biological ground truth for boundary definition; 24,387 expert annotations across seven classes"
        elif row["metric_id"] == "p0.precise.stroma_fraction":
            item["source_path"] += "; https://github.com/abelBEDOYA/PRECISE-data-utils/add_stroma.py"
            item["annotator_or_validator"] = "expert annotation package plus automatic unlabeled-tissue stroma fill"
            item["validation_evidence"] = "public utility documents threshold/blur/dilation/erosion fill; quantitative validation not reported"
        provenance.append(item)
    return (
        pd.DataFrame(rows, columns=TABLE_SCHEMAS["metric_eligibility.tsv"]),
        pd.DataFrame(provenance, columns=TABLE_SCHEMAS["measurement_provenance.csv"]),
    )


def governance_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    claims = [
        ("C01", "P0 establishes methodological feasibility for approved model-target-FOV combinations", "methodological", "pending_G0-G9", "all relevant gates and clean rerun", "pre-G0 inventory only", "methodological feasibility", "clinical validation or model superiority", "research lead"),
        ("C02", "NADT model caches share membership and source truth", "integrity", "draft_supported", "source reconciliation", "334 grade slides/39 subjects; 463 phenotype slides/39 subjects; zero mismatches", "cache/source membership and truth reconciled", "independent clinical validation", "data manager"),
        ("C03", "PANDA model caches share an image/case subset and truth", "integrity", "draft_supported_with_limits", "source reconciliation and subject linkage", "1,123 common images; zero truth mismatch; subject linkage absent", "image/case membership audit", "patient-level or paired-coordinate comparison", "data manager"),
        ("C04", "Each encoder passes at least one source positive control", "gate", "not_tested", "subject/case-grouped permutation 95th percentile using saved OOF predictions", "existing point estimates only", "no claim before P0-M3", "pass based on seed/fold counts or point estimates alone", "statistics lead"),
        ("C05", "One encoder is superior to the other", "comparative", "prohibited", "paired same-coordinate same-FOV evidence with uncertainty", "historical outputs use different FOV/sampling", "none", "encoder league table or universal superiority", "research lead"),
        ("C06", "PRECISE frozen PNI ranker is candidate triage", "approved_scope", "allowed_only_as_approved", "approved frozen-score design", "separate approved audit", "candidate triage in selected reviewed sample", "whole-slide diagnosis, sensitivity, prevalence, clinical threshold", "research lead"),
        ("C07", "PRECISE 14-focus morphology results are a method pilot", "approved_scope", "allowed_only_as_approved", "approved morphology design", "separate approved re-review", "selected 14-focus feasibility", "population morphology distribution, prognosis, AI morphology accuracy", "pathology lead"),
        ("C08", "Tumor fraction is an independent descriptive quantitative target candidate", "measurement", "supported_for_descriptive_feasibility_only", "expert annotation provenance, denominator lock, M1 eligibility", "two expert uropathologists; three-stage consensus; IHC boundary reference; quantitative repeatability not reported", "descriptive feasibility target", "confirmatory biological ground truth or clinical validation", "pathology/data lead"),
        ("C09", "Frozen shared-FOV embeddings recover descriptive PRECISE tumor fraction above chance", "methodological", "not_tested", "P0-G6 subject-grouped OOF, permutation and cluster bootstrap", "P0-G5 technical embeddings only", "no recoverability claim before P0-M6", "confirmatory biomarker, encoder superiority, clinical or PNI claim", "statistics lead"),
        ("C10", "Descriptive tumor recoverability is robust enough for a defined model-target-FOV scope", "robustness", "not_tested", "P0-G7 scale/sampling/zero/QC/discordance evidence", "P0-G6 shared-FOV association only", "no robustness claim before P0-M7", "scanner/stain robustness, encoder superiority, clinical or PNI claim", "ML/statistics lead"),
    ]
    deviations = [
        ("D001", "P0-M0", "low", "tooling", "rg is not installed", "rg preferred", "inventory used find/grep", "retain command provenance; no scientific action", "open", "shell: rg command not found"),
        ("D002", "P0-M0", "high", "PANDA_subject_linkage", "PANDA cache/source exposes image_id but no verified subject link", "subject leakage auditable", "patient terminology and patient-grouped inference prohibited", "obtain verified subject linkage or keep image/case-only scope", "open", "PANDA train.csv columns"),
        ("D003", "P0-M2", "medium", "PANDA_sampling", "525/1,123 common PANDA IDs have different n_tiles", "same sampling budget/draw for paired comparison", "membership pairing is not coordinate/FOV pairing", "do not use PANDA cache as paired representation evidence", "open", "common_sample_manifest.csv"),
        ("D004", "P0-M2", "medium", "missing_log", "Virchow PANDA execution log is absent", "per-sample exclusion reasons preserved", "14 CONCH-only and 17 neither-model Virchow exclusions lack direct reasons", "recover log or rerun read-only eligibility reconstruction before predictive use", "open", "membership_mismatch.csv"),
        ("D005", "P0-M1", "medium", "measurement_repeatability", "Zenodo v1 documents two expert uropathologists, three-stage consensus, and IHC boundary reference; quantitative interobserver/repeatability is not reported", "independent target plus repeatability evidence", "tumor fraction allowed for descriptive feasibility but not confirmatory primary; stroma remains algorithm-assisted exploratory", "obtain quantitative repeatability and stroma algorithm validation", "open_limited", "metric_eligibility.tsv; measurement_provenance.csv; DOI 10.5281/zenodo.20721779"),
        ("D006", "P0-M1", "high", "missing_measurement", "no fixed validated nuclei detector/manual validation subset found", "independent validated nuclei measurement", "nuclear density deferred", "supply and lock detector plus validation evidence", "open", "metric_eligibility.tsv"),
        ("D007", "P0-M1", "high", "missing_measurement", "no expert lumen contours or validated fixed gland/lumen segmentation found", "independent validated gland/lumen measurement", "gland/lumen fraction deferred", "supply annotation/segmentation and failure log", "open", "metric_eligibility.tsv"),
        ("D008", "P0-M3", "high", "physical_FOV", "historical native settings imply CONCH 394.24 µm and Virchow 98.56 µm fields; target_mpp=1.76 still implies 788.48 vs 394.24 µm", "same physical FOV for cross-model inference", "historical stability results are controls/sensitivity evidence, not same-FOV superiority evidence", "approve 394.24 µm shared-FOV extraction for later P0-M4/M5", "open", "run_config.json and historical scripts"),
        ("D009", "P0-M3", "medium", "status_semantics", "360 aggregated cells retain status=pending while raw_status=complete/reconciliation_status=reconciled", "unambiguous completion field", "automated readers may misclassify existing results", "use raw_status plus reconciliation_status and document field semantics", "open", "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv"),
        ("D010", "P0-M0", "resolved", "approval", "P0-G0 approved by Jin Hyun Kim (PM) at 2026-08-11T19:17:36Z", "research-lead protocol approval before inference", "P0-M3 source-control qualification is authorized; later gates remain unchanged", "none", "closed", "PROTOCOL.md"),
        ("D011", "P0-M0", "medium", "compute", "nvidia-smi cannot communicate with the driver in this session", "GPU available before paired extraction", "no impact on read-only inventory; blocks GPU extraction", "resolve only after G0-G4 and before P0-M5", "open", "inventory command output"),
        ("D012", "P0-M6", "high", "primary_target_availability", "only tumor fraction remains eligible and it is descriptive-only; its eligible-tile median is zero", "three repeatable independent primary targets", "the prespecified strong G6 rule cannot be met; G6 is capped at Conditional Pass and zero-inflation must be reported", "restrict inference to passing model-tumor combinations and revisit repeatability/target breadth before confirmatory work", "open_limited", "metric_eligibility.tsv; target_availability.csv"),
        ("D013", "P0-M7", "medium", "metadata_robustness", "stain batch metadata is unavailable and the alternate native-MPP group contains only two subjects", "stain/scanner sensitivity with adequate independent groups", "scanner/stain robustness is not assessable and G7 is capped at Amber", "obtain scanner/stain metadata and a sufficiently sized independent acquisition group", "open_limited", "tile_qc.csv; paired_tile_manifest.csv; M7_ROBUSTNESS_REPORT.md"),
    ]
    gates = [
        ("P0-G0", "P0-M0", "Is the protocol locked before results?", "pass", "Pass", True, "PROTOCOL.md; run_config.json; claim_evidence_matrix.csv", "none for approved decision bundles", "P0-M1/M2 adjudication and eligible P0-M3 source controls", "P0-M4+ until their gates pass", APPROVAL["approver"] + " (" + APPROVAL["role"] + ")", APPROVAL["timestamp_utc"]),
        ("P0-G1", "P0-M1", "Are targets independent and repeatable?", "conditional_pass_descriptive_tumor_only", "Conditional Pass", True, "metric_eligibility.tsv; measurement_provenance.csv; Zenodo v1 DOI 10.5281/zenodo.20721779", "quantitative repeatability absent; stroma algorithm-assisted; nuclei and lumen deferred", "P0-M4 tumor-fraction descriptive technical feasibility", "confirmatory PRECISE concept analysis and stroma secondary claim", "pathology/statistics", ""),
        ("P0-G2", "P0-M2", "Are membership, truth, and splits reconciled?", "conditional_pass_verified_linkage_only", "Conditional Pass", True, "common_sample_manifest.csv; membership_mismatch.csv; truth_mismatch.csv; leakage_audit.csv", "PANDA subject leakage not assessable", "NADT and other source controls with verified case linkage", "PANDA patient/split inference", "data manager", ""),
        ("P0-G3", "P0-M3", "Do source positive controls exceed grouped-permutation p95?", "not_run_gate_locked", "Revise", False, "existing stability files inventoried", "no grouped permutation distribution saved for this P0", "none", "large extraction and cross-model superiority", "statistics", ""),
        ("P0-G4", "P0-M4", "Can paired targets/tiles meet same-FOV feasibility?", "locked", "Revise", False, "none", "G0-G3 incomplete", "none", "paired extraction", "pathology/data", ""),
        ("P0-G5", "P0-M5", "Are paired embeddings technically valid?", "locked", "Revise", False, "none", "G4 incomplete and GPU unavailable", "none", "concept probes", "ML", ""),
        ("P0-G6", "P0-M6", "Are independent concepts recovered above chance?", "locked", "Revise", False, "none", "prior gates incomplete", "none", "cross-model concept conclusions", "statistics", ""),
        ("P0-G7", "P0-M7", "Are signals robust to scale/sampling/QC?", "locked", "Revise", False, "none", "prior gates incomplete", "none", "robustness claims", "ML/statistics", ""),
        ("P0-G8", "P0-M8", "What is the integrated go decision?", "locked", "Revise", False, "none", "P0-M0-M7 incomplete", "none", "main-study execution", "research lead", ""),
        ("P0-G9", "P0-M9", "Is the clean rerun reproducible and handed off?", "locked", "Revise", False, "none", "G8 incomplete", "none", "FM3+ expansion", "research lead/ML/data", ""),
    ]
    unlock = [
        ("FM0", "preparation_only", "P0-G0 then final lock after G8", "approved protocol", "draft protocol review", "final protocol claim", "PROTOCOL.md"),
        ("FM1", "preparation_only", "P0-G1", "medical T1-T4 and separate analysis registry classified", "schema/catalog planning", "unclassified metric use as independent truth", "metric_eligibility.tsv"),
        ("FM2", "locked_except_inventory", "P0-G2 and G4", "new cohort same mismatch/leakage/FOV gates", "read-only inventory", "paired manifest freeze", "p0_gate_matrix.csv"),
        ("FM3", "locked", "P0-G5,G8,G9", "approved model-target-FOV", "code/smoke design only", "large extraction", "p0_gate_matrix.csv"),
        ("FM4", "locked", "P0-G6,G8,G9", "power/family approval", "none", "concept benchmark", "p0_gate_matrix.csv"),
        ("FM5", "locked", "P0-G7,G8,G9", "paired premise", "none", "cross-model comparison", "p0_gate_matrix.csv"),
        ("FM6", "locked", "P0-G8", "independent metrics, sufficient subjects/events, external set", "none", "complementarity claim", "p0_gate_matrix.csv"),
        ("FM7", "protocol_preparation_only", "P0-G9", "multiple external sites and sentinel truth", "protocol planning", "transport threshold", "p0_gate_matrix.csv"),
        ("FM8", "interface_preparation_only", "stable FM5/FM7 residual", "approved blinded review", "interface planning", "residual biological claim", "p0_gate_matrix.csv"),
        ("FM9", "locked", "repeated FM8 candidate", "independent assay/outcome/cohort", "none", "new biomarker validation", "p0_gate_matrix.csv"),
        ("FM10", "foundation_only", "all relevant gates", "clean rerun and claim audit", "catalog/schema work", "final result packaging", "p0_gate_matrix.csv"),
    ]
    return (
        pd.DataFrame(claims, columns=TABLE_SCHEMAS["claim_evidence_matrix.csv"]),
        pd.DataFrame(deviations, columns=TABLE_SCHEMAS["deviation_log.csv"]),
        pd.DataFrame(gates, columns=TABLE_SCHEMAS["p0_gate_matrix.csv"]),
        pd.DataFrame(unlock, columns=TABLE_SCHEMAS["main_study_unlock_matrix.csv"]),
    )


def write_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != TABLE_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    separator = "\t" if name.endswith(".tsv") else ","
    frame.to_csv(OUT / name, sep=separator, index=False, lineterminator="\n")


def write_m3_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M3_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def write_m4_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M4_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def bh_adjust(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=float)
    result = np.full(len(array), np.nan)
    valid = np.flatnonzero(np.isfinite(array))
    if not len(valid):
        return result.tolist()
    order = valid[np.argsort(array[valid], kind="mergesort")]
    adjusted = array[order] * len(order) / np.arange(1, len(order) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result[order] = np.minimum(adjusted, 1.0)
    return result.tolist()


def safe_metric(kind: str, truth: np.ndarray, prediction: np.ndarray,
                outcome_time: np.ndarray | None = None) -> tuple[float, str]:
    truth = np.asarray(truth, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    valid = np.isfinite(truth) & np.isfinite(prediction)
    if outcome_time is not None:
        outcome_time = np.asarray(outcome_time, dtype=float)
        valid &= np.isfinite(outcome_time)
        outcome_time = outcome_time[valid]
    truth, prediction = truth[valid], prediction[valid]
    try:
        if len(truth) < 2:
            return np.nan, "fewer_than_two_evaluable_units"
        if kind == "spearman":
            value = stats.spearmanr(truth, prediction).statistic
        elif kind == "mae":
            value = mean_absolute_error(truth, prediction)
        elif kind == "r2":
            value = r2_score(truth, prediction)
        elif kind == "auroc":
            if np.unique(truth).size != 2:
                return np.nan, "single_class"
            value = roc_auc_score(truth.astype(int), prediction)
        elif kind == "average_precision":
            if np.unique(truth).size != 2:
                return np.nan, "single_class"
            value = average_precision_score(truth.astype(int), prediction)
        elif kind == "c_index":
            if outcome_time is None:
                return np.nan, "missing_follow_up_time"
            # Fenwick-tree Harrell C in O(n log n). Process equal-time groups
            # together so they never become comparable with one another.
            unique_risk = np.unique(prediction)
            ranks = np.searchsorted(unique_risk, prediction) + 1
            tree = np.zeros(len(unique_risk) + 1, dtype=np.int64)
            def query(rank: int) -> int:
                total = 0
                while rank > 0:
                    total += int(tree[rank])
                    rank -= rank & -rank
                return total
            def add(rank: int) -> None:
                while rank < len(tree):
                    tree[rank] += 1
                    rank += rank & -rank
            concordant = tied = comparable = 0.0
            order = np.argsort(-outcome_time, kind="mergesort")
            start = 0
            while start < len(order):
                stop = start + 1
                while stop < len(order) and outcome_time[order[stop]] == outcome_time[order[start]]:
                    stop += 1
                current = order[start:stop]
                # sksurv-compatible rule: an event is comparable with censoring
                # at the same recorded time, but not with another same-time event.
                same_time_censored = [index for index in current if truth[index] != 1]
                for index in same_time_censored:
                    add(int(ranks[index]))
                n_later = start + len(same_time_censored)
                for index in current:
                    if truth[index] == 1:
                        lower = query(int(ranks[index]) - 1)
                        equal = query(int(ranks[index])) - lower
                        comparable += n_later
                        concordant += lower
                        tied += equal
                for index in current:
                    if truth[index] == 1:
                        add(int(ranks[index]))
                start = stop
            if comparable == 0:
                return np.nan, "no_comparable_survival_pairs"
            value = (concordant + 0.5 * tied) / comparable
        else:
            raise ValueError(f"unknown metric: {kind}")
    except (ValueError, FloatingPointError) as exc:
        return np.nan, f"{type(exc).__name__}:{exc}"
    if not np.isfinite(value):
        return np.nan, "nonfinite_statistic"
    return float(value), ""


def make_probe(binary: bool, value: float):
    if binary:
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=float(value), solver="liblinear", class_weight="balanced",
                max_iter=4000, random_state=SEED,
            ),
        )
    return make_pipeline(StandardScaler(), Ridge(alpha=float(value), solver="lsqr"))


def nested_fixed_fold_oof(X: np.ndarray, y: np.ndarray, folds: np.ndarray,
                          binary: bool) -> tuple[np.ndarray, np.ndarray]:
    """Nested selection using only the four non-test, preassigned outer folds."""
    grid = np.logspace(-4, 4, 17)
    if binary:
        grid = 1.0 / grid
    predictions = np.full(len(y), np.nan)
    selected = np.full(len(y), np.nan)
    for outer in sorted(np.unique(folds)):
        train = folds != outer
        test = folds == outer
        candidates: list[tuple[float, float]] = []
        for value in grid:
            losses: list[float] = []
            for inner in sorted(np.unique(folds[train])):
                inner_train = train & (folds != inner)
                inner_valid = train & (folds == inner)
                if binary and np.unique(y[inner_train]).size < 2:
                    continue
                model = make_probe(binary, float(value))
                model.fit(X[inner_train], y[inner_train].astype(int) if binary else y[inner_train])
                if binary:
                    inner_pred = model.predict_proba(X[inner_valid])[:, 1]
                    losses.append(log_loss(y[inner_valid].astype(int), inner_pred, labels=[0, 1]))
                else:
                    inner_pred = model.predict(X[inner_valid])
                    losses.append(float(np.mean((y[inner_valid] - inner_pred) ** 2)))
            if losses:
                candidates.append((float(np.mean(losses)), float(value)))
        if not candidates:
            raise RuntimeError(f"no valid inner-fold hyperparameter for outer fold {outer}")
        best = min(candidates, key=lambda item: (item[0], item[1]))[1]
        model = make_probe(binary, best)
        model.fit(X[train], y[train].astype(int) if binary else y[train])
        predictions[test] = (
            model.predict_proba(X[test])[:, 1] if binary else model.predict(X[test])
        )
        selected[test] = best
    if not np.isfinite(predictions).all():
        raise RuntimeError("OOF prediction coverage is incomplete")
    return predictions, selected


def aligned_native_cache(cohort: str) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, str]]:
    if cohort == "NADT-Prostate":
        paths = {
            "CONCH": (
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/meta_s0_mpp0.88.csv",
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_conch/tile_embeddings_s0_mpp0.88.npy",
            ),
            "Virchow": (
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/meta_s0_mpp0.44.csv",
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/nadt_virchow/tile_embeddings_s0_mpp0.44.npy",
            ),
        }
        id_column = "file_name"
    elif cohort == "TCGA-PRAD":
        paths = {
            "CONCH": (
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/meta_s0_mpp0.88.csv",
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/conch/tile_embeddings_s0_mpp0.88.npy",
            ),
            "Virchow": (
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/meta_s0_mpp0.44.csv",
                ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/virchow/tile_embeddings_s0_mpp0.44.npy",
            ),
        }
        id_column = "file_name"
    else:
        raise ValueError(cohort)
    metas = {encoder: pd.read_csv(meta) for encoder, (meta, _) in paths.items()}
    common = sorted(set(metas["CONCH"][id_column]) & set(metas["Virchow"][id_column]))
    if not common:
        raise RuntimeError(f"no common native-cache samples for {cohort}")
    base = metas["CONCH"].set_index(id_column).loc[common].reset_index()
    other = metas["Virchow"].set_index(id_column).loc[common].reset_index()
    shared_columns = sorted((set(base.columns) & set(other.columns)) - {"path"})
    for column in shared_columns:
        left = base[column].fillna("__MISSING__").astype(str).to_numpy()
        right = other[column].fillna("__MISSING__").astype(str).to_numpy()
        if not np.array_equal(left, right):
            raise RuntimeError(f"{cohort} truth/ID mismatch in {column}; stop")
    pooled: dict[str, np.ndarray] = {}
    hashes: dict[str, str] = {}
    for encoder, (meta_path, array_path) in paths.items():
        meta = metas[encoder]
        position = pd.Series(np.arange(len(meta)), index=meta[id_column])
        indices = position.loc[common].to_numpy(int)
        array = np.load(array_path, mmap_mode="r")
        if len(array) != len(meta) or array.shape[1] < 16:
            raise RuntimeError(f"{encoder} {cohort} cache shape does not support fixed 16-tile pool")
        pooled[encoder] = np.asarray(array[indices, :16].mean(axis=1), dtype=np.float64)
        hashes[encoder] = sha256_file(array_path)
        if sha256_file(meta_path) == "":
            raise AssertionError("unreachable")
    return base, pooled, hashes


def aggregate_analysis_units(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "slide":
        return frame.copy()
    if mode == "subject_mean":
        return frame.groupby("group_id", as_index=False).agg(
            truth=("truth", "mean"), outcome_time=("outcome_time", "mean"),
            prediction=("prediction", "mean"), fold=("fold", "first"),
        )
    raise ValueError(mode)


def endpoint_frames() -> list[dict[str, object]]:
    assignments = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv", dtype={"case_id": str})
    fold_hash = sha256_file(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv")
    results: list[dict[str, object]] = []
    nadt, nadt_X, nadt_hash = aligned_native_cache("NADT-Prostate")
    nadt["patient_id"] = nadt.patient_id.map(normalized_id)
    for endpoint, column, binary, unit, metric, permutation_mode in (
        ("nadt_gleason", "gleason", False, "subject_mean", "spearman", "between_groups"),
        ("nadt_phenotype", "phenotype", True, "slide", "auroc", "within_group"),
    ):
        eligible = nadt[column].notna().to_numpy()
        meta = nadt.loc[eligible].reset_index(drop=True)
        marker = "gleason" if endpoint == "nadt_gleason" else "phenotype"
        fold_part = assignments[assignments.marker == marker]
        fold_map = dict(zip(fold_part.case_id, fold_part.fold))
        folds = np.asarray([fold_map[str(value)] for value in meta.patient_id], dtype=int)
        predictions: dict[str, np.ndarray] = {}
        selected: dict[str, np.ndarray] = {}
        for encoder in ("CONCH", "Virchow"):
            prediction, choice = nested_fixed_fold_oof(
                nadt_X[encoder][eligible], meta[column].to_numpy(float), folds, binary,
            )
            predictions[encoder], selected[encoder] = prediction, choice
        results.append({
            "endpoint_id": endpoint, "config_id": "native_s0_t16", "meta": meta,
            "sample_ids": meta.file_name.astype(str).to_numpy(),
            "groups": meta.patient_id.astype(str).to_numpy(), "folds": folds,
            "truth": meta[column].to_numpy(float), "time": np.full(len(meta), np.nan),
            "predictions": predictions, "selected": selected, "hashes": nadt_hash,
            "fold_hash": fold_hash, "binary": binary, "analysis_mode": unit,
            "gate_metric": metric, "permutation_mode": permutation_mode,
            "positive_control": True,
        })

    tcga, tcga_X, tcga_hash = aligned_native_cache("TCGA-PRAD")
    tcga["case_id"] = tcga.case_id.astype(str)
    for endpoint, column, binary, metric in (
        ("tcga_pten", "pten", True, "auroc"),
        ("tcga_spop", "spop", True, "auroc"),
        ("tcga_ar", "ar", False, "spearman"),
    ):
        eligible = tcga[column].notna().to_numpy()
        meta = tcga.loc[eligible].reset_index(drop=True)
        marker = endpoint.removeprefix("tcga_")
        fold_part = assignments[assignments.marker == marker]
        fold_map = dict(zip(fold_part.case_id, fold_part.fold))
        folds = np.asarray([fold_map[str(value)] for value in meta.case_id], dtype=int)
        predictions, selected = {}, {}
        for encoder in ("CONCH", "Virchow"):
            prediction, choice = nested_fixed_fold_oof(
                tcga_X[encoder][eligible], meta[column].to_numpy(float), folds, binary,
            )
            predictions[encoder], selected[encoder] = prediction, choice
        results.append({
            "endpoint_id": endpoint, "config_id": "native_s0_t16", "meta": meta,
            "sample_ids": meta.file_name.astype(str).to_numpy(),
            "groups": meta.case_id.astype(str).to_numpy(), "folds": folds,
            "truth": meta[column].to_numpy(float), "time": np.full(len(meta), np.nan),
            "predictions": predictions, "selected": selected, "hashes": tcga_hash,
            "fold_hash": fold_hash, "binary": binary, "analysis_mode": "subject_mean",
            "gate_metric": metric, "permutation_mode": "between_groups",
            "positive_control": False,
        })

    recurrence_paths = {
        "CONCH": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/direct_recurrence_oof.csv",
        "Virchow": ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/direct_recurrence_oof.csv",
    }
    recurrence = {encoder: pd.read_csv(path) for encoder, path in recurrence_paths.items()}
    merged = recurrence["CONCH"].merge(
        recurrence["Virchow"], on="case_id", suffixes=("_conch", "_virchow"),
        validate="one_to_one",
    ).sort_values("case_id").reset_index(drop=True)
    for column in ("event", "follow_up_years", "n_tiles"):
        if not np.allclose(merged[f"{column}_conch"], merged[f"{column}_virchow"], equal_nan=True):
            raise RuntimeError(f"LEOPARD recurrence mismatch in {column}; stop")
    from sklearn.model_selection import KFold
    historical_order = recurrence["CONCH"].case_id.astype(str).tolist()
    historical_folds: dict[str, int] = {}
    for fold, (_, test) in enumerate(KFold(5, shuffle=True, random_state=0).split(historical_order)):
        for index in test:
            historical_folds[historical_order[index]] = fold
    results.append({
        "endpoint_id": "leopard_recurrence", "config_id": "historical_direct_oof_pca8",
        "meta": merged, "sample_ids": merged.case_id.astype(str).to_numpy(),
        "groups": merged.case_id.astype(str).to_numpy(),
        "folds": np.asarray([historical_folds[x] for x in merged.case_id.astype(str)], dtype=int),
        "truth": merged.event_conch.to_numpy(float),
        "time": merged.follow_up_years_conch.to_numpy(float),
        "predictions": {
            "CONCH": merged.oof_risk_conch.to_numpy(float),
            "Virchow": merged.oof_risk_virchow.to_numpy(float),
        },
        "selected": {"CONCH": np.full(len(merged), 8.0), "Virchow": np.full(len(merged), 8.0)},
        "hashes": {encoder: sha256_file(path) for encoder, path in recurrence_paths.items()},
        "fold_hash": "historical_KFold_n5_shuffle_seed0_reconstructed_from_locked_row_order",
        "binary": False, "analysis_mode": "subject_mean", "gate_metric": "c_index",
        "permutation_mode": "between_groups", "positive_control": False,
    })
    return results


def analysis_frame(endpoint: dict[str, object], encoder: str) -> pd.DataFrame:
    frame = pd.DataFrame({
        "sample_id": endpoint["sample_ids"], "group_id": endpoint["groups"],
        "fold": endpoint["folds"], "truth": endpoint["truth"],
        "outcome_time": endpoint["time"], "prediction": endpoint["predictions"][encoder],
    })
    return aggregate_analysis_units(frame, str(endpoint["analysis_mode"]))


def resampled_metric(frame: pd.DataFrame, metric_name: str,
                     sampled_groups: np.ndarray) -> tuple[float, str]:
    group_indices = frame.attrs.get("group_indices")
    if group_indices is None:
        values = frame.group_id.to_numpy()
        group_indices = {group: np.flatnonzero(values == group) for group in pd.unique(values)}
        frame.attrs["group_indices"] = group_indices
    indices = np.concatenate([group_indices[group] for group in sampled_groups])
    return safe_metric(
        metric_name, frame.truth.to_numpy()[indices], frame.prediction.to_numpy()[indices],
        frame.outcome_time.to_numpy()[indices] if metric_name == "c_index" else None,
    )


def run_m3() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn.linear_model")
    run_pre_g0()
    started = datetime.now(timezone.utc)
    endpoints = endpoint_frames()
    prediction_rows: list[dict[str, object]] = []
    result_rows: list[dict[str, object]] = []
    permutation_rows: list[dict[str, object]] = []
    bootstrap_rows: list[dict[str, object]] = []
    delta_rows: list[dict[str, object]] = []
    saved_bootstrap: dict[tuple[str, str, str], np.ndarray] = {}
    endpoint_summaries: list[dict[str, object]] = []

    for endpoint in endpoints:
        endpoint_id = str(endpoint["endpoint_id"])
        config_id = str(endpoint["config_id"])
        if endpoint["gate_metric"] == "c_index":
            metric_names = ["c_index"]
        elif bool(endpoint["binary"]):
            metric_names = ["auroc", "average_precision"]
        else:
            metric_names = ["mae", "r2", "spearman"]

        for encoder in ("CONCH", "Virchow"):
            for index in range(len(endpoint["sample_ids"])):
                prediction_rows.append({
                    "endpoint_id": endpoint_id, "encoder": encoder,
                    "config_id": config_id, "sample_id": endpoint["sample_ids"][index],
                    "group_id": endpoint["groups"][index], "fold": endpoint["folds"][index],
                    "truth": endpoint["truth"][index], "outcome_time": endpoint["time"][index],
                    "prediction": endpoint["predictions"][encoder][index],
                    "prediction_status": "historical_locked_oof" if endpoint_id == "leopard_recurrence" else "new_fixed_fold_oof",
                    "selected_hyperparameter": endpoint["selected"][encoder][index],
                    "source_embedding_sha256": endpoint["hashes"][encoder],
                    "fold_manifest_sha256": endpoint["fold_hash"],
                })

        frames = {encoder: analysis_frame(endpoint, encoder) for encoder in ("CONCH", "Virchow")}
        for encoder in ("CONCH", "Virchow"):
            frame = frames[encoder]
            observed_gate, observed_reason = safe_metric(
                str(endpoint["gate_metric"]), frame.truth.to_numpy(), frame.prediction.to_numpy(),
                frame.outcome_time.to_numpy() if endpoint["gate_metric"] == "c_index" else None,
            )
            if observed_reason:
                raise RuntimeError(f"observed {endpoint_id}/{encoder} gate metric undefined: {observed_reason}")
            null_values: list[float] = []
            truth_values = frame.truth.to_numpy()
            prediction_values = frame.prediction.to_numpy()
            time_values = frame.outcome_time.to_numpy()
            grouped_indices = {
                group: np.flatnonzero(frame.group_id.to_numpy() == group)
                for group in frame.group_id.drop_duplicates()
            }
            for replicate in range(2000):
                rng = np.random.default_rng(SEED + replicate)
                permuted_truth = truth_values.copy()
                permuted_time = time_values.copy()
                if endpoint["permutation_mode"] == "within_group":
                    for indices in grouped_indices.values():
                        permuted_truth[indices] = rng.permutation(permuted_truth[indices])
                else:
                    order = rng.permutation(len(frame))
                    permuted_truth = truth_values[order]
                    if endpoint["gate_metric"] == "c_index":
                        permuted_time = time_values[order]
                estimate, reason = safe_metric(
                    str(endpoint["gate_metric"]), permuted_truth, prediction_values,
                    permuted_time if endpoint["gate_metric"] == "c_index" else None,
                )
                null_values.append(estimate)
                permutation_rows.append({
                    "endpoint_id": endpoint_id, "encoder": encoder, "config_id": config_id,
                    "replicate_id": replicate, "permutation_seed": SEED + replicate,
                    "metric_name": endpoint["gate_metric"], "estimate": estimate,
                    "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                    "undefined_reason": reason,
                })
            valid_null = np.asarray([value for value in null_values if np.isfinite(value)])
            if not len(valid_null):
                raise RuntimeError(f"all permutation replicates undefined for {endpoint_id}/{encoder}")
            p95 = float(np.quantile(valid_null, 0.95))
            empirical_p = float((1 + np.sum(valid_null >= observed_gate)) / (1 + len(valid_null)))

            groups = frame.group_id.drop_duplicates().to_numpy()
            metric_bootstrap: dict[str, list[float]] = {metric: [] for metric in metric_names}
            for replicate in range(2000):
                rng = np.random.default_rng(SEED + 1 + replicate)
                sampled_groups = rng.choice(groups, size=len(groups), replace=True)
                for metric_name in metric_names:
                    estimate, reason = resampled_metric(frame, metric_name, sampled_groups)
                    metric_bootstrap[metric_name].append(estimate)
                    bootstrap_rows.append({
                        "endpoint_id": endpoint_id, "encoder": encoder,
                        "config_id": config_id, "replicate_id": replicate,
                        "bootstrap_seed": SEED + 1 + replicate, "metric_name": metric_name,
                        "estimate": estimate,
                        "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                        "undefined_reason": reason,
                    })
            for metric_name in metric_names:
                estimate, reason = safe_metric(
                    metric_name, frame.truth.to_numpy(), frame.prediction.to_numpy(),
                    frame.outcome_time.to_numpy() if metric_name == "c_index" else None,
                )
                if reason:
                    raise RuntimeError(f"observed {endpoint_id}/{encoder}/{metric_name} undefined: {reason}")
                distribution = np.asarray(metric_bootstrap[metric_name])
                saved_bootstrap[(endpoint_id, encoder, metric_name)] = distribution
                valid = distribution[np.isfinite(distribution)]
                result_rows.append({
                    "endpoint_id": endpoint_id, "encoder": encoder, "config_id": config_id,
                    "analysis_unit": "slide_clustered_by_subject" if endpoint["analysis_mode"] == "slide" else "subject/case",
                    "metric_name": metric_name, "estimate": estimate,
                    "ci_low": float(np.quantile(valid, 0.025)) if len(valid) else np.nan,
                    "ci_high": float(np.quantile(valid, 0.975)) if len(valid) else np.nan,
                    "n_samples": len(frame), "n_groups": frame.group_id.nunique(),
                    "n_valid_bootstrap": len(valid),
                    "n_undefined_bootstrap": int((~np.isfinite(distribution)).sum()),
                    "permutation_p95": p95 if metric_name == endpoint["gate_metric"] else np.nan,
                    "empirical_p": empirical_p if metric_name == endpoint["gate_metric"] else np.nan,
                    "empirical_q": np.nan,
                    "gate_exceedance": bool(estimate > p95) if metric_name == endpoint["gate_metric"] else "not_gate_metric",
                })

        conch_frame, virchow_frame = frames["CONCH"], frames["Virchow"]
        if not np.array_equal(conch_frame.group_id.to_numpy(), virchow_frame.group_id.to_numpy()):
            raise RuntimeError(f"paired analysis-unit order mismatch for {endpoint_id}")
        groups = conch_frame.group_id.drop_duplicates().to_numpy()
        for metric_name in metric_names:
            conch_observed, _ = safe_metric(
                metric_name, conch_frame.truth, conch_frame.prediction,
                conch_frame.outcome_time if metric_name == "c_index" else None,
            )
            virchow_observed, _ = safe_metric(
                metric_name, virchow_frame.truth, virchow_frame.prediction,
                virchow_frame.outcome_time if metric_name == "c_index" else None,
            )
            distribution = (
                saved_bootstrap[(endpoint_id, "CONCH", metric_name)]
                - saved_bootstrap[(endpoint_id, "Virchow", metric_name)]
            )
            valid = distribution[np.isfinite(distribution)]
            delta_rows.append({
                "endpoint_id": endpoint_id, "config_id": config_id,
                "metric_name": metric_name, "conch_estimate": conch_observed,
                "virchow_estimate": virchow_observed,
                "paired_delta": conch_observed - virchow_observed,
                "ci_low": float(np.quantile(valid, 0.025)) if len(valid) else np.nan,
                "ci_high": float(np.quantile(valid, 0.975)) if len(valid) else np.nan,
                "n_valid": len(valid), "n_undefined": int((~np.isfinite(distribution)).sum()),
            })

    results = pd.DataFrame(result_rows, columns=M3_SCHEMAS["existing_common_sample_results.csv"])
    gate_indices = results.index[results.empirical_p.notna()].tolist()
    adjusted = bh_adjust(results.loc[gate_indices, "empirical_p"].astype(float).tolist())
    results.loc[gate_indices, "empirical_q"] = adjusted
    predictions = pd.DataFrame(prediction_rows, columns=M3_SCHEMAS["existing_oof_predictions.csv"])
    permutations = pd.DataFrame(permutation_rows, columns=M3_SCHEMAS["existing_permutation_null.csv"])
    bootstraps = pd.DataFrame(bootstrap_rows, columns=M3_SCHEMAS["existing_bootstrap_replicates.csv"])
    deltas = pd.DataFrame(delta_rows, columns=M3_SCHEMAS["existing_paired_deltas.csv"])
    write_m3_table("existing_oof_predictions.csv", predictions)
    write_m3_table("existing_common_sample_results.csv", results)
    write_m3_table("existing_permutation_null.csv", permutations)
    write_m3_table("existing_bootstrap_replicates.csv", bootstraps)
    write_m3_table("existing_paired_deltas.csv", deltas)

    positive = results[
        results.endpoint_id.isin(["nadt_gleason", "nadt_phenotype"])
        & results.metric_name.isin(["spearman", "auroc"])
    ].copy()
    encoder_pass = {
        encoder: bool(positive.loc[positive.encoder == encoder, "gate_exceedance"].eq(True).any())
        for encoder in ("CONCH", "Virchow")
    }
    gate_pass = all(encoder_pass.values())
    for row in results[results.metric_name.isin(["spearman", "auroc", "c_index"])].itertuples():
        endpoint_summaries.append({
            "endpoint": row.endpoint_id, "encoder": row.encoder, "metric": row.metric_name,
            "estimate": float(row.estimate), "ci_low": float(row.ci_low),
            "ci_high": float(row.ci_high),
            "p95": None if pd.isna(row.permutation_p95) else float(row.permutation_p95),
            "p": None if pd.isna(row.empirical_p) else float(row.empirical_p),
            "q": None if pd.isna(row.empirical_q) else float(row.empirical_q),
            "exceeds_p95": row.gate_exceedance,
        })

    report_lines = [
        "# P0-M3 existing-embedding positive-control report", "",
        f"- Protocol: `{PROTOCOL_ID}`", f"- Approval: {APPROVAL['approver']} ({APPROVAL['role']}), {APPROVAL['timestamp_utc']}",
        f"- P0-G3 decision: **{'Pass' if gate_pass else 'Stop'}**", "",
        "## Observed facts", "",
        "All new probe predictions are subject/case-grouped OOF predictions from frozen embeddings and preassigned folds. "
        "NADT/TCGA use sampling seed 0, the first 16 ranked tiles, and each encoder's historical native FOV. "
        "LEOPARD recurrence reuses locked historical direct-recurrence OOF risks; it is not refit in this stage.", "",
        "| Endpoint | Encoder | Metric | Estimate | 95% cluster CI | Permutation p95 | Empirical p | BH q | Gate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in endpoint_summaries:
        p95_text = "" if item["p95"] is None else f"{item['p95']:.4f}"
        p_text = "" if item["p"] is None else f"{item['p']:.4g}"
        q_text = "" if item["q"] is None else f"{item['q']:.4g}"
        report_lines.append(
            f"| {item['endpoint']} | {item['encoder']} | {item['metric']} | {item['estimate']:.4f} | "
            f"[{item['ci_low']:.4f}, {item['ci_high']:.4f}] | "
            f"{p95_text} | {p_text} | {q_text} | {item['exceeds_p95']} |"
        )
    report_lines.extend([
        "", "## Statistical inference", "",
        "The gate uses only the two prespecified NADT controls. A model passes if at least one of its NADT "
        "statistics exceeds that model/control's 2,000-replicate grouped permutation 95th percentile. "
        f"CONCH pass={encoder_pass['CONCH']}; Virchow pass={encoder_pass['Virchow']}.", "",
        "Permutations are conditional on the saved frozen OOF predictions: subject-level outcomes are permuted "
        "between subjects/cases; NADT phenotype labels are permuted within subject to preserve each subject's "
        "label counts. Models are not retuned inside null replicates. Bootstrap rows retain every undefined replicate.", "",
        "## Interpretation boundary", "",
        "This qualifies the existing-embedding analysis pipeline only. Native physical FOVs differ, so paired "
        "deltas are sensitivity descriptions, not encoder superiority. It provides no clinical validation, no "
        "whole-slide PNI diagnostic claim, and no authorization for PRECISE Frame D unless a later G1/G4 "
        "adjudication explicitly unlocks a limited target role.",
    ])
    (OUT / "positive_control_report.md").write_text("\n".join(report_lines) + "\n")

    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    mask = gates.gate_id == "P0-G3"
    gates.loc[mask, "status"] = "pass" if gate_pass else "stop"
    gates.loc[mask, "draft_decision"] = "Pass" if gate_pass else "Stop"
    gates.loc[mask, "entry_condition_met"] = gate_pass
    gates.loc[mask, "direct_evidence"] = "existing_oof_predictions.csv; existing_permutation_null.csv; existing_bootstrap_replicates.csv; positive_control_report.md"
    gates.loc[mask, "unresolved_risk"] = "native FOV differs; recurrence OOF is historical; conditional permutation does not refit"
    gates.loc[mask, "next_unlocked"] = "P0-M4 feasibility only if P0-G1 provenance blocker is resolved" if gate_pass else "none"
    gates.loc[mask, "still_prohibited"] = "PRECISE Frame D; large extraction; encoder-superiority or clinical claims"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])
    claims = pd.read_csv(OUT / "claim_evidence_matrix.csv")
    mask = claims.claim_id == "C04"
    claims.loc[mask, "status"] = "supported" if gate_pass else "not_supported"
    claims.loc[mask, "current_evidence"] = f"CONCH_pass={encoder_pass['CONCH']}; Virchow_pass={encoder_pass['Virchow']}"
    claims.loc[mask, "allowed_wording"] = "existing-embedding source-control pipeline qualified" if gate_pass else "source-control gate not passed"
    write_table("claim_evidence_matrix.csv", claims[TABLE_SCHEMAS["claim_evidence_matrix.csv"]])

    inventory = pd.read_csv(OUT / "source_inventory.csv")
    changed = []
    for row in inventory.itertuples(index=False):
        current = sha256_file(Path(row.resolved_path))
        if current != row.sha256_pre:
            changed.append(row.source_id)
    if changed:
        raise RuntimeError("source changed during P0-M3: " + ", ".join(changed))
    finished = datetime.now(timezone.utc)
    config_path = OUT / "run_config.json"
    config = json.loads(config_path.read_text())
    config["stage_executed"] = "P0-M0-M3 approved source-control qualification"
    config["stage_not_executed"] = "PRECISE Frame D/P0-M4+; GPU extraction"
    config["m3"] = {
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
        "execution_seconds": (finished - started).total_seconds(),
        "outer_folds": "preassigned subject/case grouped five-fold",
        "inner_selection": "four remaining preassigned fold strata; identical 17-value L2 grid",
        "configuration": "sampling seed 0, first 16 ranked tiles, encoder-native historical FOV",
        "permutation": "2000 conditional grouped label permutations; no refit within replicate",
        "bootstrap": "2000 paired subject/case-cluster replicates; undefined retained",
        "encoder_gate_pass": encoder_pass, "p0_g3_pass": gate_pass,
        "endpoint_summary": endpoint_summaries,
    }
    config["all_source_pre_post_hashes_match_after_m3"] = True
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "run_config.json" and path.name != "PROTOCOL.md"
        and path.name != "run_preexperiment.py"
    }
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"P0-G3": "Pass" if gate_pass else "Stop", "encoder_pass": encoder_pass}, indent=2))


def restore_saved_m3_gate() -> dict[str, bool]:
    required = list(M3_SCHEMAS) + ["positive_control_report.md"]
    missing = [name for name in required if not (OUT / name).exists()]
    if missing:
        raise FileNotFoundError("saved P0-M3 evidence missing: " + ", ".join(missing))
    loaded: dict[str, pd.DataFrame] = {}
    for name, columns in M3_SCHEMAS.items():
        frame = pd.read_csv(OUT / name)
        if list(frame.columns) != columns:
            raise RuntimeError(f"saved P0-M3 schema mismatch: {name}")
        loaded[name] = frame
    results = loaded["existing_common_sample_results.csv"]
    predictions = loaded["existing_oof_predictions.csv"]
    if predictions.prediction.isna().any() or predictions.duplicated(
        ["endpoint_id", "encoder", "sample_id"]
    ).any():
        raise RuntimeError("saved P0-M3 predictions are incomplete or duplicated")
    positive = results[
        results.endpoint_id.isin(["nadt_gleason", "nadt_phenotype"])
        & results.metric_name.isin(["spearman", "auroc"])
    ]
    encoder_pass = {
        encoder: bool(positive.loc[positive.encoder == encoder, "gate_exceedance"].astype(str).str.lower().eq("true").any())
        for encoder in ("CONCH", "Virchow")
    }
    if not all(encoder_pass.values()):
        raise RuntimeError(f"saved P0-M3 no longer satisfies the approved gate: {encoder_pass}")
    inventory_hashes = set(pd.read_csv(OUT / "source_inventory.csv").sha256_pre.astype(str))
    if not set(predictions.source_embedding_sha256.astype(str)) <= inventory_hashes:
        raise RuntimeError("saved P0-M3 prediction source hash is absent from current inventory")
    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    gate = gates.gate_id == "P0-G3"
    gates.loc[gate, "status"] = "pass_saved_outputs_reverified"
    gates.loc[gate, "draft_decision"] = "Pass"
    gates.loc[gate, "entry_condition_met"] = True
    gates.loc[gate, "direct_evidence"] = "existing_oof_predictions.csv; existing_permutation_null.csv; existing_bootstrap_replicates.csv; positive_control_report.md"
    gates.loc[gate, "unresolved_risk"] = "native FOV differs; recurrence OOF is historical; conditional permutation does not refit"
    gates.loc[gate, "next_unlocked"] = "P0-M4 descriptive technical feasibility under conditional P0-G1"
    gates.loc[gate, "still_prohibited"] = "confirmatory PRECISE concept analysis; encoder-superiority or clinical claims"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])
    claims = pd.read_csv(OUT / "claim_evidence_matrix.csv")
    claim = claims.claim_id == "C04"
    claims.loc[claim, "status"] = "supported_saved_outputs_reverified"
    claims.loc[claim, "current_evidence"] = "CONCH_pass=True; Virchow_pass=True"
    claims.loc[claim, "allowed_wording"] = "existing-embedding source-control pipeline qualified"
    write_table("claim_evidence_matrix.csv", claims[TABLE_SCHEMAS["claim_evidence_matrix.csv"]])
    return encoder_pass


def parse_ome_mpp(ome_xml: str) -> tuple[float, float]:
    x = re.search(r'PhysicalSizeX="([^"]+)"', ome_xml or "")
    y = re.search(r'PhysicalSizeY="([^"]+)"', ome_xml or "")
    if not x or not y:
        raise RuntimeError("OME PhysicalSizeX/PhysicalSizeY missing")
    return float(x.group(1)), float(y.group(1))


def mapped_boundary(start: int, stop: int, full_size: int, level_size: int) -> tuple[int, int]:
    low = int(np.floor(start * level_size / full_size))
    high = int(np.ceil(stop * level_size / full_size))
    return max(0, low), min(level_size, high)


def he_qc_metrics(rgb: np.ndarray) -> dict[str, object]:
    if rgb.size == 0 or rgb.ndim != 3 or rgb.shape[2] < 3:
        return {name: np.nan for name in (
            "brightness_mean", "grayscale_sd", "laplacian_variance", "saturation_mean",
            "high_saturation_fraction", "dark_fold_fraction", "blue_pen_fraction",
            "green_pen_fraction",
        )} | {"he_qc_status": "missing_or_invalid_crop"}
    value = rgb[..., :3].astype(np.float32)
    gray = 0.299 * value[..., 0] + 0.587 * value[..., 1] + 0.114 * value[..., 2]
    maximum, minimum = value.max(axis=2), value.min(axis=2)
    saturation = (maximum - minimum) / np.maximum(maximum, 1.0)
    red, green, blue = value[..., 0], value[..., 1], value[..., 2]
    return {
        "brightness_mean": float(gray.mean()),
        "grayscale_sd": float(gray.std()),
        "laplacian_variance": float(ndimage.laplace(gray).var()),
        "saturation_mean": float(saturation.mean()),
        "high_saturation_fraction": float((saturation > 0.8).mean()),
        "dark_fold_fraction": float((gray < 40).mean()),
        "blue_pen_fraction": float(((blue > 1.2 * red) & (blue > 1.1 * green) & (blue < 220)).mean()),
        "green_pen_fraction": float(((green > 1.2 * red) & (green > 1.1 * blue) & (green < 220)).mean()),
        "he_qc_status": "recorded_not_used_for_exclusion",
    }


def m5_model_spec(encoder: str) -> dict[str, object]:
    if encoder == "conch":
        return {
            "model_id": "conch_ViT-B-16 / MahmoodLab/conch",
            "revision": "f9ca9f877171a28ade80228fb195ac5d79003357",
            "weights": model_snapshot_root("conch") / "pytorch_model.bin",
            "input_px": 448,
            "dimension": M5_DIMENSION[encoder],
        }
    if encoder == "virchow":
        snapshot = model_snapshot_root("virchow")
        return {
            "model_id": "paige-ai/Virchow",
            "revision": "19eebc84ae33e79f1b2d866e6ff90ae50e522f9a",
            "weights": snapshot / "model.safetensors",
            "config": snapshot / "config.json",
            "input_px": 224,
            "dimension": M5_DIMENSION[encoder],
        }
    raise ValueError(f"unknown encoder: {encoder}")


def read_tiled_rgb_region(
    page: tifffile.TiffPage, x0: int, y0: int, x1: int, y1: int
) -> np.ndarray:
    """Decode only TIFF tiles intersecting one locked level-0 rectangle."""
    if not page.is_tiled or page.planarconfig != 1 or page.samplesperpixel < 3:
        raise RuntimeError("P0-M5 requires contiguous tiled RGB level-0 H&E")
    if not (0 <= x0 < x1 <= page.imagewidth and 0 <= y0 < y1 <= page.imagelength):
        raise RuntimeError("P0-M5 crop boundary falls outside level-0 H&E")
    tile_width, tile_height = int(page.tilewidth), int(page.tilelength)
    tiles_across = math.ceil(page.imagewidth / tile_width)
    crop = np.empty((y1 - y0, x1 - x0, 3), dtype=np.uint8)
    coverage = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    handle = page.parent.filehandle
    for tile_y in range(y0 // tile_height, (y1 - 1) // tile_height + 1):
        for tile_x in range(x0 // tile_width, (x1 - 1) // tile_width + 1):
            tile_index = tile_y * tiles_across + tile_x
            handle.seek(page.dataoffsets[tile_index])
            encoded = handle.read(page.databytecounts[tile_index])
            decoded = page.decode(encoded, tile_index, jpegtables=page.jpegtables)[0]
            if decoded is None:
                raise RuntimeError(f"failed to decode TIFF tile {tile_index}")
            tile = decoded[0] if decoded.ndim == 4 else decoded
            if tile.ndim != 3 or tile.shape[2] < 3:
                raise RuntimeError(f"unexpected decoded TIFF tile shape: {tile.shape}")
            global_x0, global_y0 = tile_x * tile_width, tile_y * tile_height
            overlap_x0, overlap_y0 = max(x0, global_x0), max(y0, global_y0)
            overlap_x1 = min(x1, global_x0 + tile.shape[1])
            overlap_y1 = min(y1, global_y0 + tile.shape[0])
            crop_y = slice(overlap_y0 - y0, overlap_y1 - y0)
            crop_x = slice(overlap_x0 - x0, overlap_x1 - x0)
            tile_y_slice = slice(overlap_y0 - global_y0, overlap_y1 - global_y0)
            tile_x_slice = slice(overlap_x0 - global_x0, overlap_x1 - global_x0)
            crop[crop_y, crop_x] = tile[tile_y_slice, tile_x_slice, :3]
            coverage[crop_y, crop_x] = True
    if not coverage.all():
        raise RuntimeError("decoded TIFF tiles do not fully cover the locked crop")
    return crop


def m5_audit_indices(n_rows: int) -> np.ndarray:
    if n_rows < 8:
        raise RuntimeError("P0-M5 determinism audit requires at least 8 eligible tiles")
    return np.sort(np.random.default_rng(SEED + 5).choice(n_rows, size=8, replace=False))


def load_m5_model(encoder: str, device: object) -> tuple[object, object]:
    import torch

    spec = m5_model_spec(encoder)
    weights = Path(spec["weights"])
    if not weights.exists():
        raise FileNotFoundError(weights)
    if encoder == "conch":
        from conch.open_clip_custom import create_model_from_pretrained

        model, transform = create_model_from_pretrained(
            "conch_ViT-B-16", checkpoint_path=str(weights), device=device
        )
    else:
        import timm
        from timm.layers import SwiGLUPacked

        config = json.loads(Path(spec["config"]).read_text())
        model = timm.create_model(
            config["architecture"], pretrained=False,
            pretrained_cfg=config["pretrained_cfg"], checkpoint_path=str(weights),
            mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU,
            **config["model_args"],
        ).to(device)
        data_config = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
        transform = timm.data.create_transform(**data_config, is_training=False)
    return model.eval(), transform


def m5_embed_batch(encoder: str, model: object, batch: object) -> object:
    if encoder == "conch":
        return model.encode_image(batch, proj_contrast=False, normalize=False)
    tokens = model.forward_features(batch)
    return __import__("torch").cat([tokens[:, 0], tokens[:, 1:].mean(dim=1)], dim=-1)


def m5_read_crops(rows: pd.DataFrame) -> tuple[list[np.ndarray], list[str]]:
    crops: list[np.ndarray] = []
    hashes: list[str] = []
    he_paths = rows.he_path.unique()
    if len(he_paths) != 1:
        raise RuntimeError("M5 crop batch must come from exactly one H&E source")
    with tifffile.TiffFile(ROOT / he_paths[0]) as tif:
        page = tif.series[0].levels[0].pages[0]
        for row in rows.itertuples(index=False):
            crop = read_tiled_rgb_region(
                page, int(row.level0_x0), int(row.level0_y0),
                int(row.level0_x1), int(row.level0_y1),
            )
            crops.append(crop)
            hashes.append(hashlib.sha256(crop.tobytes(order="C")).hexdigest())
    return crops, hashes


def prepare_m5_manifest() -> pd.DataFrame:
    manifest_path = OUT / "paired_tile_manifest.csv"
    if not manifest_path.exists():
        raise RuntimeError("P0-M4 paired tile manifest is absent")
    source = pd.read_csv(manifest_path, keep_default_na=False)
    if list(source.columns) != M4_SCHEMAS["paired_tile_manifest.csv"]:
        raise RuntimeError("P0-M4 paired tile manifest schema changed")
    eligible = source[source.inclusion_status.eq("eligible_descriptive_tumor")].copy()
    if len(eligible) != 1218 or eligible.subject_id.nunique() != 25:
        raise RuntimeError("P0-M4 eligible universe no longer matches the locked 1,218 tiles / 25 subjects")
    if eligible.tile_id.duplicated().any() or not eligible.same_boundary_for_both_models.all():
        raise RuntimeError("P0-M4 eligible tile IDs/boundaries are not paired")
    eligible.insert(0, "embedding_row", np.arange(len(eligible), dtype=int))
    return eligible.reset_index(drop=True)


def write_m5_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M5_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def configure_m5_determinism() -> object:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("P0-M5 requires a visible CUDA device; run outside the sandbox")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


def transform_m5_crops(transform: object, crops: list[np.ndarray]) -> object:
    import torch
    from PIL import Image

    return torch.stack([transform(Image.fromarray(crop, mode="RGB")) for crop in crops])


def run_m5_encoder(encoder: str, smoke_only: bool = False) -> None:
    import torch

    manifest = prepare_m5_manifest()
    device = configure_m5_determinism()
    spec = m5_model_spec(encoder)
    model, transform = load_m5_model(encoder, device)
    batch_size = M5_BATCH_SIZE[encoder]
    audit_rows = manifest.iloc[m5_audit_indices(len(manifest))]
    audit_crops: list[np.ndarray] = []
    for index in audit_rows.index:
        crops, _ = m5_read_crops(manifest.loc[[index]])
        audit_crops.extend(crops)
    audit_tensor = transform_m5_crops(transform, audit_crops).to(device)
    with torch.inference_mode():
        first = m5_embed_batch(encoder, model, audit_tensor).detach().cpu().float().numpy()
        second = m5_embed_batch(encoder, model, audit_tensor).detach().cpu().float().numpy()
    if first.shape != (8, M5_DIMENSION[encoder]):
        raise RuntimeError(f"unexpected {encoder} smoke shape: {first.shape}")
    audit_records = []
    for audit_order, (row, left, right) in enumerate(
        zip(audit_rows.itertuples(index=False), first, second, strict=True)
    ):
        audit_records.append({
            "encoder": encoder, "tile_id": row.tile_id, "audit_order": audit_order,
            "first_feature_sha256": hashlib.sha256(left.tobytes()).hexdigest(),
            "second_feature_sha256": hashlib.sha256(right.tobytes()).hexdigest(),
            "exact_equal": bool(np.array_equal(left, right)),
            "max_abs_difference": float(np.max(np.abs(left - right))),
            "all_finite": bool(np.isfinite(left).all() and np.isfinite(right).all()),
            "deterministic_algorithms_enabled": bool(torch.are_deterministic_algorithms_enabled()),
            "batch_size": batch_size,
        })
    smoke_exact = all(row["exact_equal"] and row["all_finite"] for row in audit_records)
    print(json.dumps({
        "stage": "P0-M5 smoke", "encoder": encoder, "device": str(device),
        "shape": list(first.shape), "exact_repeat": smoke_exact,
        "max_abs_difference": max(row["max_abs_difference"] for row in audit_records),
    }, indent=2), flush=True)
    if not smoke_exact:
        raise RuntimeError(f"{encoder} deterministic smoke failed")
    if smoke_only:
        del model, audit_tensor
        torch.cuda.empty_cache()
        return

    features = np.empty((len(manifest), M5_DIMENSION[encoder]), dtype=np.float32)
    crop_hashes = np.empty(len(manifest), dtype=object)
    processed = 0
    for he_path, slide_rows in manifest.groupby("he_path", sort=False):
        for start in range(0, len(slide_rows), batch_size):
            part = slide_rows.iloc[start:start + batch_size]
            crops, hashes = m5_read_crops(part)
            tensor = transform_m5_crops(transform, crops).to(device)
            with torch.inference_mode():
                output = m5_embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
            if output.shape != (len(part), M5_DIMENSION[encoder]):
                raise RuntimeError(f"unexpected {encoder} embedding shape: {output.shape}")
            positions = part.embedding_row.to_numpy(dtype=int)
            features[positions] = output
            crop_hashes[positions] = hashes
            processed += len(part)
        print(
            f"P0-M5 {encoder}: {Path(he_path).name} complete ({processed}/{len(manifest)})",
            flush=True,
        )
    if not np.isfinite(features).all() or any(value is None for value in crop_hashes):
        raise RuntimeError(f"{encoder} extraction produced missing/nonfinite values")
    array_path = OUT / M5_ARRAY_FILE[encoder]
    partial_path = array_path.with_name(array_path.stem + ".partial.npy")
    np.save(partial_path, features, allow_pickle=False)
    os.replace(partial_path, array_path)

    manifest_path = OUT / "paired_embedding_manifest.csv"
    if manifest_path.exists():
        paired = pd.read_csv(manifest_path, keep_default_na=False)
        if list(paired.columns) != M5_SCHEMAS["paired_embedding_manifest.csv"]:
            raise RuntimeError("existing paired embedding manifest schema changed")
        if not paired.tile_id.equals(manifest.tile_id):
            raise RuntimeError("existing paired embedding manifest tile order changed")
    else:
        paired = pd.DataFrame({
            "embedding_row": manifest.embedding_row,
            "tile_id": manifest.tile_id,
            "subject_id": manifest.subject_id,
            "image_id": manifest.image_id,
            "fold": manifest.fold,
            "inclusion_status": manifest.inclusion_status,
            "level0_x0": manifest.level0_x0,
            "level0_y0": manifest.level0_y0,
            "level0_x1": manifest.level0_x1,
            "level0_y1": manifest.level0_y1,
            "physical_fov_um": manifest.physical_fov_um,
            "same_boundary_for_both_models": manifest.same_boundary_for_both_models,
            "conch_input_px": manifest.conch_input_px,
            "virchow_input_px": manifest.virchow_input_px,
            "conch_crop_sha256": "", "virchow_crop_sha256": "",
            "crop_hash_match": False,
            "conch_embedding_status": "not_extracted",
            "virchow_embedding_status": "not_extracted",
        }, columns=M5_SCHEMAS["paired_embedding_manifest.csv"])
    paired[f"{encoder}_crop_sha256"] = crop_hashes
    paired[f"{encoder}_embedding_status"] = "complete_finite"
    paired["crop_hash_match"] = (
        paired.conch_crop_sha256.ne("") & paired.virchow_crop_sha256.ne("")
        & paired.conch_crop_sha256.eq(paired.virchow_crop_sha256)
    )
    write_m5_table("paired_embedding_manifest.csv", paired[M5_SCHEMAS["paired_embedding_manifest.csv"]])

    audit_path = OUT / "embedding_determinism_audit.csv"
    if audit_path.exists():
        audit = pd.read_csv(audit_path)
        audit = audit[audit.encoder.ne(encoder)]
    else:
        audit = pd.DataFrame(columns=M5_SCHEMAS["embedding_determinism_audit.csv"])
    new_audit = pd.DataFrame(audit_records, columns=M5_SCHEMAS["embedding_determinism_audit.csv"])
    audit = new_audit if audit.empty else pd.concat([audit, new_audit], ignore_index=True)
    audit = audit.sort_values(["encoder", "audit_order"]).reset_index(drop=True)
    write_m5_table("embedding_determinism_audit.csv", audit[M5_SCHEMAS["embedding_determinism_audit.csv"]])
    print(json.dumps({
        "stage": "P0-M5 extraction", "encoder": encoder, "rows": len(features),
        "dimension": features.shape[1], "array_sha256": sha256_file(array_path),
    }, indent=2), flush=True)
    del model, audit_tensor, features
    gc.collect()
    torch.cuda.empty_cache()
    if all((OUT / M5_ARRAY_FILE[name]).exists() for name in ("conch", "virchow")):
        finalize_m5()


def finalize_m5() -> None:
    manifest = prepare_m5_manifest()
    paired = pd.read_csv(OUT / "paired_embedding_manifest.csv", keep_default_na=False)
    audit = pd.read_csv(OUT / "embedding_determinism_audit.csv")
    if list(paired.columns) != M5_SCHEMAS["paired_embedding_manifest.csv"]:
        raise RuntimeError("P0-M5 paired embedding manifest schema changed")
    if not paired.tile_id.equals(manifest.tile_id):
        raise RuntimeError("P0-M5 tile order does not match P0-M4")
    crop_match = bool(paired.crop_hash_match.all())
    paired_ids_match = bool(paired.tile_id.is_unique and len(paired) == len(manifest))
    qc_rows = []
    for encoder in ("conch", "virchow"):
        spec = m5_model_spec(encoder)
        array_path = OUT / M5_ARRAY_FILE[encoder]
        values = np.load(array_path, mmap_mode="r", allow_pickle=False)
        norms = np.linalg.norm(values, axis=1)
        encoder_audit = audit[audit.encoder.eq(encoder)]
        determinism_exact = bool(
            len(encoder_audit) == 8
            and encoder_audit.exact_equal.astype(bool).all()
            and encoder_audit.all_finite.astype(bool).all()
            and encoder_audit.max_abs_difference.eq(0).all()
        )
        complete = bool(
            values.shape == (len(manifest), M5_DIMENSION[encoder])
            and values.dtype == np.float32
            and np.isfinite(values).all()
            and (norms > 0).all()
            and paired_ids_match and crop_match and determinism_exact
            and paired[f"{encoder}_embedding_status"].eq("complete_finite").all()
        )
        qc_rows.append({
            "encoder": encoder.upper() if encoder == "conch" else "Virchow",
            "model_id": spec["model_id"], "model_revision": spec["revision"],
            "weights_sha256": sha256_file(Path(spec["weights"])),
            "output_file": array_path.name, "output_sha256": sha256_file(array_path),
            "expected_rows": len(manifest), "observed_rows": values.shape[0],
            "expected_dimension": M5_DIMENSION[encoder], "observed_dimension": values.shape[1],
            "dtype": str(values.dtype), "n_nonfinite_values": int((~np.isfinite(values)).sum()),
            "n_zero_norm_rows": int((norms == 0).sum()), "norm_min": float(norms.min()),
            "norm_median": float(np.median(norms)), "norm_max": float(norms.max()),
            "n_duplicate_tile_ids": int(paired.tile_id.duplicated().sum()),
            "paired_tile_ids_match": paired_ids_match, "crop_hashes_match": crop_match,
            "determinism_exact": determinism_exact,
            "technical_status": "pass" if complete else "fail",
        })
    qc = pd.DataFrame(qc_rows, columns=M5_SCHEMAS["embedding_technical_qc.csv"])
    write_m5_table("embedding_technical_qc.csv", qc)

    inventory = pd.read_csv(OUT / "source_inventory.csv")
    changed = []
    for row in inventory[inventory.category.isin({"whole_slide_image", "model_weight"})].itertuples(index=False):
        if sha256_file(Path(row.resolved_path)) != row.sha256_pre:
            changed.append(row.source_id)
    technical_pass = bool(qc.technical_status.eq("pass").all() and not changed)
    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    gate = gates.gate_id.eq("P0-G5")
    gates.loc[gate, "status"] = "pass_technical_paired_embeddings" if technical_pass else "stop_technical_embedding_failure"
    gates.loc[gate, "draft_decision"] = "Pass" if technical_pass else "Stop"
    gates.loc[gate, "entry_condition_met"] = technical_pass
    gates.loc[gate, "direct_evidence"] = "paired_embedding_manifest.csv; embedding_determinism_audit.csv; embedding_technical_qc.csv; M5_TECHNICAL_REPORT.md"
    gates.loc[gate, "unresolved_risk"] = "shared GPU execution; descriptive tumor target only; no concept inference yet"
    gates.loc[gate, "next_unlocked"] = "P0-M6 descriptive tumor concept OOF/permutation" if technical_pass else "none"
    gates.loc[gate, "still_prohibited"] = "confirmatory target claims; stroma secondary claim; encoder superiority; clinical/PNI claims"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])

    unlock = pd.read_csv(OUT / "main_study_unlock_matrix.csv")
    fm3 = unlock.main_stage.eq("FM3")
    unlock.loc[fm3, "current_status"] = "technical_embeddings_ready_descriptive_tumor_only" if technical_pass else "stopped_at_P0_G5"
    unlock.loc[fm3, "currently_allowed"] = "P0-M6 descriptive tumor probe/permutation preparation" if technical_pass else "technical discrepancy review"
    unlock.loc[fm3, "currently_prohibited"] = "confirmatory benchmark; cross-model superiority; clinical or whole-slide PNI claim"
    unlock.loc[fm3, "evidence"] = "embedding_technical_qc.csv; p0_gate_matrix.csv"
    write_table("main_study_unlock_matrix.csv", unlock[TABLE_SCHEMAS["main_study_unlock_matrix.csv"]])

    deviations = pd.read_csv(OUT / "deviation_log.csv")
    compute = deviations.deviation_id.eq("D011")
    deviations.loc[compute, "observed"] = "GPU driver available outside sandbox; extraction ran on an explicitly selected shared device"
    deviations.loc[compute, "impact"] = "P0-M5 technical extraction completed; shared-device load retained as execution context"
    deviations.loc[compute, "required_action"] = "retain device/process snapshot and do not infer performance timing"
    deviations.loc[compute, "status"] = "resolved_with_shared_device_limit" if technical_pass else "open"
    deviations.loc[compute, "evidence"] = "embedding_technical_qc.csv; run_config.json"
    write_table("deviation_log.csv", deviations[TABLE_SCHEMAS["deviation_log.csv"]])

    report = [
        "# P0-M5 paired embedding technical report", "",
        f"- Protocol: `{PROTOCOL_ID}`",
        f"- P0-G5 decision: **{'Pass' if technical_pass else 'Stop'}**", "",
        "## Technical evidence", "",
        f"- Locked eligible universe: {len(manifest)} tiles / {manifest.subject_id.nunique()} subjects",
        f"- Same decoded level-0 crop bytes for both encoders: {crop_match}",
    ]
    for row in qc.itertuples(index=False):
        report.append(
            f"- {row.encoder}: shape {row.observed_rows}×{row.observed_dimension}, dtype {row.dtype}, "
            f"nonfinite={row.n_nonfinite_values}, zero_norm={row.n_zero_norm_rows}, "
            f"8-tile exact repeat={row.determinism_exact}, status={row.technical_status}"
        )
    report.extend([
        "", "## Interpretation boundary", "",
        "This gate establishes technical pairedness and deterministic frozen-feature extraction only. "
        "It does not establish above-chance target recovery, encoder superiority, clinical validation, "
        "or whole-slide PNI performance. Tumor fraction remains descriptive-only; stroma remains exploratory.",
    ])
    (OUT / "M5_TECHNICAL_REPORT.md").write_text("\n".join(report) + "\n")
    config = json.loads((OUT / "run_config.json").read_text())
    config["stage_executed"] = "P0-M0-M5 technical paired embedding extraction"
    config["stage_not_executed"] = "P0-M6+ concept inference, robustness, integrated decision"
    config["m5"] = {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "eligible_tiles": len(manifest), "subjects": int(manifest.subject_id.nunique()),
        "batch_sizes": M5_BATCH_SIZE, "float_precision": "float32; no autocast; TF32 disabled",
        "deterministic_algorithms": True, "crop_hashes_match": crop_match,
        "all_wsi_and_model_weight_hashes_match": not changed,
        "p0_g5_status": gates.loc[gate, "status"].iloc[0],
        "claim_limit": "technical paired embedding evidence only; descriptive tumor target",
    }
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"run_config.json", "PROTOCOL.md", "run_preexperiment.py"}
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    if not technical_pass:
        raise RuntimeError(f"P0-G5 technical gate failed; changed sources={changed}")
    print(json.dumps({
        "P0-G5": "Pass", "rows": len(manifest),
        "dimensions": M5_DIMENSION, "crop_hash_match": crop_match,
    }, indent=2), flush=True)


def write_m6_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M6_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def prepare_m6_inputs() -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, str]]:
    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    if not gates.loc[gates.gate_id.eq("P0-G5"), "status"].eq("pass_technical_paired_embeddings").all():
        raise RuntimeError("P0-M6 requires P0-G5 technical pass")
    paired = pd.read_csv(OUT / "paired_embedding_manifest.csv", keep_default_na=False)
    if list(paired.columns) != M5_SCHEMAS["paired_embedding_manifest.csv"]:
        raise RuntimeError("P0-M5 paired embedding manifest schema changed")
    if len(paired) != 1218 or not paired.crop_hash_match.all() or paired.tile_id.duplicated().any():
        raise RuntimeError("P0-M5 paired universe/hash condition no longer holds")
    targets = pd.read_csv(OUT / "quantitative_targets.csv").set_index("tile_id")
    if not set(paired.tile_id) <= set(targets.index):
        raise RuntimeError("P0-M6 target rows are missing")
    aligned = targets.loc[paired.tile_id].reset_index()
    for column in ("subject_id", "image_id", "fold"):
        if not np.array_equal(aligned[column].to_numpy(), paired[column].to_numpy()):
            raise RuntimeError(f"P0-M6 paired/target mismatch in {column}")
    if not aligned.tumor_target_status.eq("eligible_descriptive").all():
        raise RuntimeError("P0-M6 contains a non-eligible tumor target")
    if not np.isfinite(aligned.tumor_fraction).all():
        raise RuntimeError("P0-M6 tumor truth contains missing/nonfinite values")
    analysis = paired[[
        "embedding_row", "tile_id", "subject_id", "image_id", "fold",
    ]].copy()
    analysis["truth"] = aligned.tumor_fraction.to_numpy(float)
    arrays: dict[str, np.ndarray] = {}
    hashes: dict[str, str] = {}
    technical_qc = pd.read_csv(OUT / "embedding_technical_qc.csv").set_index("encoder")
    for encoder, label in (("CONCH", "CONCH"), ("Virchow", "Virchow")):
        key = encoder.lower()
        path = OUT / M5_ARRAY_FILE[key]
        current_hash = sha256_file(path)
        if current_hash != technical_qc.loc[label, "output_sha256"]:
            raise RuntimeError(f"P0-M6 {encoder} embedding hash changed")
        values = np.load(path, mmap_mode="r", allow_pickle=False)
        if values.shape != (len(analysis), M5_DIMENSION[key]) or not np.isfinite(values).all():
            raise RuntimeError(f"P0-M6 {encoder} embedding array invalid")
        arrays[encoder] = np.asarray(values, dtype=np.float32)
        hashes[encoder] = current_hash
    return analysis, arrays, hashes


def m6_nested_oof(
    X: np.ndarray, y: np.ndarray, folds: np.ndarray, groups: np.ndarray, encoder: str
) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    predictions, selected = nested_fixed_fold_oof(X, y, folds, binary=False)
    diagnostics: list[dict[str, object]] = []
    for outer in sorted(np.unique(folds)):
        train, test = folds != outer, folds == outer
        values = np.unique(selected[test])
        if len(values) != 1:
            raise RuntimeError(f"P0-M6 fold {outer} does not have one selected alpha")
        alpha = float(values[0])
        model = make_probe(False, alpha)
        model.fit(X[train], y[train])
        train_prediction = model.predict(X[train])
        test_prediction = predictions[test]
        metrics: dict[str, float] = {}
        reasons: list[str] = []
        for split, truth, prediction in (
            ("train", y[train], train_prediction), ("test", y[test], test_prediction),
        ):
            for metric in ("mae", "r2", "spearman"):
                estimate, reason = safe_metric(metric, truth, prediction)
                metrics[f"{split}_{metric}"] = estimate
                if reason:
                    reasons.append(f"{split}_{metric}:{reason}")
        diagnostics.append({
            "target_id": "tumor_fraction", "encoder": encoder, "fold": int(outer),
            "selected_alpha": alpha, "n_train_tiles": int(train.sum()),
            "n_test_tiles": int(test.sum()), "n_train_subjects": int(np.unique(groups[train]).size),
            "n_test_subjects": int(np.unique(groups[test]).size),
            "train_target_min": float(y[train].min()), "train_target_max": float(y[train].max()),
            "test_target_min": float(y[test].min()), "test_target_max": float(y[test].max()),
            "train_mae": metrics["train_mae"], "test_mae": metrics["test_mae"],
            "train_r2": metrics["train_r2"], "test_r2": metrics["test_r2"],
            "train_spearman": metrics["train_spearman"], "test_spearman": metrics["test_spearman"],
            "spearman_generalization_gap": metrics["train_spearman"] - metrics["test_spearman"],
            "diagnostic_status": "pass" if not reasons else "undefined:" + "|".join(reasons),
        })
    return predictions, selected, diagnostics


def m6_analysis_frame(
    analysis: pd.DataFrame, prediction: np.ndarray, unit: str
) -> pd.DataFrame:
    frame = pd.DataFrame({
        "group_id": analysis.subject_id.astype(str), "truth": analysis.truth.to_numpy(float),
        "prediction": np.asarray(prediction, dtype=float), "outcome_time": np.nan,
    })
    if unit == "tile_clustered_by_subject":
        return frame
    if unit == "subject_mean":
        return frame.groupby("group_id", as_index=False).agg(
            truth=("truth", "mean"), prediction=("prediction", "mean"),
            outcome_time=("outcome_time", "mean"),
        )
    raise ValueError(unit)


def run_m6() -> None:
    started = datetime.now(timezone.utc)
    analysis, arrays, embedding_hashes = prepare_m6_inputs()
    folds = analysis.fold.to_numpy(int)
    groups = analysis.subject_id.astype(str).to_numpy()
    truth = analysis.truth.to_numpy(float)
    paired_manifest_hash = sha256_file(OUT / "paired_embedding_manifest.csv")
    fold_hash = sha256_file(OUT / "fold_assignments.csv")
    predictions: dict[str, np.ndarray] = {}
    selected: dict[str, np.ndarray] = {}
    fold_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        prediction, choice, diagnostics = m6_nested_oof(
            arrays[encoder], truth, folds, groups, encoder,
        )
        predictions[encoder], selected[encoder] = prediction, choice
        fold_rows.extend(diagnostics)
        print(f"P0-M6 {encoder} nested OOF complete", flush=True)

    prediction_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        for index, row in enumerate(analysis.itertuples(index=False)):
            prediction_rows.append({
                "target_id": "tumor_fraction", "encoder": encoder,
                "tile_id": row.tile_id, "subject_id": row.subject_id,
                "image_id": row.image_id, "fold": row.fold,
                "embedding_row": row.embedding_row, "truth": row.truth,
                "prediction": predictions[encoder][index],
                "prediction_status": "new_subject_grouped_nested_oof",
                "selected_alpha": selected[encoder][index],
                "source_embedding_file": M5_ARRAY_FILE[encoder.lower()],
                "source_embedding_sha256": embedding_hashes[encoder],
                "paired_manifest_sha256": paired_manifest_hash,
                "fold_assignment_sha256": fold_hash,
            })

    units = ("tile_clustered_by_subject", "subject_mean")
    metrics = ("mae", "r2", "spearman")
    frames = {
        (encoder, unit): m6_analysis_frame(analysis, predictions[encoder], unit)
        for encoder in ("CONCH", "Virchow") for unit in units
    }
    permutation_rows: list[dict[str, object]] = []
    null_values: dict[tuple[str, str], list[float]] = {}
    for encoder in ("CONCH", "Virchow"):
        subject_frame = frames[(encoder, "subject_mean")]
        tile_frame = frames[(encoder, "tile_clustered_by_subject")]
        subject_null: list[float] = []
        coordinate_null: list[float] = []
        subject_truth = subject_frame.truth.to_numpy()
        subject_prediction = subject_frame.prediction.to_numpy()
        tile_truth = tile_frame.truth.to_numpy()
        tile_prediction = tile_frame.prediction.to_numpy()
        group_indices = {
            group: np.flatnonzero(tile_frame.group_id.to_numpy() == group)
            for group in tile_frame.group_id.drop_duplicates()
        }
        for replicate in range(M6_N_PERMUTATIONS):
            seed = SEED + replicate
            rng = np.random.default_rng(seed)
            estimate, reason = safe_metric(
                "spearman", rng.permutation(subject_truth), subject_prediction,
            )
            subject_null.append(estimate)
            permutation_rows.append({
                "target_id": "tumor_fraction", "encoder": encoder,
                "null_type": "subject_mean_label_permutation",
                "analysis_unit": "subject_mean", "replicate_id": replicate,
                "permutation_seed": seed, "metric_name": "spearman",
                "estimate": estimate, "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                "undefined_reason": reason,
            })
            permuted_prediction = tile_prediction.copy()
            for indices in group_indices.values():
                permuted_prediction[indices] = rng.permutation(permuted_prediction[indices])
            estimate, reason = safe_metric("spearman", tile_truth, permuted_prediction)
            coordinate_null.append(estimate)
            permutation_rows.append({
                "target_id": "tumor_fraction", "encoder": encoder,
                "null_type": "within_subject_coordinate_permutation",
                "analysis_unit": "tile_clustered_by_subject", "replicate_id": replicate,
                "permutation_seed": seed, "metric_name": "spearman",
                "estimate": estimate, "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                "undefined_reason": reason,
            })
        null_values[(encoder, "subject_mean_label_permutation")] = subject_null
        null_values[(encoder, "within_subject_coordinate_permutation")] = coordinate_null
        print(f"P0-M6 {encoder} permutations complete", flush=True)

    bootstrap_rows: list[dict[str, object]] = []
    bootstrap_values: dict[tuple[str, str, str], list[float]] = {
        (encoder, unit, metric): []
        for encoder in ("CONCH", "Virchow") for unit in units for metric in metrics
    }
    unique_groups = pd.unique(groups)
    for replicate in range(M6_N_BOOTSTRAPS):
        seed = SEED + 1 + replicate
        sampled_groups = np.random.default_rng(seed).choice(
            unique_groups, size=len(unique_groups), replace=True,
        )
        for encoder in ("CONCH", "Virchow"):
            for unit in units:
                frame = frames[(encoder, unit)]
                for metric in metrics:
                    estimate, reason = resampled_metric(frame, metric, sampled_groups)
                    bootstrap_values[(encoder, unit, metric)].append(estimate)
                    bootstrap_rows.append({
                        "target_id": "tumor_fraction", "encoder": encoder,
                        "analysis_unit": unit, "replicate_id": replicate,
                        "bootstrap_seed": seed, "metric_name": metric,
                        "estimate": estimate,
                        "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                        "undefined_reason": reason,
                    })
    print("P0-M6 paired subject bootstraps complete", flush=True)

    summary_rows: list[dict[str, object]] = []
    gate_p_values: list[float] = []
    gate_row_indices: list[int] = []
    for encoder in ("CONCH", "Virchow"):
        for unit in units:
            frame = frames[(encoder, unit)]
            for metric in metrics:
                estimate, reason = safe_metric(metric, frame.truth, frame.prediction)
                if reason:
                    raise RuntimeError(f"P0-M6 observed {encoder}/{unit}/{metric} undefined: {reason}")
                distribution = np.asarray(bootstrap_values[(encoder, unit, metric)], dtype=float)
                valid_bootstrap = distribution[np.isfinite(distribution)]
                null_type = ""
                p95 = empirical_p = np.nan
                gate: object = "not_gate_metric"
                if metric == "spearman" and unit == "subject_mean":
                    null_type = "subject_mean_label_permutation"
                    null = np.asarray(null_values[(encoder, null_type)], dtype=float)
                    valid_null = null[np.isfinite(null)]
                    p95 = float(np.quantile(valid_null, 0.95))
                    empirical_p = float((1 + np.sum(valid_null >= estimate)) / (1 + len(valid_null)))
                    gate = bool(estimate > p95)
                elif metric == "spearman" and unit == "tile_clustered_by_subject":
                    null_type = "within_subject_coordinate_permutation"
                    null = np.asarray(null_values[(encoder, null_type)], dtype=float)
                    valid_null = null[np.isfinite(null)]
                    p95 = float(np.quantile(valid_null, 0.95))
                    empirical_p = float((1 + np.sum(valid_null >= estimate)) / (1 + len(valid_null)))
                summary_rows.append({
                    "target_id": "tumor_fraction",
                    "target_role": "descriptive_primary_candidate_not_confirmatory",
                    "encoder": encoder, "analysis_unit": unit, "metric_name": metric,
                    "estimate": estimate,
                    "ci_low": float(np.quantile(valid_bootstrap, 0.025)),
                    "ci_high": float(np.quantile(valid_bootstrap, 0.975)),
                    "n_tiles": len(analysis), "n_subjects": analysis.subject_id.nunique(),
                    "n_valid_bootstrap": len(valid_bootstrap),
                    "n_undefined_bootstrap": int((~np.isfinite(distribution)).sum()),
                    "permutation_null_type": null_type, "permutation_p95": p95,
                    "empirical_p": empirical_p, "empirical_q": np.nan,
                    "gate_exceedance": gate,
                })
                if metric == "spearman" and unit == "subject_mean":
                    gate_row_indices.append(len(summary_rows) - 1)
                    gate_p_values.append(empirical_p)
    adjusted = bh_adjust(gate_p_values)
    for index, q_value in zip(gate_row_indices, adjusted, strict=True):
        summary_rows[index]["empirical_q"] = q_value

    delta_rows: list[dict[str, object]] = []
    for unit in units:
        for metric in metrics:
            conch_frame, virchow_frame = frames[("CONCH", unit)], frames[("Virchow", unit)]
            conch_estimate, _ = safe_metric(metric, conch_frame.truth, conch_frame.prediction)
            virchow_estimate, _ = safe_metric(metric, virchow_frame.truth, virchow_frame.prediction)
            distribution = (
                np.asarray(bootstrap_values[("CONCH", unit, metric)], dtype=float)
                - np.asarray(bootstrap_values[("Virchow", unit, metric)], dtype=float)
            )
            valid = distribution[np.isfinite(distribution)]
            delta_rows.append({
                "target_id": "tumor_fraction", "analysis_unit": unit,
                "metric_name": metric, "conch_estimate": conch_estimate,
                "virchow_estimate": virchow_estimate,
                "paired_delta_conch_minus_virchow": conch_estimate - virchow_estimate,
                "ci_low": float(np.quantile(valid, 0.025)),
                "ci_high": float(np.quantile(valid, 0.975)),
                "n_valid_bootstrap": len(valid),
                "n_undefined_bootstrap": int((~np.isfinite(distribution)).sum()),
                "direction_note": "negative favors CONCH" if metric == "mae" else "positive favors CONCH",
            })

    oof = pd.DataFrame(prediction_rows, columns=M6_SCHEMAS["concept_oof_predictions.csv"])
    summary = pd.DataFrame(summary_rows, columns=M6_SCHEMAS["concept_summary.csv"])
    deltas = pd.DataFrame(delta_rows, columns=M6_SCHEMAS["concept_paired_deltas.csv"])
    permutations = pd.DataFrame(permutation_rows, columns=M6_SCHEMAS["concept_permutation_null.csv"])
    bootstraps = pd.DataFrame(bootstrap_rows, columns=M6_SCHEMAS["concept_bootstrap_replicates.csv"])
    diagnostics = pd.DataFrame(fold_rows, columns=M6_SCHEMAS["concept_fold_diagnostics.csv"])
    write_m6_table("concept_oof_predictions.csv", oof)
    write_m6_table("concept_summary.csv", summary)
    write_m6_table("concept_paired_deltas.csv", deltas)
    write_m6_table("concept_permutation_null.csv", permutations)
    write_m6_table("concept_bootstrap_replicates.csv", bootstraps)
    write_m6_table("concept_fold_diagnostics.csv", diagnostics)

    gate_results = summary[
        summary.analysis_unit.eq("subject_mean") & summary.metric_name.eq("spearman")
    ].set_index("encoder")
    passing = [encoder for encoder in ("CONCH", "Virchow") if bool(gate_results.loc[encoder, "gate_exceedance"])]
    if passing:
        decision = "Conditional Pass"
        status = "conditional_pass_descriptive_tumor_" + "_and_".join(name.lower() for name in passing)
    else:
        decision = "Stop"
        status = "stop_no_above_chance_descriptive_tumor_combination"
    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    gate = gates.gate_id.eq("P0-G6")
    gates.loc[gate, "status"] = status
    gates.loc[gate, "draft_decision"] = decision
    gates.loc[gate, "entry_condition_met"] = bool(passing)
    gates.loc[gate, "direct_evidence"] = "concept_oof_predictions.csv; concept_summary.csv; concept_permutation_null.csv; concept_bootstrap_replicates.csv; concept_fold_diagnostics.csv; M6_CONCEPT_REPORT.md"
    gates.loc[gate, "unresolved_risk"] = "single descriptive target; quantitative repeatability absent; zero-inflated target; 25 subjects"
    gates.loc[gate, "next_unlocked"] = (
        "P0-M7 sensitivity for " + ", ".join(f"{name}-tumor-394.24um" for name in passing)
        if passing else "none"
    )
    gates.loc[gate, "still_prohibited"] = "strong G6 claim; confirmatory target; encoder superiority; clinical or PNI claims"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])

    claims = pd.read_csv(OUT / "claim_evidence_matrix.csv")
    if not claims.claim_id.eq("C09").any():
        claims = pd.concat([claims, governance_tables()[0].query("claim_id == 'C09'")], ignore_index=True)
    claim = claims.claim_id.eq("C09")
    claims.loc[claim, "status"] = "supported_descriptive_conditional" if passing else "not_supported"
    claims.loc[claim, "current_evidence"] = "; ".join(
        f"{encoder}:rho={gate_results.loc[encoder, 'estimate']:.4f},p95={gate_results.loc[encoder, 'permutation_p95']:.4f},q={gate_results.loc[encoder, 'empirical_q']:.4g},pass={bool(gate_results.loc[encoder, 'gate_exceedance'])}"
        for encoder in ("CONCH", "Virchow")
    )
    claims.loc[claim, "allowed_wording"] = (
        "descriptive tumor fraction recoverability above subject-grouped chance for: " + ", ".join(passing)
        if passing else "no above-chance descriptive tumor recoverability demonstrated"
    )
    write_table("claim_evidence_matrix.csv", claims[TABLE_SCHEMAS["claim_evidence_matrix.csv"]])

    deviations = pd.read_csv(OUT / "deviation_log.csv")
    if not deviations.deviation_id.eq("D012").any():
        deviations = pd.concat([deviations, governance_tables()[1].query("deviation_id == 'D012'")], ignore_index=True)
    deviation = deviations.deviation_id.eq("D012")
    deviations.loc[deviation, "observed"] = "only one descriptive target available; tumor median=0; passing encoders=" + ",".join(passing)
    deviations.loc[deviation, "impact"] = "G6 capped at Conditional Pass; only passing model-tumor combinations may enter M7"
    deviations.loc[deviation, "status"] = "open_limited"
    deviations.loc[deviation, "evidence"] = "concept_summary.csv; target_availability.csv; M6_CONCEPT_REPORT.md"
    write_table("deviation_log.csv", deviations[TABLE_SCHEMAS["deviation_log.csv"]])

    unlock = pd.read_csv(OUT / "main_study_unlock_matrix.csv")
    fm4 = unlock.main_stage.eq("FM4")
    unlock.loc[fm4, "current_status"] = "conditional_descriptive_combinations_only" if passing else "stopped_at_P0_G6"
    unlock.loc[fm4, "currently_allowed"] = (
        "P0-M7 sensitivity for " + ", ".join(passing) if passing else "target/reliability redesign only"
    )
    unlock.loc[fm4, "currently_prohibited"] = "large confirmatory benchmark; encoder superiority; clinical or PNI inference"
    unlock.loc[fm4, "evidence"] = "concept_summary.csv; p0_gate_matrix.csv"
    write_table("main_study_unlock_matrix.csv", unlock[TABLE_SCHEMAS["main_study_unlock_matrix.csv"]])

    report = [
        "# P0-M6 descriptive tumor concept-recovery report", "",
        f"- Protocol: `{PROTOCOL_ID}`", f"- P0-G6 decision: **{decision}** (`{status}`)",
        f"- Passing model–target–FOV combinations: {', '.join(passing) if passing else 'none'}", "",
        "## Primary subject-grouped inference", "",
        "| Encoder | Subject-mean Spearman | 95% subject-bootstrap CI | Permutation p95 | p | BH q | Gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for encoder in ("CONCH", "Virchow"):
        row = gate_results.loc[encoder]
        report.append(
            f"| {encoder} | {row.estimate:.4f} | [{row.ci_low:.4f}, {row.ci_high:.4f}] | "
            f"{row.permutation_p95:.4f} | {row.empirical_p:.4g} | {row.empirical_q:.4g} | {row.gate_exceedance} |"
        )
    report.extend(["", "## Tile-level descriptive results", ""])
    for encoder in ("CONCH", "Virchow"):
        rows = summary[(summary.encoder == encoder) & (summary.analysis_unit == "tile_clustered_by_subject")].set_index("metric_name")
        report.append(
            f"- {encoder}: MAE={rows.loc['mae', 'estimate']:.4f}, R²={rows.loc['r2', 'estimate']:.4f}, "
            f"Spearman={rows.loc['spearman', 'estimate']:.4f}; within-subject coordinate-null "
            f"p95={rows.loc['spearman', 'permutation_p95']:.4f}."
        )
    report.extend([
        "", "## Interpretation boundary", "",
        "The primary statistic is one subject-level aggregate per person; tile metrics use subject-cluster "
        "uncertainty and are descriptive. Because only one non-confirmatory target survived G1, a strong G6 "
        "pass is impossible by design. This result does not establish encoder superiority, clinical validity, "
        "whole-slide diagnosis, or PNI performance. Stroma, nuclei, and gland/lumen are not inferred here.",
    ])
    (OUT / "M6_CONCEPT_REPORT.md").write_text("\n".join(report) + "\n")

    config = json.loads((OUT / "run_config.json").read_text())
    config["stage_executed"] = "P0-M0-M6 descriptive tumor concept inference"
    config["stage_not_executed"] = "P0-M7+ sensitivity, integrated decision and handoff"
    config["m6"] = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": "tumor_fraction_descriptive_not_confirmatory",
        "tiles": len(analysis), "subjects": int(analysis.subject_id.nunique()),
        "outer_folds": 5, "alpha_grid": M6_ALPHA_GRID.tolist(),
        "permutations": M6_N_PERMUTATIONS, "bootstraps": M6_N_BOOTSTRAPS,
        "primary_gate_metric": "subject_mean_spearman",
        "conditional_permutation_no_refit": True,
        "passing_encoders": passing, "p0_g6_status": status,
        "strong_pass_unavailable_reason": "only one descriptive target survived G1",
    }
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"run_config.json", "PROTOCOL.md", "run_preexperiment.py"}
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "P0-G6": decision, "status": status, "passing_encoders": passing,
        "subject_mean_spearman": {
            encoder: float(gate_results.loc[encoder, "estimate"]) for encoder in ("CONCH", "Virchow")
        },
    }, indent=2), flush=True)


def write_m7_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M7_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def write_m8_table(name: str, frame: pd.DataFrame) -> None:
    if list(frame.columns) != M8_SCHEMAS[name]:
        raise ValueError(f"schema mismatch for {name}: {list(frame.columns)}")
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def m8_draft_decision(gate_status: dict[str, str]) -> str:
    """Apply the locked M8 rule without inferring human approval."""
    required = {f"P0-G{number}" for number in range(8)}
    if not required <= set(gate_status):
        return "Revise/Stop"
    integrity_ok = (
        gate_status["P0-G0"] == "pass"
        and gate_status["P0-G2"].startswith(("pass", "conditional_pass"))
        and gate_status["P0-G3"].startswith("pass")
        and gate_status["P0-G5"].startswith("pass")
    )
    if not integrity_ok or gate_status["P0-G7"].startswith("red"):
        return "Revise/Stop"
    conditional = any(
        gate_status[gate].startswith("conditional_pass")
        for gate in ("P0-G1", "P0-G2", "P0-G4", "P0-G6")
    ) or gate_status["P0-G7"].startswith("amber")
    return "Conditional Go" if conditional else "Go"


def prepare_m7_native_manifest() -> pd.DataFrame:
    paired = pd.read_csv(OUT / "paired_embedding_manifest.csv", keep_default_na=False)
    m4 = pd.read_csv(OUT / "paired_tile_manifest.csv", keep_default_na=False).set_index("tile_id")
    if len(paired) != 1218 or not set(paired.tile_id) <= set(m4.index):
        raise RuntimeError("P0-M7 native manifest cannot reconcile P0-M4/M5")
    aligned = m4.loc[paired.tile_id].reset_index()
    rows: list[dict[str, object]] = []
    for embedding_row, row in enumerate(aligned.itertuples(index=False)):
        if row.inclusion_status != "eligible_descriptive_tumor":
            raise RuntimeError("P0-M7 native manifest contains an ineligible tile")
        crop_px = int(round(M7_NATIVE_FOV_UM / float(row.native_mpp_x)))
        x0 = int(math.floor(float(row.center_x) - crop_px / 2))
        y0 = int(math.floor(float(row.center_y) - crop_px / 2))
        x1, y1 = x0 + crop_px, y0 + crop_px
        if not (
            int(row.level0_x0) <= x0 < x1 <= int(row.level0_x1)
            and int(row.level0_y0) <= y0 < y1 <= int(row.level0_y1)
        ):
            raise RuntimeError(f"native crop leaves shared boundary: {row.tile_id}")
        rows.append({
            "embedding_row": embedding_row, "tile_id": row.tile_id,
            "subject_id": row.subject_id, "image_id": row.image_id, "fold": row.fold,
            "he_path": row.he_path, "center_x": row.center_x, "center_y": row.center_y,
            "native_mpp_x": row.native_mpp_x, "native_mpp_y": row.native_mpp_y,
            "level0_x0": x0, "level0_y0": y0, "level0_x1": x1, "level0_y1": y1,
            "crop_px": crop_px, "physical_fov_um": crop_px * float(row.native_mpp_x),
            "physical_fov_error_um": crop_px * float(row.native_mpp_x) - M7_NATIVE_FOV_UM,
            "crop_sha256": "", "embedding_status": "not_extracted",
        })
    return pd.DataFrame(rows, columns=M7_SCHEMAS["m7_native_fov_manifest.csv"])


def run_m7_native_extraction(smoke_only: bool = False) -> None:
    import torch

    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    if not gates.loc[gates.gate_id.eq("P0-G6"), "status"].str.startswith("conditional_pass").all():
        raise RuntimeError("P0-M7 requires conditional P0-G6 pass")
    manifest = prepare_m7_native_manifest()
    device = configure_m5_determinism()
    model, transform = load_m5_model("virchow", device)
    audit_rows = manifest.iloc[m5_audit_indices(len(manifest))]
    audit_crops: list[np.ndarray] = []
    for index in audit_rows.index:
        crops, _ = m5_read_crops(manifest.loc[[index]])
        audit_crops.extend(crops)
    tensor = transform_m5_crops(transform, audit_crops).to(device)
    with torch.inference_mode():
        first = m5_embed_batch("virchow", model, tensor).detach().cpu().float().numpy()
        second = m5_embed_batch("virchow", model, tensor).detach().cpu().float().numpy()
    audit_rows_out = []
    for order, (row, left, right) in enumerate(
        zip(audit_rows.itertuples(index=False), first, second, strict=True)
    ):
        audit_rows_out.append({
            "configuration": "Virchow_native_98.56um", "tile_id": row.tile_id,
            "audit_order": order,
            "first_feature_sha256": hashlib.sha256(left.tobytes()).hexdigest(),
            "second_feature_sha256": hashlib.sha256(right.tobytes()).hexdigest(),
            "exact_equal": bool(np.array_equal(left, right)),
            "max_abs_difference": float(np.max(np.abs(left - right))),
            "all_finite": bool(np.isfinite(left).all() and np.isfinite(right).all()),
            "batch_size": M5_BATCH_SIZE["virchow"],
        })
    audit = pd.DataFrame(audit_rows_out, columns=M7_SCHEMAS["m7_native_determinism_audit.csv"])
    exact = bool(audit.exact_equal.all() and audit.all_finite.all() and audit.max_abs_difference.eq(0).all())
    print(json.dumps({
        "stage": "P0-M7 native smoke", "shape": list(first.shape),
        "exact_repeat": exact, "max_abs_difference": float(audit.max_abs_difference.max()),
    }, indent=2), flush=True)
    if not exact:
        raise RuntimeError("P0-M7 native determinism smoke failed")
    if smoke_only:
        del model, tensor
        torch.cuda.empty_cache()
        return

    features = np.empty((len(manifest), M5_DIMENSION["virchow"]), dtype=np.float32)
    hashes = np.empty(len(manifest), dtype=object)
    processed = 0
    for he_path, slide_rows in manifest.groupby("he_path", sort=False):
        for start in range(0, len(slide_rows), M5_BATCH_SIZE["virchow"]):
            part = slide_rows.iloc[start:start + M5_BATCH_SIZE["virchow"]]
            crops, crop_hashes = m5_read_crops(part)
            batch = transform_m5_crops(transform, crops).to(device)
            with torch.inference_mode():
                output = m5_embed_batch("virchow", model, batch).detach().cpu().float().numpy()
            positions = part.embedding_row.to_numpy(int)
            features[positions] = output
            hashes[positions] = crop_hashes
            processed += len(part)
        print(
            f"P0-M7 Virchow native: {Path(he_path).name} complete ({processed}/{len(manifest)})",
            flush=True,
        )
    if not np.isfinite(features).all() or (np.linalg.norm(features, axis=1) == 0).any():
        raise RuntimeError("P0-M7 native features failed finite/nonzero QC")
    array_path = OUT / "precise_virchow_native_fov_embeddings.npy"
    partial = OUT / "precise_virchow_native_fov_embeddings.partial.npy"
    np.save(partial, features, allow_pickle=False)
    os.replace(partial, array_path)
    manifest["crop_sha256"] = hashes
    manifest["embedding_status"] = "complete_finite"
    write_m7_table("m7_native_fov_manifest.csv", manifest)
    write_m7_table("m7_native_determinism_audit.csv", audit)

    inventory = pd.read_csv(OUT / "source_inventory.csv")
    changed = []
    for row in inventory[inventory.category.eq("whole_slide_image")].itertuples(index=False):
        if sha256_file(Path(row.resolved_path)) != row.sha256_pre:
            changed.append(row.source_id)
    values = np.load(array_path, mmap_mode="r", allow_pickle=False)
    technical_pass = bool(
        values.shape == (1218, 2560) and values.dtype == np.float32
        and np.isfinite(values).all() and (np.linalg.norm(values, axis=1) > 0).all()
        and manifest.tile_id.is_unique and exact and not changed
    )
    qc = pd.DataFrame([{
        "encoder": "Virchow", "fov_um": M7_NATIVE_FOV_UM,
        "output_file": array_path.name, "output_sha256": sha256_file(array_path),
        "expected_rows": 1218, "observed_rows": values.shape[0],
        "expected_dimension": 2560, "observed_dimension": values.shape[1],
        "dtype": str(values.dtype), "n_nonfinite_values": int((~np.isfinite(values)).sum()),
        "n_zero_norm_rows": int((np.linalg.norm(values, axis=1) == 0).sum()),
        "determinism_exact": exact, "manifest_rows": len(manifest),
        "unique_tile_ids": int(manifest.tile_id.nunique()),
        "source_hashes_match": not changed,
        "technical_status": "pass" if technical_pass else "fail",
    }], columns=M7_SCHEMAS["m7_native_embedding_qc.csv"])
    write_m7_table("m7_native_embedding_qc.csv", qc)
    if not technical_pass:
        raise RuntimeError(f"P0-M7 native technical extraction failed; changed={changed}")
    print(json.dumps({
        "stage": "P0-M7 native extraction", "rows": len(values), "dimension": values.shape[1],
        "array_sha256": sha256_file(array_path), "manifest_sha256": sha256_file(OUT / "m7_native_fov_manifest.csv"),
    }, indent=2), flush=True)
    del model, tensor, features
    gc.collect()
    torch.cuda.empty_cache()


def linear_cka(X: np.ndarray, Y: np.ndarray) -> float:
    Xc = np.asarray(X, dtype=np.float64) - np.asarray(X, dtype=np.float64).mean(axis=0, keepdims=True)
    Yc = np.asarray(Y, dtype=np.float64) - np.asarray(Y, dtype=np.float64).mean(axis=0, keepdims=True)
    gram_x, gram_y = Xc @ Xc.T, Yc @ Yc.T
    denominator = np.sqrt(np.sum(gram_x * gram_x) * np.sum(gram_y * gram_y))
    return float(np.sum(gram_x * gram_y) / denominator) if denominator > 0 else np.nan


def distance_rsa_spearman(X: np.ndarray, Y: np.ndarray) -> float:
    X = np.asarray(X, dtype=np.float64)
    Y = np.asarray(Y, dtype=np.float64)
    X = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), np.finfo(float).eps)
    Y = Y / np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), np.finfo(float).eps)
    upper = np.triu_indices(len(X), k=1)
    distance_x = (1.0 - X @ X.T)[upper]
    distance_y = (1.0 - Y @ Y.T)[upper]
    return float(stats.spearmanr(distance_x, distance_y).statistic)


def aggregate_features_by_subject(X: np.ndarray, groups: np.ndarray) -> np.ndarray:
    return np.stack([np.asarray(X)[groups == group].mean(axis=0) for group in pd.unique(groups)])


def cluster_bootstrap_interval(frame: pd.DataFrame, metric: str) -> tuple[float, float, int]:
    groups = frame.group_id.drop_duplicates().to_numpy()
    values = []
    for replicate in range(M6_N_BOOTSTRAPS):
        sampled = np.random.default_rng(SEED + 1 + replicate).choice(groups, size=len(groups), replace=True)
        estimate, _ = resampled_metric(frame, metric, sampled)
        values.append(estimate)
    array = np.asarray(values, dtype=float)
    valid = array[np.isfinite(array)]
    return (
        float(np.quantile(valid, 0.025)) if len(valid) else np.nan,
        float(np.quantile(valid, 0.975)) if len(valid) else np.nan,
        int((~np.isfinite(array)).sum()),
    )


def run_m7() -> None:
    started = datetime.now(timezone.utc)
    analysis, shared_arrays, embedding_hashes = prepare_m6_inputs()
    native_qc = pd.read_csv(OUT / "m7_native_embedding_qc.csv")
    native_manifest = pd.read_csv(OUT / "m7_native_fov_manifest.csv", keep_default_na=False)
    native_path = OUT / "precise_virchow_native_fov_embeddings.npy"
    if not native_qc.technical_status.eq("pass").all() or len(native_manifest) != len(analysis):
        raise RuntimeError("P0-M7 native technical evidence is incomplete")
    native_hash = sha256_file(native_path)
    if native_hash != native_qc.output_sha256.iloc[0]:
        raise RuntimeError("P0-M7 native embedding hash changed")
    native = np.asarray(np.load(native_path, mmap_mode="r", allow_pickle=False), dtype=np.float32)
    if not native_manifest.tile_id.equals(analysis.tile_id):
        raise RuntimeError("P0-M7 native/shared tile order mismatch")

    m6_oof = pd.read_csv(OUT / "concept_oof_predictions.csv")
    base_predictions = {}
    for encoder in ("CONCH", "Virchow"):
        part = m6_oof[m6_oof.encoder.eq(encoder)].set_index("tile_id").loc[analysis.tile_id]
        if not np.array_equal(part.truth.to_numpy(float), analysis.truth.to_numpy(float)):
            raise RuntimeError(f"P0-M7 {encoder} OOF truth mismatch")
        base_predictions[encoder] = part.prediction.to_numpy(float)
    folds = analysis.fold.to_numpy(int)
    groups = analysis.subject_id.astype(str).to_numpy()
    truth = analysis.truth.to_numpy(float)

    sensitivity_arrays = {
        "Virchow_native_98.56um": native,
        "Virchow_shared_CLS_only": shared_arrays["Virchow"][:, :1280],
        "Virchow_shared_patchmean_only": shared_arrays["Virchow"][:, 1280:],
    }
    sensitivity_predictions: dict[str, np.ndarray] = {}
    native_oof_rows: list[dict[str, object]] = []
    for configuration, values in sensitivity_arrays.items():
        prediction, selected, _ = m6_nested_oof(values, truth, folds, groups, configuration)
        sensitivity_predictions[configuration] = prediction
        source_hash = native_hash if configuration == "Virchow_native_98.56um" else embedding_hashes["Virchow"]
        for index, row in enumerate(analysis.itertuples(index=False)):
            native_oof_rows.append({
                "configuration": configuration, "tile_id": row.tile_id,
                "subject_id": row.subject_id, "fold": row.fold, "truth": row.truth,
                "prediction": prediction[index], "selected_alpha": selected[index],
                "source_embedding_sha256": source_hash,
                "prediction_status": "new_subject_grouped_nested_oof_sensitivity",
            })
        print(f"P0-M7 {configuration} nested OOF complete", flush=True)
    native_oof = pd.DataFrame(native_oof_rows, columns=M7_SCHEMAS["m7_native_oof_predictions.csv"])
    write_m7_table("m7_native_oof_predictions.csv", native_oof)

    configurations = {
        "CONCH_shared_394.24um": {
            "encoder": "CONCH", "fov": 394.24, "prediction": base_predictions["CONCH"],
            "features": shared_arrays["CONCH"],
        },
        "Virchow_shared_394.24um": {
            "encoder": "Virchow", "fov": 394.24, "prediction": base_predictions["Virchow"],
            "features": shared_arrays["Virchow"],
        },
        "Virchow_native_98.56um": {
            "encoder": "Virchow", "fov": 98.56,
            "prediction": sensitivity_predictions["Virchow_native_98.56um"], "features": native,
        },
        "Virchow_shared_CLS_only": {
            "encoder": "Virchow", "fov": 394.24,
            "prediction": sensitivity_predictions["Virchow_shared_CLS_only"],
            "features": shared_arrays["Virchow"][:, :1280],
        },
        "Virchow_shared_patchmean_only": {
            "encoder": "Virchow", "fov": 394.24,
            "prediction": sensitivity_predictions["Virchow_shared_patchmean_only"],
            "features": shared_arrays["Virchow"][:, 1280:],
        },
    }

    representation_rows: list[dict[str, object]] = []
    representation_pairs = (
        ("CONCH_shared_394.24um", "Virchow_shared_394.24um"),
        ("Virchow_shared_394.24um", "Virchow_native_98.56um"),
        ("CONCH_shared_394.24um", "Virchow_native_98.56um"),
    )
    for left_name, right_name in representation_pairs:
        for unit in ("tile", "subject_mean"):
            left = configurations[left_name]["features"]
            right = configurations[right_name]["features"]
            if unit == "subject_mean":
                left = aggregate_features_by_subject(left, groups)
                right = aggregate_features_by_subject(right, groups)
            for metric, estimate in (
                ("centered_linear_CKA", linear_cka(left, right)),
                ("pairwise_cosine_distance_RSA_spearman", distance_rsa_spearman(left, right)),
            ):
                representation_rows.append({
                    "representation_a": left_name, "representation_b": right_name,
                    "analysis_unit": unit, "n_units": len(left), "metric_name": metric,
                    "estimate": estimate,
                    "interpretation_limit": "descriptive representation similarity; dimensions and training differ",
                })
    representation = pd.DataFrame(representation_rows, columns=M7_SCHEMAS["representation_similarity.csv"])
    write_m7_table("representation_similarity.csv", representation)

    scale_rows: list[dict[str, object]] = []
    for configuration, item in configurations.items():
        for unit in ("tile_clustered_by_subject", "subject_mean"):
            frame = m6_analysis_frame(analysis, item["prediction"], unit)
            for metric in ("mae", "r2", "spearman"):
                estimate, _ = safe_metric(metric, frame.truth, frame.prediction)
                scale_rows.append({
                    "configuration": configuration, "encoder": item["encoder"],
                    "fov_um": item["fov"], "sensitivity_type": "full_configuration",
                    "tile_budget": "all", "draw_id": -1, "sampling_seed": -1,
                    "analysis_unit": unit, "metric_name": metric, "estimate": estimate,
                    "n_tiles": len(analysis), "n_subjects": analysis.subject_id.nunique(),
                    "direction_positive": bool(estimate > 0) if metric != "mae" else "not_applicable",
                    "paired_draw_id": "all_tiles",
                })
    group_indices = {
        group: np.flatnonzero(groups == group) for group in sorted(pd.unique(groups))
    }
    for draw in range(M7_N_SAMPLING_DRAWS):
        seed = SEED + 7000 + draw
        permutations = {
            group: np.random.default_rng(seed + index).permutation(indices)
            for index, (group, indices) in enumerate(group_indices.items())
        }
        for budget in M7_SAMPLING_BUDGETS:
            chosen = np.sort(np.concatenate([
                indices[:min(budget, len(indices))] for indices in permutations.values()
            ]))
            sampled_analysis = analysis.iloc[chosen].reset_index(drop=True)
            for configuration, item in configurations.items():
                sampled_prediction = np.asarray(item["prediction"])[chosen]
                frame = m6_analysis_frame(sampled_analysis, sampled_prediction, "subject_mean")
                estimate, _ = safe_metric("spearman", frame.truth, frame.prediction)
                scale_rows.append({
                    "configuration": configuration, "encoder": item["encoder"],
                    "fov_um": item["fov"], "sensitivity_type": "paired_tile_budget",
                    "tile_budget": budget, "draw_id": draw, "sampling_seed": seed,
                    "analysis_unit": "subject_mean", "metric_name": "spearman",
                    "estimate": estimate, "n_tiles": len(chosen),
                    "n_subjects": sampled_analysis.subject_id.nunique(),
                    "direction_positive": bool(estimate > 0),
                    "paired_draw_id": f"draw_{draw:02d}_budget_{budget}",
                })
    scale = pd.DataFrame(scale_rows, columns=M7_SCHEMAS["scale_sampling_sensitivity.csv"])
    write_m7_table("scale_sampling_sensitivity.csv", scale)

    zero_rows: list[dict[str, object]] = []
    main_configurations = (
        "CONCH_shared_394.24um", "Virchow_shared_394.24um", "Virchow_native_98.56um",
    )
    positive = truth > 0
    for configuration in main_configurations:
        item = configurations[configuration]
        prediction = np.asarray(item["prediction"])
        presence_frame = pd.DataFrame({
            "group_id": groups, "truth": positive.astype(float),
            "prediction": prediction, "outcome_time": np.nan,
        })
        for metric in ("auroc", "average_precision"):
            estimate, reason = safe_metric(metric, presence_frame.truth, presence_frame.prediction)
            low, high, undefined = cluster_bootstrap_interval(presence_frame, metric)
            zero_rows.append({
                "configuration": configuration, "encoder": item["encoder"],
                "analysis_subset": "tumor_presence_truth_gt_0", "analysis_unit": "tile_clustered_by_subject",
                "metric_name": metric, "estimate": estimate, "ci_low": low, "ci_high": high,
                "n_tiles": len(analysis), "n_subjects": analysis.subject_id.nunique(),
                "zero_fraction": float((~positive).mean()),
                "interpretation": f"presence decomposition only; undefined_bootstrap={undefined}; observed_reason={reason}",
            })
        positive_analysis = analysis.loc[positive].reset_index(drop=True)
        positive_prediction = prediction[positive]
        for unit in ("tile_clustered_by_subject", "subject_mean"):
            frame = m6_analysis_frame(positive_analysis, positive_prediction, unit)
            for metric in ("mae", "r2", "spearman"):
                estimate, reason = safe_metric(metric, frame.truth, frame.prediction)
                low, high, undefined = cluster_bootstrap_interval(frame, metric)
                zero_rows.append({
                    "configuration": configuration, "encoder": item["encoder"],
                    "analysis_subset": "positive_tumor_fraction_only", "analysis_unit": unit,
                    "metric_name": metric, "estimate": estimate, "ci_low": low, "ci_high": high,
                    "n_tiles": len(positive_analysis), "n_subjects": positive_analysis.subject_id.nunique(),
                    "zero_fraction": 0.0,
                    "interpretation": f"sensitivity evaluation of existing OOF; undefined_bootstrap={undefined}; observed_reason={reason}",
                })
    zero = pd.DataFrame(zero_rows, columns=M7_SCHEMAS["zero_inflation_sensitivity.csv"])
    write_m7_table("zero_inflation_sensitivity.csv", zero)

    tile_qc = pd.read_csv(OUT / "tile_qc.csv").set_index("tile_id").loc[analysis.tile_id]
    targets = pd.read_csv(OUT / "quantitative_targets.csv").set_index("tile_id").loc[analysis.tile_id]
    m4 = pd.read_csv(OUT / "paired_tile_manifest.csv").set_index("tile_id").loc[analysis.tile_id]
    qc_data = tile_qc[["brightness_mean", "grayscale_sd", "laplacian_variance", "saturation_mean"]].reset_index(drop=True)
    qc_data["valid_biological_fraction"] = targets.valid_biological_fraction.to_numpy(float)
    qc_data["artifact_fraction"] = targets.artifact_fraction.to_numpy(float)
    qc_data["native_mpp_x"] = m4.native_mpp_x.to_numpy(float)
    qc_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        prediction = base_predictions[encoder]
        absolute_error = np.abs(truth - prediction)
        for variable in M7_QC_VARIABLES:
            values = qc_data[variable].to_numpy(float)
            estimate, reason = safe_metric("spearman", values, absolute_error)
            alternate_mpp_underpowered = (
                variable == "native_mpp_x"
                and int(np.unique(groups[values == np.min(values)]).size) < 5
            )
            large = bool(np.isfinite(estimate) and abs(estimate) >= 0.5 and not alternate_mpp_underpowered)
            status = "not_assessable_two_subject_alternate_mpp_group" if alternate_mpp_underpowered else ("pass" if not reason else reason)
            qc_rows.append({
                "encoder": encoder, "qc_variable": variable,
                "analysis_type": "absolute_error_association", "stratum": "all",
                "threshold_low": np.nan, "threshold_high": np.nan,
                "n_tiles": len(analysis), "n_subjects": analysis.subject_id.nunique(),
                "metric_name": "spearman", "estimate": estimate,
                "direction_positive": bool(estimate > 0) if np.isfinite(estimate) else False,
                "qc_dominance_flag": large, "assessment_status": status,
            })
            q25, q75 = float(np.quantile(values, 0.25)), float(np.quantile(values, 0.75))
            for stratum, selection, low_threshold, high_threshold in (
                ("Q1", values <= q25, float(np.min(values)), q25),
                ("Q4", values >= q75, q75, float(np.max(values))),
            ):
                estimate, reason = safe_metric("spearman", truth[selection], prediction[selection])
                n_subjects = int(np.unique(groups[selection]).size)
                dominance = bool(
                    np.isfinite(estimate) and estimate <= 0 and n_subjects >= 10
                    and not alternate_mpp_underpowered
                )
                qc_rows.append({
                    "encoder": encoder, "qc_variable": variable,
                    "analysis_type": "OOF_performance_stratum", "stratum": stratum,
                    "threshold_low": low_threshold, "threshold_high": high_threshold,
                    "n_tiles": int(selection.sum()), "n_subjects": n_subjects,
                    "metric_name": "spearman", "estimate": estimate,
                    "direction_positive": bool(np.isfinite(estimate) and estimate > 0),
                    "qc_dominance_flag": dominance, "assessment_status": status if alternate_mpp_underpowered else ("pass" if not reason else reason),
                })
    qc_sensitivity = pd.DataFrame(qc_rows, columns=M7_SCHEMAS["qc_sensitivity.csv"])
    write_m7_table("qc_sensitivity.csv", qc_sensitivity)

    conch_error = truth - base_predictions["CONCH"]
    virchow_error = truth - base_predictions["Virchow"]
    error_delta = np.abs(conch_error) - np.abs(virchow_error)
    q10, q90 = float(np.quantile(error_delta, 0.10)), float(np.quantile(error_delta, 0.90))
    classes = np.where(
        error_delta >= q90, "conch_worse_top_decile",
        np.where(error_delta <= q10, "virchow_worse_bottom_decile", "concordant_middle_80pct"),
    )
    discordance = pd.DataFrame({
        "tile_id": analysis.tile_id, "subject_id": analysis.subject_id,
        "image_id": analysis.image_id, "fold": analysis.fold, "truth": truth,
        "conch_prediction": base_predictions["CONCH"],
        "virchow_prediction": base_predictions["Virchow"],
        "conch_residual": conch_error, "virchow_residual": virchow_error,
        "conch_absolute_error": np.abs(conch_error),
        "virchow_absolute_error": np.abs(virchow_error),
        "absolute_error_delta_conch_minus_virchow": error_delta,
        "prediction_difference": base_predictions["CONCH"] - base_predictions["Virchow"],
        "discordance_class": classes,
        "brightness_mean": qc_data.brightness_mean,
        "grayscale_sd": qc_data.grayscale_sd,
        "laplacian_variance": qc_data.laplacian_variance,
        "saturation_mean": qc_data.saturation_mean,
        "valid_biological_fraction": qc_data.valid_biological_fraction,
        "artifact_fraction": qc_data.artifact_fraction,
        "native_mpp_x": qc_data.native_mpp_x,
    }, columns=M7_SCHEMAS["discordance_manifest.csv"])
    write_m7_table("discordance_manifest.csv", discordance)
    association_rows: list[dict[str, object]] = []
    absolute_disagreement = np.abs(discordance.prediction_difference.to_numpy(float))
    for variable in M7_QC_VARIABLES:
        estimate, reason = safe_metric("spearman", qc_data[variable].to_numpy(float), absolute_disagreement)
        underpowered = (
            variable == "native_mpp_x"
            and int(np.unique(groups[qc_data[variable].to_numpy(float) == qc_data[variable].min()]).size) < 5
        )
        large = bool(np.isfinite(estimate) and abs(estimate) >= 0.5 and not underpowered)
        association_rows.append({
            "qc_variable": variable, "metric_name": "spearman_with_absolute_prediction_disagreement",
            "estimate": estimate, "n_tiles": len(analysis),
            "n_subjects": analysis.subject_id.nunique(),
            "association_direction": "positive" if estimate > 0 else "negative",
            "large_association_flag": large,
            "assessment_status": "not_assessable_two_subject_alternate_mpp_group" if underpowered else ("pass" if not reason else reason),
        })
    associations = pd.DataFrame(association_rows, columns=M7_SCHEMAS["discordance_qc_associations.csv"])
    write_m7_table("discordance_qc_associations.csv", associations)

    m6_summary = pd.read_csv(OUT / "concept_summary.csv")
    null_rows = m6_summary[m6_summary.metric_name.eq("spearman") & m6_summary.permutation_p95.notna()]
    null_controls_pass = bool((null_rows.estimate > null_rows.permutation_p95).all())
    paired_premise = bool(native_qc.technical_status.eq("pass").all() and native_manifest.tile_id.equals(analysis.tile_id))
    sampling_check = scale[
        scale.sensitivity_type.eq("paired_tile_budget")
        & pd.to_numeric(scale.tile_budget, errors="coerce").ge(8)
        & scale.configuration.isin(main_configurations)
    ]
    sampling_direction_retained = bool(sampling_check.direction_positive.astype(bool).all())
    positive_subject = zero[
        zero.analysis_subset.eq("positive_tumor_fraction_only")
        & zero.analysis_unit.eq("subject_mean") & zero.metric_name.eq("spearman")
    ]
    positive_only_direction_retained = bool((positive_subject.estimate > 0).all())
    native_subject_spearman = scale[
        scale.configuration.eq("Virchow_native_98.56um")
        & scale.sensitivity_type.eq("full_configuration")
        & scale.analysis_unit.eq("subject_mean") & scale.metric_name.eq("spearman")
    ].estimate.iloc[0]
    dominance_counts = (
        qc_sensitivity[qc_sensitivity.qc_dominance_flag.astype(bool)]
        .groupby("encoder").qc_variable.nunique().to_dict()
    )
    red = bool(
        not paired_premise or not null_controls_pass
        or any(dominance_counts.get(encoder, 0) >= 2 for encoder in ("CONCH", "Virchow"))
    )
    if red:
        decision, status = "Red", "red_robustness_or_paired_premise_failure"
    else:
        decision, status = "Amber", "amber_defined_shared_fov_descriptive_scope"

    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    gate = gates.gate_id.eq("P0-G7")
    gates.loc[gate, "status"] = status
    gates.loc[gate, "draft_decision"] = decision
    gates.loc[gate, "entry_condition_met"] = not red
    gates.loc[gate, "direct_evidence"] = "representation_similarity.csv; scale_sampling_sensitivity.csv; zero_inflation_sensitivity.csv; qc_sensitivity.csv; discordance_manifest.csv; M7_ROBUSTNESS_REPORT.md"
    gates.loc[gate, "unresolved_risk"] = "stain metadata absent; alternate MPP group has two subjects; single zero-inflated descriptive target"
    gates.loc[gate, "next_unlocked"] = "P0-M8 integrated Conditional-Go adjudication for shared 394.24um descriptive tumor combinations" if not red else "none"
    gates.loc[gate, "still_prohibited"] = "Green scanner/stain robustness; encoder superiority; confirmatory, clinical or PNI claims"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])

    claims = pd.read_csv(OUT / "claim_evidence_matrix.csv")
    if not claims.claim_id.eq("C10").any():
        claims = pd.concat([claims, governance_tables()[0].query("claim_id == 'C10'")], ignore_index=True)
    claim = claims.claim_id.eq("C10")
    claims.loc[claim, "status"] = "supported_amber_defined_shared_fov_scope" if not red else "not_supported_red"
    claims.loc[claim, "current_evidence"] = (
        f"sampling_direction_retained={sampling_direction_retained}; positive_only_direction_retained={positive_only_direction_retained}; "
        f"native_virchow_subject_rho={native_subject_spearman:.4f}; null_controls_pass={null_controls_pass}; qc_dominance={dominance_counts}"
    )
    claims.loc[claim, "allowed_wording"] = "shared-394.24um descriptive tumor recoverability is robust within tested sensitivity limits" if not red else "no robustness claim"
    write_table("claim_evidence_matrix.csv", claims[TABLE_SCHEMAS["claim_evidence_matrix.csv"]])

    deviations = pd.read_csv(OUT / "deviation_log.csv")
    if not deviations.deviation_id.eq("D013").any():
        deviations = pd.concat([deviations, governance_tables()[1].query("deviation_id == 'D013'")], ignore_index=True)
    write_table("deviation_log.csv", deviations[TABLE_SCHEMAS["deviation_log.csv"]])

    unlock = pd.read_csv(OUT / "main_study_unlock_matrix.csv")
    fm5 = unlock.main_stage.eq("FM5")
    unlock.loc[fm5, "current_status"] = "amber_shared_fov_descriptive_scope" if not red else "stopped_at_P0_G7"
    unlock.loc[fm5, "currently_allowed"] = "P0-M8 integration for CONCH/Virchow descriptive tumor at shared 394.24um" if not red else "robustness redesign only"
    unlock.loc[fm5, "currently_prohibited"] = "encoder superiority; scanner/stain robustness; confirmatory, clinical or PNI claim"
    unlock.loc[fm5, "evidence"] = "M7_ROBUSTNESS_REPORT.md; p0_gate_matrix.csv"
    write_table("main_study_unlock_matrix.csv", unlock[TABLE_SCHEMAS["main_study_unlock_matrix.csv"]])

    shared_sampling = scale[
        scale.sensitivity_type.eq("paired_tile_budget")
        & scale.configuration.isin(("CONCH_shared_394.24um", "Virchow_shared_394.24um"))
    ].groupby(["configuration", "tile_budget"]).estimate.agg(["min", "median", "max"]).reset_index()
    report = [
        "# P0-M7 robustness and discordance report", "",
        f"- Protocol: `{PROTOCOL_ID}`", f"- P0-G7 decision: **{decision}** (`{status}`)",
        "- Scope carried forward: CONCH/Virchow–descriptive tumor–shared 394.24µm", "",
        "## Prespecified checks", "",
        f"- Paired/hash premise intact: {paired_premise}",
        f"- M6 label/coordinate null controls passed: {null_controls_pass}",
        f"- Sampling direction retained at budgets >=8: {sampling_direction_retained}",
        f"- Positive-only subject direction retained: {positive_only_direction_retained}",
        f"- Virchow native-98.56µm input / shared-target subject Spearman: {native_subject_spearman:.4f}",
        f"- QC dominance counts: {json.dumps(dominance_counts, sort_keys=True)}", "",
        "## Shared-draw sampling ranges", "",
    ]
    for row in shared_sampling.itertuples(index=False):
        report.append(
            f"- {row.configuration}, budget={row.tile_budget}: rho min/median/max="
            f"{row.min:.4f}/{row.median:.4f}/{row.max:.4f}"
        )
    report.extend([
        "", "## Interpretation boundary", "",
        "Amber is mandatory because stain batch metadata are absent and the alternate-MPP acquisition group "
        "contains only two subjects. Native Virchow uses a 98.56µm input to predict the locked shared-window "
        "target, so it is input-context sensitivity, not a native-window target validation. CKA/RSA and residual "
        "discordance are descriptive. No result authorizes encoder superiority, confirmatory biomarkers, clinical "
        "validation, whole-slide diagnosis, or PNI performance claims.",
    ])
    (OUT / "M7_ROBUSTNESS_REPORT.md").write_text("\n".join(report) + "\n")

    config = json.loads((OUT / "run_config.json").read_text())
    config["stage_executed"] = "P0-M0-M7 robustness and discordance sensitivity"
    config["stage_not_executed"] = "P0-M8 integrated decision and P0-M9 handoff"
    config["m7"] = {
        "started_at_utc": started.isoformat(), "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "native_virchow_fov_um": M7_NATIVE_FOV_UM,
        "sampling_budgets": list(M7_SAMPLING_BUDGETS), "sampling_draws": M7_N_SAMPLING_DRAWS,
        "zero_threshold": 0.0, "qc_large_association_threshold_abs_rho": 0.5,
        "native_subject_spearman": float(native_subject_spearman),
        "sampling_direction_retained": sampling_direction_retained,
        "positive_only_direction_retained": positive_only_direction_retained,
        "null_controls_pass": null_controls_pass, "qc_dominance_counts": dominance_counts,
        "p0_g7_status": status,
        "amber_cap_reason": "stain metadata absent; alternate MPP group has two subjects",
    }
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"run_config.json", "PROTOCOL.md", "run_preexperiment.py"}
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "P0-G7": decision, "status": status,
        "native_subject_spearman": native_subject_spearman,
        "sampling_direction_retained": sampling_direction_retained,
        "positive_only_direction_retained": positive_only_direction_retained,
        "qc_dominance_counts": dominance_counts,
    }, indent=2), flush=True)


def run_m8() -> None:
    """Integrate saved G0-G7 evidence into a non-self-approving G8 draft."""
    started = datetime.now(timezone.utc)
    required_files = [
        "source_inventory.csv", "common_sample_manifest.csv", "membership_mismatch.csv",
        "truth_mismatch.csv", "existing_common_sample_results.csv", "concept_summary.csv",
        "concept_paired_deltas.csv", "paired_embedding_manifest.csv",
        "embedding_technical_qc.csv", "representation_similarity.csv",
        "scale_sampling_sensitivity.csv", "zero_inflation_sensitivity.csv",
        "qc_sensitivity.csv", "M7_ROBUSTNESS_REPORT.md", "p0_gate_matrix.csv",
        "main_study_unlock_matrix.csv",
    ]
    missing = [name for name in required_files if not (OUT / name).exists()]
    if missing:
        raise FileNotFoundError("P0-M8 evidence is incomplete: " + "; ".join(missing))
    clinician_source = ROOT / "resources/data/precise_pni_candidate_triage/pathologist_reviews/candidate_review/precise_pni_review (1).csv"
    if sha256_file(clinician_source) != EXPECTED_CLINICIAN_SHA256:
        raise RuntimeError("immutable PRECISE clinician source hash mismatch; stop")

    gates = pd.read_csv(OUT / "p0_gate_matrix.csv", keep_default_na=False)
    gate_status = gates.set_index("gate_id").status.astype(str).to_dict()
    draft_decision = m8_draft_decision(gate_status)
    if draft_decision != "Conditional Go":
        raise RuntimeError(f"current locked M8 evidence does not support the expected Conditional Go draft: {draft_decision}")

    effects = {
        "P0-G0": "locked protocol and decision rules retained",
        "P0-G1": "tumor fraction descriptive only; stroma exploratory; nuclei/lumen deferred",
        "P0-G2": "verified-linkage cohorts only; PANDA patient inference prohibited",
        "P0-G3": "saved source controls qualify the frozen encoders, without superiority inference",
        "P0-G4": "1,218 same-boundary tumor tiles from 25 subjects are the allowed universe",
        "P0-G5": "paired frozen embeddings are technically usable for the defined universe",
        "P0-G6": "both shared-FOV tumor combinations pass the conditional above-chance rule",
        "P0-G7": "Amber limits carry-forward to shared-FOV descriptive use",
    }
    integrated_rows = []
    for row in gates[gates.gate_id.isin(effects)].sort_values("gate_id").itertuples(index=False):
        integrated_rows.append({
            "gate_id": row.gate_id, "milestone": row.milestone, "status": row.status,
            "decision": row.draft_decision,
            "entry_condition_met": str(row.entry_condition_met).lower() == "true",
            "evidence": row.direct_evidence, "unresolved_risk": row.unresolved_risk,
            "m8_effect": effects[row.gate_id],
        })
    integrated = pd.DataFrame(integrated_rows, columns=M8_SCHEMAS["integrated_gate_summary.csv"])
    write_m8_table("integrated_gate_summary.csv", integrated)

    common = pd.read_csv(OUT / "common_sample_manifest.csv", keep_default_na=False)
    membership = pd.read_csv(OUT / "membership_mismatch.csv", keep_default_na=False)
    truth_mismatch = pd.read_csv(OUT / "truth_mismatch.csv", keep_default_na=False)
    paired = pd.read_csv(OUT / "paired_embedding_manifest.csv", keep_default_na=False)
    technical = pd.read_csv(OUT / "embedding_technical_qc.csv", keep_default_na=False)
    concept = pd.read_csv(OUT / "concept_summary.csv")
    deltas = pd.read_csv(OUT / "concept_paired_deltas.csv")
    source_controls = pd.read_csv(OUT / "existing_common_sample_results.csv")
    representation = pd.read_csv(OUT / "representation_similarity.csv")
    scale = pd.read_csv(OUT / "scale_sampling_sensitivity.csv")
    zero = pd.read_csv(OUT / "zero_inflation_sensitivity.csv")
    qc = pd.read_csv(OUT / "qc_sensitivity.csv")

    panda_common = int(((common.cohort_id == "PANDA") & (common.endpoint_id == "isup_grade")).sum())
    mismatch_counts = membership.membership_status.value_counts().to_dict()
    pairing_exact = bool(
        len(paired) == 1218 and paired.tile_id.nunique() == 1218
        and paired.same_boundary_for_both_models.astype(bool).all()
    )
    pairing_exact = pairing_exact and bool(
        technical.technical_status.eq("pass").all()
        and technical.paired_tile_ids_match.astype(bool).all()
        and technical.crop_hashes_match.astype(bool).all()
    )
    subject_results = concept[
        concept.analysis_unit.eq("subject_mean") & concept.metric_name.eq("spearman")
    ].set_index("encoder")
    subject_delta = deltas[
        deltas.analysis_unit.eq("subject_mean") & deltas.metric_name.eq("spearman")
    ].iloc[0]
    tile_delta = deltas[
        deltas.analysis_unit.eq("tile_clustered_by_subject") & deltas.metric_name.eq("spearman")
    ].iloc[0]
    shared_representation = representation[
        representation.representation_a.eq("CONCH_shared_394.24um")
        & representation.representation_b.eq("Virchow_shared_394.24um")
        & representation.metric_name.eq("centered_linear_CKA")
    ]
    cka_subject = shared_representation[
        shared_representation.analysis_unit.eq("subject_mean")
    ].estimate.iloc[0]
    cka_tile = shared_representation[
        shared_representation.analysis_unit.eq("tile")
    ].estimate.iloc[0]
    positive_subject = zero[
        zero.analysis_subset.eq("positive_tumor_fraction_only")
        & zero.analysis_unit.eq("subject_mean") & zero.metric_name.eq("spearman")
    ].set_index("configuration")
    full_scale = scale[
        scale.sensitivity_type.eq("full_configuration") & scale.metric_name.eq("r2")
        & scale.analysis_unit.eq("tile_clustered_by_subject")
    ].set_index("configuration")
    sampling_min = scale[
        scale.sensitivity_type.eq("paired_tile_budget")
        & pd.to_numeric(scale.tile_budget, errors="coerce").ge(8)
        & scale.configuration.isin(("CONCH_shared_394.24um", "Virchow_shared_394.24um"))
    ].groupby("configuration").estimate.min().to_dict()
    dominance_count = int(qc.qc_dominance_flag.astype(bool).sum())

    gate_controls = source_controls[source_controls.gate_exceedance.astype(str).eq("True")]
    passed_control_pairs = sorted(set(zip(gate_controls.endpoint_id, gate_controls.encoder)))
    question_rows = [
        {
            "question_id": "P0-Q1",
            "question": "공통 표본과 정답이 두 모델에서 정확히 일치하는가?",
            "minimum_answer_form": "membership·truth mismatch 감사표",
            "integrated_answer": (
                f"검증된 common universe의 source truth mismatch는 {len(truth_mismatch)}건이다. "
                f"PANDA는 공통 image {panda_common}개이나 CONCH-only {mismatch_counts.get('conch_only', 0)}, "
                f"Virchow-only {mismatch_counts.get('virchow_only', 0)}, neither {mismatch_counts.get('neither_model', 0)}이고 "
                "subject linkage가 없다. PRECISE 분석 universe는 1,218 tile이며 모델 간 tile ID·boundary·crop pairing이 "
                f"{'정확히 일치한다' if pairing_exact else '일치하지 않는다'}."
            ),
            "status": "pass_with_PANDA_linkage_limit",
            "evidence": "common_sample_manifest.csv; membership_mismatch.csv; truth_mismatch.csv; paired_embedding_manifest.csv; embedding_technical_qc.csv",
            "claim_limit": "PANDA patient-level 또는 paired-coordinate 추론 금지",
        },
        {
            "question_id": "P0-Q2",
            "question": "독립 정량개념이 각 모델 표현에서 chance보다 잘 복원되는가?",
            "minimum_answer_form": "OOF 효과량·grouped permutation",
            "integrated_answer": (
                f"descriptive tumor fraction subject-mean Spearman은 CONCH {subject_results.loc['CONCH', 'estimate']:.4f} "
                f"(95% CI {subject_results.loc['CONCH', 'ci_low']:.4f}–{subject_results.loc['CONCH', 'ci_high']:.4f}, "
                f"null p95 {subject_results.loc['CONCH', 'permutation_p95']:.4f}, q={subject_results.loc['CONCH', 'empirical_q']:.4g}), "
                f"Virchow {subject_results.loc['Virchow', 'estimate']:.4f} "
                f"(95% CI {subject_results.loc['Virchow', 'ci_low']:.4f}–{subject_results.loc['Virchow', 'ci_high']:.4f}, "
                f"null p95 {subject_results.loc['Virchow', 'permutation_p95']:.4f}, q={subject_results.loc['Virchow', 'empirical_q']:.4g})로 둘 다 chance 기준을 넘었다."
            ),
            "status": "conditional_pass_one_descriptive_target",
            "evidence": "concept_summary.csv; concept_permutation_null.csv; concept_bootstrap_replicates.csv",
            "claim_limit": "독립 confirmatory target이 아니라 descriptive feasibility만 허용",
        },
        {
            "question_id": "P0-Q3",
            "question": "어느 개념이 두 모델 공통이고 어느 개념이 모델 특이적인가?",
            "minimum_answer_form": "paired delta·불확실성·방향성",
            "integrated_answer": (
                f"tumor fraction은 두 모델의 공통 recoverable signal이다. Subject Spearman Δ(CONCH−Virchow)="
                f"{subject_delta.paired_delta_conch_minus_virchow:.4f} (95% CI {subject_delta.ci_low:.4f}–{subject_delta.ci_high:.4f}); "
                f"tile Δ={tile_delta.paired_delta_conch_minus_virchow:.4f} (95% CI {tile_delta.ci_low:.4f}–{tile_delta.ci_high:.4f}). "
                f"shared representation CKA는 tile {cka_tile:.4f}, subject {cka_subject:.4f}이다. 하나뿐인 target으로 모델 특이 개념이나 보편적 우월성을 확정할 수 없다."
            ),
            "status": "common_signal_no_model_specific_claim",
            "evidence": "concept_paired_deltas.csv; representation_similarity.csv; discordance_manifest.csv",
            "claim_limit": "tile 단일 metric 차이를 encoder superiority로 일반화 금지",
        },
        {
            "question_id": "P0-Q4",
            "question": "결과가 FOV, scale, tile sampling과 probe에 얼마나 민감한가?",
            "minimum_answer_form": "사전 정의 sensitivity matrix",
            "integrated_answer": (
                f"budget≥8 paired sampling의 최저 subject rho는 CONCH {sampling_min['CONCH_shared_394.24um']:.3f}, "
                f"Virchow {sampling_min['Virchow_shared_394.24um']:.3f}로 방향을 유지했다. Positive-only subject rho는 "
                f"CONCH {positive_subject.loc['CONCH_shared_394.24um', 'estimate']:.4f}, shared Virchow "
                f"{positive_subject.loc['Virchow_shared_394.24um', 'estimate']:.4f}, native-input Virchow "
                f"{positive_subject.loc['Virchow_native_98.56um', 'estimate']:.4f}다. Virchow tile R²는 shared "
                f"{full_scale.loc['Virchow_shared_394.24um', 'estimate']:.4f}에서 native-input "
                f"{full_scale.loc['Virchow_native_98.56um', 'estimate']:.4f}로 낮아졌다. QC dominance flag는 {dominance_count}건이다."
            ),
            "status": "amber_scale_sensitive_metadata_limited",
            "evidence": "scale_sampling_sensitivity.csv; zero_inflation_sensitivity.csv; qc_sensitivity.csv; M7_ROBUSTNESS_REPORT.md",
            "claim_limit": "scanner/stain robustness와 native-window target validation 주장 금지",
        },
        {
            "question_id": "P0-Q5",
            "question": "기존의 강한·약한 표적 패턴을 공통 표본 재분석이 재현하는가?",
            "minimum_answer_form": "positive/weak control 결과",
            "integrated_answer": (
                "NADT Gleason·tumor/benign과 LEOPARD recurrence는 두 encoder에서 grouped-null을 넘었다. "
                "약한 TCGA 패턴은 혼합적이었다: PTEN은 Virchow만, SPOP은 CONCH만 gate를 넘었고 AR은 둘 다 작지만 양의 Spearman으로 넘었다. "
                f"총 gate-exceeding endpoint–encoder 쌍은 {len(passed_control_pairs)}개다."
            ),
            "status": "pass_strong_controls_weak_patterns_heterogeneous",
            "evidence": "existing_common_sample_results.csv; existing_paired_deltas.csv; positive_control_report.md",
            "claim_limit": "historical native FOV 결과는 same-FOV superiority evidence가 아님",
        },
        {
            "question_id": "P0-Q6",
            "question": "본 연구에서 허용할 model–target–FOV 조합은 무엇인가?",
            "minimum_answer_form": "gate 및 unlock matrix",
            "integrated_answer": (
                "G8 draft가 제안하는 조합은 CONCH–tumor fraction–shared 394.24µm와 "
                "Virchow–tumor fraction–shared 394.24µm의 descriptive Conditional-Go 후보뿐이다. "
                "Virchow 98.56µm는 input-context sensitivity 전용이고 stroma는 exploratory, nuclei와 gland/lumen은 deferred다. "
                "연구책임자 G8 승인과 G9 전에는 실제 main-study 실행이 잠겨 있다."
            ),
            "status": "draft_conditional_go_pending_research_lead_approval",
            "evidence": "model_target_fov_decision.csv; p0_gate_matrix.csv; main_study_unlock_matrix.csv",
            "claim_limit": "confirmatory·clinical·PNI·encoder-superiority 주장 금지",
        },
    ]
    questions = pd.DataFrame(question_rows, columns=M8_SCHEMAS["p0_question_answer_matrix.csv"])
    write_m8_table("p0_question_answer_matrix.csv", questions)

    combination_rows = [
        ("CMB-01", "CONCH", "tumor_fraction", 394.24, 394.24, "descriptive_only",
         "G5 Pass; G6 Conditional Pass; G7 Amber", "Conditional Go candidate pending G8 approval",
         "protocol/code/schema/smoke preparation", "main-study execution before G8 approval and G9; confirmatory/clinical/PNI claims",
         "research-lead G8 approval and clean G9 rerun", "concept_summary.csv; M7_ROBUSTNESS_REPORT.md"),
        ("CMB-02", "Virchow", "tumor_fraction", 394.24, 394.24, "descriptive_only",
         "G5 Pass; G6 Conditional Pass; G7 Amber", "Conditional Go candidate pending G8 approval",
         "protocol/code/schema/smoke preparation", "main-study execution before G8 approval and G9; confirmatory/clinical/PNI claims",
         "research-lead G8 approval and clean G9 rerun", "concept_summary.csv; M7_ROBUSTNESS_REPORT.md"),
        ("CMB-03", "Virchow", "tumor_fraction", 98.56, 394.24, "input_context_sensitivity_only",
         "G7 Amber; native input predicts shared-window target", "Sensitivity only; not a primary combination",
         "locked sensitivity interpretation", "native-window target or scanner robustness claim; main-study primary use",
         "independent native-window target plus adequate acquisition groups", "scale_sampling_sensitivity.csv; zero_inflation_sensitivity.csv"),
        ("CMB-04", "CONCH and Virchow", "stroma_fraction", 394.24, 394.24, "exploratory_algorithm_assisted",
         "not probed; G1 limited", "Locked for inferential use",
         "measurement-method development only", "main-study concept inference or confirmatory claim",
         "validated fixed measurement and approval", "metric_eligibility.tsv; measurement_provenance.csv"),
        ("CMB-05", "CONCH and Virchow", "nuclear_density_mm2", np.nan, np.nan, "deferred",
         "no validated locked measurement", "Locked",
         "detector validation planning", "embedding-target inference",
         "fixed detector and independent validation evidence", "metric_eligibility.tsv"),
        ("CMB-06", "CONCH and Virchow", "gland_lumen_fraction", np.nan, np.nan, "deferred",
         "no validated locked measurement", "Locked",
         "segmentation validation planning", "embedding-target inference",
         "fixed segmentation and expert validation evidence", "metric_eligibility.tsv"),
    ]
    combinations = pd.DataFrame(combination_rows, columns=M8_SCHEMAS["model_target_fov_decision.csv"])
    write_m8_table("model_target_fov_decision.csv", combinations)

    risk_rows = [
        ("M8-R01", "D005", "medium", "tumor/stroma measurement", "quantitative repeatability is not reported",
         "tumor remains descriptive; stroma remains exploratory", "required before confirmatory use, not current preparation",
         "accept with scope cap", "pathology/statistics", "measurement_provenance.csv"),
        ("M8-R02", "D002", "high", "PANDA", "verified subject linkage is absent",
         "patient grouping and leakage cannot be assessed", "required before PANDA patient inference",
         "exclude PANDA patient inference", "data manager", "leakage_audit.csv"),
        ("M8-R03", "D012", "high", "target breadth/zero inflation", "one descriptive target; 62.89% tile truth is zero",
         "strong G6 and complementarity claims are unavailable", "additional independent targets required before confirmatory/complementarity work",
         "accept only descriptive single-target scope", "pathology/statistics", "target_availability.csv; zero_inflation_sensitivity.csv"),
        ("M8-R04", "D013", "medium", "scanner/stain robustness", "stain metadata absent; alternate-MPP group has two subjects",
         "G7 capped at Amber", "required before scanner/stain robustness claim",
         "accept Amber scope cap", "ML/data/statistics", "qc_sensitivity.csv; M7_ROBUSTNESS_REPORT.md"),
        ("M8-R05", "none", "high", "governance", "research-lead G8 final approval is not recorded",
         "Conditional Go remains a draft; main-study execution stays locked", "required before any G8 unlock",
         "pending research-lead review", "research lead", "p0_gate_matrix.csv; P0_REPORT.md"),
        ("M8-R06", "AGENTS.md", "high", "claim boundary", "evidence concerns descriptive tumor recoverability, not PNI diagnosis",
         "clinical, whole-slide and PNI performance inference would be invalid", "separate approved study required",
         "permanent scope boundary for this P0", "research lead", "claim_evidence_matrix.csv; PROTOCOL.md"),
    ]
    risks = pd.DataFrame(risk_rows, columns=M8_SCHEMAS["unresolved_risk_register.csv"])
    write_m8_table("unresolved_risk_register.csv", risks)

    gate = gates.gate_id.eq("P0-G8")
    gates.loc[gate, "status"] = "draft_conditional_go_pending_research_lead_approval"
    gates.loc[gate, "draft_decision"] = draft_decision
    gates.loc[gate, "entry_condition_met"] = False
    gates.loc[gate, "direct_evidence"] = "integrated_gate_summary.csv; p0_question_answer_matrix.csv; model_target_fov_decision.csv; unresolved_risk_register.csv; P0_REPORT.md"
    gates.loc[gate, "unresolved_risk"] = "research-lead final approval not recorded; specialist reviews are non-blocking advisory"
    gates.loc[gate, "next_unlocked"] = "P0-G8 human adjudication, then P0-M9 clean rerun if approved"
    gates.loc[gate, "still_prohibited"] = "main-study execution; confirmatory, clinical, whole-slide PNI or encoder-superiority claims"
    gates.loc[gate, "approver"] = "pending: research lead"
    gates.loc[gate, "approval_timestamp"] = ""
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])

    claims = pd.read_csv(OUT / "claim_evidence_matrix.csv", keep_default_na=False)
    claim = claims.claim_id.eq("C01")
    claims.loc[claim, "status"] = "draft_supported_pending_G8_research_lead_approval"
    claims.loc[claim, "current_evidence"] = "G0-G7 integrated; two shared-394.24um descriptive tumor combinations proposed; G8 approvals pending"
    claims.loc[claim, "allowed_wording"] = "draft Conditional Go for defined descriptive model-target-FOV combinations, pending G8 approval and G9"
    claims.loc[claim, "prohibited_wording"] = "approved Go; clinical validation; whole-slide PNI diagnosis; encoder superiority"
    write_table("claim_evidence_matrix.csv", claims[TABLE_SCHEMAS["claim_evidence_matrix.csv"]])

    unlock = pd.read_csv(OUT / "main_study_unlock_matrix.csv", keep_default_na=False)
    updates = {
        "FM0": ("conditional_go_draft_pending_G8", "G8 packet review and protocol revision preparation", "final Go or main execution before recorded approval"),
        "FM1": ("descriptive_tumor_catalog_ready_pending_G8_G9", "descriptive tumor catalog/schema preparation", "confirmatory target designation"),
        "FM2": ("paired_manifest_ready_pending_G8_G9", "manifest/schema validation and smoke preparation", "new main-study manifest freeze before G8/G9"),
        "FM3": ("conditional_go_candidate_shared_fov_descriptive_pending_G8_G9", "CONCH/Virchow shared-394.24um tumor code/schema/smoke preparation", "large main-study extraction before G8 approval and G9"),
        "FM4": ("conditional_go_candidate_shared_fov_descriptive_pending_G8_G9", "analysis code/schema/smoke preparation for the two candidate combinations", "main concept benchmark; confirmatory or clinical inference"),
        "FM5": ("amber_scope_candidate_pending_G8_G9", "paired comparison code/schema preparation within shared-FOV descriptive scope", "encoder superiority; scanner/stain robustness; main execution"),
        "FM6": ("locked_insufficient_independent_targets", "none", "complementarity claim or execution"),
        "FM10": ("handoff_preparation_only_pending_G8_G9", "claim audit and handoff checklist preparation", "final result packaging as approved Go"),
    }
    for stage, (status, allowed, prohibited) in updates.items():
        mask = unlock.main_stage.eq(stage)
        unlock.loc[mask, "current_status"] = status
        unlock.loc[mask, "currently_allowed"] = allowed
        unlock.loc[mask, "currently_prohibited"] = prohibited
        unlock.loc[mask, "evidence"] = "P0_REPORT.md; p0_gate_matrix.csv; model_target_fov_decision.csv"
    fm1 = unlock.main_stage.eq("FM1")
    unlock.loc[fm1, "additional_requirement"] = "medical T1-T4 and separate analysis registry classified with parent linkage"
    write_table("main_study_unlock_matrix.csv", unlock[TABLE_SCHEMAS["main_study_unlock_matrix.csv"]])

    saved_questions = pd.read_csv(OUT / "p0_question_answer_matrix.csv", keep_default_na=False)
    saved_combinations = pd.read_csv(OUT / "model_target_fov_decision.csv", keep_default_na=False)
    saved_risks = pd.read_csv(OUT / "unresolved_risk_register.csv", keep_default_na=False)
    medical_catalog = pd.concat([
        pd.read_csv(path, sep="\t", keep_default_na=False)
        for path in sorted((
            ROOT / "infrastructure/packages/vlm_pathology_metrics/src/vlm_pathology_metrics/data/medical"
        ).glob("tier*.tsv"))
    ], ignore_index=True)
    legacy_measures = pd.read_csv(
        ROOT / "infrastructure/packages/vlm_pathology_metrics/src/vlm_pathology_metrics/data/legacy/metric_catalog_113.tsv",
        sep="\t", keep_default_na=False,
    )
    tier_counts = medical_catalog.tier.value_counts().sort_index().to_dict()
    analysis_measure_count = int((~legacy_measures.metric_id.isin(medical_catalog.metric_id)).sum())
    report = [
        "# P0-M8 통합 판정 보고서", "",
        f"- Protocol: `{PROTOCOL_ID}`",
        f"- 기계적 draft 판정: **{draft_decision}**",
        "- G8 상태: **연구책임자 최종 승인 대기** (전문 검토는 필요 시 비차단 자문)",
        "- 가설 변경: 없음. 사전 고정된 descriptive tumor fraction과 shared 394.24µm 범위만 통합했다.",
        "- 의미: 제한된 방법론적 feasibility 제안이며 임상 Go가 아니다.", "",
        "## 정량지표 분모의 해석", "",
        "기존 113개 목록은 의료 측정치와 모델평가·통계·QC가 섞인 legacy measure registry다. "
        "현재 tiered 의료·파생 카탈로그는 "
        f"T1 {tier_counts.get('T1', 0)}, T2 {tier_counts.get('T2', 0)}, "
        f"T3 {tier_counts.get('T3', 0)}, T4 {tier_counts.get('T4', 0)}개이며, "
        f"별도 analysis measure는 {analysis_measure_count}개다.",
        "이번 P0에서 완전한 paired OOF/permutation을 수행한 것은 T2 tumor fraction 하나이며, "
        "이를 전체 의료 카탈로그에서 하나만 사용 가능하다는 뜻으로 해석하지 않는다.", "",
        "## P0 질문별 답", "",
    ]
    for row in saved_questions.itertuples(index=False):
        report.extend([f"### {row.question_id}", "", row.integrated_answer, "", f"상태: `{row.status}`", f"한계: {row.claim_limit}", ""])
    report.extend(["## Model–target–FOV 판정", "", "| 조합 | 역할 | M8 권고 | 현재 허용 | 현재 금지 |", "|---|---|---|---|---|"])
    for row in saved_combinations.itertuples(index=False):
        report.append(f"| {row.model}–{row.target}–input {row.input_fov_um or 'NA'}µm | {row.target_role} | {row.m8_recommendation} | {row.currently_allowed} | {row.currently_prohibited} |")
    report.extend(["", "## 미해결 위험", ""])
    for row in saved_risks.itertuples(index=False):
        report.append(f"- **{row.risk_id} ({row.severity})**: {row.observed} — {row.disposition}")
    report.extend([
        "", "## 결론과 unlock", "",
        "두 허용 후보는 CONCH–tumor fraction–394.24µm와 Virchow–tumor fraction–394.24µm이며 모두 descriptive only다.",
        "현재는 protocol/code/schema/smoke 준비만 가능하다. 실제 main-study 실행은 연구책임자 G8 승인과 P0-M9 clean rerun 전까지 잠겨 있다.", "",
        "## 승인 기록", "",
        "- Research lead final approval: PENDING",
        "- Pathology/statistics/ML-data review: OPTIONAL ADVISORY", "",
        "승인자는 `p0_gate_matrix.csv`의 G8 approver와 timestamp를 명시적으로 기록해야 한다. 이 보고서는 서명을 대신하지 않는다.", "",
        "## 주장 경계", "",
        "현재 결과는 candidate triage를 포함한 별도 PRECISE PNI 연구의 whole-slide 진단 성능이나 임상 유효성을 검증하지 않는다. "
        "Encoder superiority, scanner/stain robustness, confirmatory biomarker, PNI sensitivity 또는 population prevalence를 주장할 수 없다.",
    ])
    (OUT / "P0_REPORT.md").write_text("\n".join(report) + "\n")

    config = json.loads((OUT / "run_config.json").read_text())
    config["stage_executed"] = "P0-M0-M8 integrated decision draft"
    config["stage_not_executed"] = "P0-G8 human approval and P0-M9 clean-rerun handoff"
    config["m8"] = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "draft_decision": draft_decision,
        "gate_status": "draft_conditional_go_pending_research_lead_approval",
        "hypothesis_changed": False,
        "candidate_combinations": ["CONCH-tumor_fraction-394.24um", "Virchow-tumor_fraction-394.24um"],
        "candidate_role": "descriptive_only",
        "human_approvals_recorded": False,
        "main_study_execution_unlocked": False,
        "metric_taxonomy": {
            "tier_counts": tier_counts,
            "analysis_measure_count": analysis_measure_count,
            "p0_fully_benchmarked_medical_metric": "candidate.tumor_fraction",
        },
    }
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"run_config.json", "PROTOCOL.md", "run_preexperiment.py"}
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "P0-G8_draft": draft_decision,
        "status": "pending_research_lead_approval",
        "candidate_combinations": 2,
        "main_study_execution_unlocked": False,
    }, indent=2), flush=True)


def run_m4() -> None:
    run_pre_g0()
    encoder_pass = restore_saved_m3_gate()
    started = datetime.now(timezone.utc)
    data_root = ROOT / "resources/data/shared/opendataset/PRECISE/extracted/data"
    mask_paths = sorted(data_root.glob("sub-*/ses-*/wsi_h-e/*_mask.ome.tif"))
    if len(mask_paths) != 27:
        raise RuntimeError(f"expected 27 PRECISE H&E masks, found {len(mask_paths)}")
    subjects = sorted({path.parents[2].name for path in mask_paths})
    if len(subjects) != 25:
        raise RuntimeError(f"expected 25 PRECISE subjects, found {len(subjects)}")
    shuffled = np.asarray(subjects, dtype=object)
    np.random.default_rng(SEED).shuffle(shuffled)
    fold_map = {str(subject): int(index % 5) for index, subject in enumerate(shuffled)}

    pni = pd.read_csv(
        ROOT / "resources/artifacts/precise_pni_candidate_triage/morphology_rereview/locked/normalized_morphology_review.csv"
    )
    if len(pni) != 14 or pni.candidate_id.duplicated().any():
        raise RuntimeError("locked PNI exclusion source does not contain 14 unique candidates")
    pni["x1"] = pni.x0 + pni.window_px
    pni["y1"] = pni.y0 + pni.window_px
    focus_audit = {
        row.candidate_id: {
            "candidate_id": row.candidate_id, "subject_id": row.subject_id,
            "image_id": row.image_id, "focus_x0": int(row.x0), "focus_y0": int(row.y0),
            "focus_x1": int(row.x1), "focus_y1": int(row.y1),
            "n_overlapping_inventory_tiles": 0,
            "n_overlapping_eligible_before_exclusion": 0,
            "exclusion_verified": False,
        }
        for row in pni.itertuples(index=False)
    }

    manifest_rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []
    for mask_path in mask_paths:
        he_path = Path(str(mask_path).replace("_mask.ome.tif", ".ome.tif"))
        subject_id, session_id = mask_path.parents[2].name, mask_path.parents[1].name
        image_id = mask_path.name.removesuffix("_h-e_mask.ome.tif")
        fold = fold_map[subject_id]
        with tifffile.TiffFile(he_path) as he_tif, tifffile.TiffFile(mask_path) as mask_tif:
            he_series, mask_series = he_tif.series[0], mask_tif.series[0]
            he_height, he_width = map(int, he_series.levels[0].shape[:2])
            mask_height, mask_width = map(int, mask_series.levels[0].shape[:2])
            shape_match = (he_height, he_width) == (mask_height, mask_width)
            mpp_x, mpp_y = parse_ome_mpp(he_tif.ome_metadata or "")
            if not np.isclose(mpp_x, mpp_y, rtol=0, atol=1e-9):
                raise RuntimeError(f"anisotropic MPP is not permitted: {image_id}")
            crop_px = int(round(394.24 / mpp_x))
            physical_fov = crop_px * mpp_x
            mask_level_index = 3
            he_qc_level_index = 4
            mask_level = mask_series.levels[mask_level_index].asarray()
            he_qc_level = he_series.levels[he_qc_level_index].asarray()
            mask_labels_valid = bool(set(np.unique(mask_level).tolist()) <= set(range(8)))
            level_h, level_w = map(int, mask_level.shape[:2])
            qc_h, qc_w = map(int, he_qc_level.shape[:2])
            image_foci = pni[pni.image_id == image_id]
            for row_index, y0 in enumerate(range(0, he_height - crop_px + 1, crop_px)):
                for column_index, x0 in enumerate(range(0, he_width - crop_px + 1, crop_px)):
                    x1, y1 = x0 + crop_px, y0 + crop_px
                    tile_id = f"{image_id}__r{row_index:04d}_c{column_index:04d}"
                    mx0, mx1 = mapped_boundary(x0, x1, he_width, level_w)
                    my0, my1 = mapped_boundary(y0, y1, he_height, level_h)
                    mask_crop = mask_level[my0:my1, mx0:mx1]
                    counts = np.bincount(mask_crop.reshape(-1), minlength=8) if mask_crop.size else np.zeros(8, dtype=int)
                    n_pixels = int(mask_crop.size)
                    n_valid = int(counts[[1, 2, 4, 5, 6, 7]].sum())
                    n_tumor, n_stroma, n_artifact = int(counts[1]), int(counts[7]), int(counts[3])
                    valid_fraction = n_valid / n_pixels if n_pixels else np.nan
                    artifact_fraction = n_artifact / n_pixels if n_pixels else np.nan
                    tumor_fraction = n_tumor / n_valid if n_valid else np.nan
                    stroma_fraction = n_stroma / n_valid if n_valid else np.nan
                    reasons: list[str] = []
                    if not shape_match:
                        reasons.append("he_mask_level0_shape_mismatch")
                    if not mask_labels_valid:
                        reasons.append("unexpected_mask_label")
                    if not n_valid:
                        reasons.append("zero_valid_biological_denominator")
                    if np.isfinite(valid_fraction) and valid_fraction < 0.50:
                        reasons.append("valid_biological_fraction_below_0.50")
                    if np.isfinite(artifact_fraction) and artifact_fraction > 0.05:
                        reasons.append("artifact_fraction_above_0.05")
                    eligible_before_pni = not reasons
                    overlapping_candidates: list[str] = []
                    for focus in image_foci.itertuples(index=False):
                        overlaps = x0 < focus.x1 and x1 > focus.x0 and y0 < focus.y1 and y1 > focus.y0
                        if overlaps:
                            overlapping_candidates.append(focus.candidate_id)
                            focus_audit[focus.candidate_id]["n_overlapping_inventory_tiles"] += 1
                            if eligible_before_pni:
                                focus_audit[focus.candidate_id]["n_overlapping_eligible_before_exclusion"] += 1
                    if overlapping_candidates:
                        reasons.append("overlaps_locked_pni_focus")

                    qx0, qx1 = mapped_boundary(x0, x1, he_width, qc_w)
                    qy0, qy1 = mapped_boundary(y0, y1, he_height, qc_h)
                    he_crop = he_qc_level[qy0:qy1, qx0:qx1]
                    qc = he_qc_metrics(he_crop)
                    included = not reasons
                    manifest_rows.append({
                        "tile_id": tile_id, "subject_id": subject_id, "session_id": session_id,
                        "image_id": image_id, "fold": fold, "he_path": relative_or_absolute(he_path),
                        "mask_path": relative_or_absolute(mask_path), "level0_x0": x0,
                        "level0_y0": y0, "level0_x1": x1, "level0_y1": y1,
                        "center_x": x0 + crop_px / 2, "center_y": y0 + crop_px / 2,
                        "native_mpp_x": mpp_x, "native_mpp_y": mpp_y, "crop_px": crop_px,
                        "physical_fov_um": physical_fov,
                        "physical_fov_error_um": physical_fov - 394.24,
                        "target_mask_level": mask_level_index, "target_level_x0": mx0,
                        "target_level_y0": my0, "target_level_x1": mx1,
                        "target_level_y1": my1, "conch_input_px": 448,
                        "virchow_input_px": 224, "same_boundary_for_both_models": True,
                        "overlaps_locked_pni_focus": "|".join(overlapping_candidates),
                        "inclusion_status": "eligible_descriptive_tumor" if included else "excluded",
                        "exclusion_reason": "|".join(reasons),
                    })
                    target_rows.append({
                        "tile_id": tile_id, "subject_id": subject_id, "image_id": image_id,
                        "fold": fold, "n_mask_pixels": n_pixels,
                        "n_valid_biological_pixels": n_valid, "n_tumor_pixels": n_tumor,
                        "n_stroma_pixels": n_stroma, "n_artifact_pixels": n_artifact,
                        "valid_biological_fraction": valid_fraction,
                        "artifact_fraction": artifact_fraction, "tumor_fraction": tumor_fraction,
                        "stroma_fraction": stroma_fraction,
                        "tumor_target_status": "eligible_descriptive" if included else ("missing" if not n_valid else "measured_not_eligible"),
                        "stroma_target_status": "exploratory_algorithm_assisted" if n_valid else "missing",
                        "missing_reason": "zero_valid_biological_denominator" if not n_valid else "",
                    })
                    qc_rows.append({
                        "tile_id": tile_id, "subject_id": subject_id, "image_id": image_id,
                        "fold": fold, "mask_shape_match": shape_match,
                        "mask_labels_valid": mask_labels_valid, "he_qc_level": he_qc_level_index,
                        "he_qc_width": int(he_crop.shape[1]) if he_crop.ndim >= 2 else 0,
                        "he_qc_height": int(he_crop.shape[0]) if he_crop.ndim >= 2 else 0,
                        **qc, "qc_exclusion_applied": False,
                    })
        print(f"P0-M4 inventoried {image_id}", flush=True)

    manifest = pd.DataFrame(manifest_rows, columns=M4_SCHEMAS["paired_tile_manifest.csv"])
    targets = pd.DataFrame(target_rows, columns=M4_SCHEMAS["quantitative_targets.csv"])
    qc = pd.DataFrame(qc_rows, columns=M4_SCHEMAS["tile_qc.csv"])
    if manifest.tile_id.duplicated().any() or not manifest.tile_id.equals(targets.tile_id) or not manifest.tile_id.equals(qc.tile_id):
        raise RuntimeError("P0-M4 tile IDs are duplicated or misaligned")
    for candidate_id, item in focus_audit.items():
        overlaps_candidate = manifest.overlaps_locked_pni_focus.fillna("").str.split("|").apply(
            lambda values: candidate_id in values
        )
        item["exclusion_verified"] = not bool(
            manifest.loc[overlaps_candidate, "inclusion_status"].eq("eligible_descriptive_tumor").any()
        )
    focus_frame = pd.DataFrame(list(focus_audit.values()), columns=M4_SCHEMAS["pni_focus_overlap_audit.csv"])

    eligible = manifest.inclusion_status == "eligible_descriptive_tumor"
    sessions_per_subject = manifest.groupby("subject_id").image_id.nunique()
    inventory_per_subject = manifest.groupby("subject_id").size()
    eligible_per_subject = manifest.loc[eligible].groupby("subject_id").size()
    fold_rows = [{
        "subject_id": subject, "fold": fold_map[subject], "assignment_seed": SEED,
        "assignment_method": "sorted_subjects_seeded_shuffle_round_robin_5fold",
        "n_sessions": int(sessions_per_subject.get(subject, 0)),
        "n_inventory_tiles": int(inventory_per_subject.get(subject, 0)),
        "n_tumor_eligible_tiles": int(eligible_per_subject.get(subject, 0)),
    } for subject in sorted(subjects)]
    folds = pd.DataFrame(fold_rows, columns=M4_SCHEMAS["fold_assignments.csv"])

    availability_rows: list[dict[str, object]] = []
    for target_id, target_role in (
        ("tumor_fraction", "descriptive_primary_candidate"),
        ("stroma_fraction", "exploratory_algorithm_assisted"),
    ):
        for scope, fold_value in [("overall", "all")] + [("fold", value) for value in range(5)]:
            selection = eligible if scope == "overall" else eligible & manifest.fold.eq(fold_value)
            values = targets.loc[selection, target_id].dropna()
            selected_manifest = manifest.loc[selection]
            quantiles = values.quantile([0.25, 0.5, 0.75]) if len(values) else pd.Series(dtype=float)
            n_subjects = selected_manifest.subject_id.nunique()
            fold_counts = manifest.loc[eligible].groupby("fold").subject_id.nunique()
            subject_floor = n_subjects >= (20 if scope == "overall" else 4)
            fold_floor = bool((fold_counts >= 4).all()) if scope == "overall" else n_subjects >= 4
            availability_rows.append({
                "target_id": target_id, "target_role": target_role, "scope": scope,
                "fold": fold_value, "n_sessions": selected_manifest.image_id.nunique(),
                "n_subjects": n_subjects, "n_inventory_tiles": len(selected_manifest),
                "n_evaluable_tiles": len(values),
                "n_missing_tiles": int(len(selected_manifest) - len(values)),
                "minimum": float(values.min()) if len(values) else np.nan,
                "q25": float(quantiles.get(0.25, np.nan)),
                "median": float(quantiles.get(0.5, np.nan)),
                "q75": float(quantiles.get(0.75, np.nan)),
                "maximum": float(values.max()) if len(values) else np.nan,
                "n_unique_rounded_6dp": int(values.round(6).nunique()),
                "subject_floor_met": subject_floor, "fold_floor_met": fold_floor,
                "variation_present": bool(values.max() > values.min()) if len(values) else False,
                "gate_relevance": "P0-G4 descriptive tumor feasibility" if target_id == "tumor_fraction" else "exploratory_only",
            })
    availability = pd.DataFrame(availability_rows, columns=M4_SCHEMAS["target_availability.csv"])
    write_m4_table("paired_tile_manifest.csv", manifest)
    write_m4_table("quantitative_targets.csv", targets)
    write_m4_table("tile_qc.csv", qc)
    write_m4_table("fold_assignments.csv", folds)
    write_m4_table("target_availability.csv", availability)
    write_m4_table("pni_focus_overlap_audit.csv", focus_frame)

    tumor_availability = availability[availability.target_id == "tumor_fraction"]
    overall = tumor_availability[tumor_availability.scope == "overall"].iloc[0]
    technical_pass = bool(
        manifest.same_boundary_for_both_models.all()
        and manifest.tile_id.is_unique
        and qc.mask_shape_match.all()
        and qc.mask_labels_valid.all()
        and overall.subject_floor_met
        and overall.fold_floor_met
        and tumor_availability.variation_present.all()
        and focus_frame.exclusion_verified.all()
    )
    if not technical_pass:
        decision, status = "Stop", "stop_technical_feasibility_failed"
    else:
        decision, status = "Conditional Pass", "conditional_pass_descriptive_tumor_only"
    gates = pd.read_csv(OUT / "p0_gate_matrix.csv")
    gate = gates.gate_id == "P0-G4"
    gates.loc[gate, "status"] = status
    gates.loc[gate, "draft_decision"] = decision
    gates.loc[gate, "entry_condition_met"] = technical_pass
    gates.loc[gate, "direct_evidence"] = "paired_tile_manifest.csv; quantitative_targets.csv; tile_qc.csv; fold_assignments.csv; target_availability.csv; pni_focus_overlap_audit.csv"
    gates.loc[gate, "unresolved_risk"] = "quantitative annotation repeatability absent; stroma algorithm-assisted; H&E QC thresholds not used for exclusion"
    gates.loc[gate, "next_unlocked"] = "P0-M5 technical paired embedding extraction after GPU restoration; descriptive tumor target only" if technical_pass else "none"
    gates.loc[gate, "still_prohibited"] = "confirmatory primary/secondary claims; stroma confirmatory use; P0-M6 inference before G5"
    write_table("p0_gate_matrix.csv", gates[TABLE_SCHEMAS["p0_gate_matrix.csv"]])

    unlock = pd.read_csv(OUT / "main_study_unlock_matrix.csv")
    fm2 = unlock.main_stage == "FM2"
    unlock.loc[fm2, "current_status"] = "paired_manifest_ready_descriptive_tumor_only" if technical_pass else "stopped_at_P0_G4"
    unlock.loc[fm2, "currently_allowed"] = (
        "locked paired manifest and descriptive tumor target; P0-M5 technical preparation after GPU restoration"
        if technical_pass else "read-only inventory and discrepancy review"
    )
    unlock.loc[fm2, "currently_prohibited"] = (
        "confirmatory target claim; stroma secondary claim; large extraction until P0-M5 prerequisites"
        if technical_pass else "paired extraction and concept inference"
    )
    unlock.loc[fm2, "evidence"] = "p0_gate_matrix.csv; paired_tile_manifest.csv; target_availability.csv"
    write_table("main_study_unlock_matrix.csv", unlock[TABLE_SCHEMAS["main_study_unlock_matrix.csv"]])

    overall_stroma = availability[
        (availability.target_id == "stroma_fraction") & (availability.scope == "overall")
    ].iloc[0]
    fold_subject_counts = manifest.loc[eligible].groupby("fold").subject_id.nunique().to_dict()
    report_lines = [
        "# P0-M4 paired-target technical feasibility report", "",
        f"- Protocol: `{PROTOCOL_ID}`",
        f"- P0-G4 decision: **{decision}** (`{status}`)",
        "- Allowed interpretation: descriptive tumor-fraction feasibility only", "",
        "## Provenance adjudication", "",
        "PRECISE v1 reports pixel annotations validated by two expert uropathologists through a "
        "structured three-stage consensus process, with IHC used for boundary definition. No quantitative "
        "interobserver or repeatability coefficient was found. The public stroma utility documents an "
        "algorithm-assisted fill, so stroma remains exploratory.", "",
        "## Inventory and target availability", "",
        f"- Slides/sessions: {manifest.image_id.nunique()}",
        f"- Subjects: {manifest.subject_id.nunique()}",
        f"- Full-grid inventory tiles: {len(manifest)}",
        f"- Tumor-eligible tiles after fixed mask/QC/PNI rules: {int(eligible.sum())}",
        f"- Tumor-eligible subjects: {int(overall.n_subjects)}",
        f"- Subject counts by fold: {json.dumps({str(k): int(v) for k, v in fold_subject_counts.items()}, sort_keys=True)}",
        f"- Tumor fraction range/median: {overall['minimum']:.6f}--{overall['maximum']:.6f} / {overall['median']:.6f}",
        f"- Exploratory stroma range/median: {overall_stroma['minimum']:.6f}--{overall_stroma['maximum']:.6f} / {overall_stroma['median']:.6f}",
        f"- Locked PNI foci audited/excluded: {len(focus_frame)} / verified={bool(focus_frame.exclusion_verified.all())}", "",
        "## Gate interpretation", "",
        "The paired manifest uses the same level-0 physical boundary for both encoders and subject-grouped "
        "folds. Passing P0-G4 authorizes only P0-M5 technical preparation and paired embedding extraction "
        "after the GPU prerequisite is restored. It does not establish above-chance concept recovery.", "",
        "## Claim boundary", "",
        "This is not clinical validation, a whole-slide PNI diagnostic evaluation, an encoder-superiority "
        "claim, or confirmatory validation of tumor/stroma as biological ground truth. Stroma is exploratory; "
        "nuclei and gland/lumen remain deferred.",
    ]
    (OUT / "M4_FEASIBILITY_REPORT.md").write_text("\n".join(report_lines) + "\n")

    inventory = pd.read_csv(OUT / "source_inventory.csv")
    m4_categories = {"whole_slide_image", "pixel_annotation", "exclusion_manifest", "provenance_metadata"}
    changed = []
    for row in inventory[inventory.category.isin(m4_categories)].itertuples(index=False):
        if sha256_file(Path(row.resolved_path)) != row.sha256_pre:
            changed.append(row.source_id)
    if changed:
        raise RuntimeError("P0-M4 source changed during run: " + ", ".join(changed))
    finished = datetime.now(timezone.utc)
    config_path = OUT / "run_config.json"
    config = json.loads(config_path.read_text())
    config["stage_executed"] = "P0-M0-M4 with saved P0-M3 evidence reverified"
    config["stage_not_executed"] = "P0-M5+ paired embedding extraction and concept inference"
    config["m3_saved_output_verification"] = {"encoder_gate_pass": encoder_pass, "status": "pass"}
    config["m4"] = {
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
        "execution_seconds": (finished - started).total_seconds(),
        "shared_fov_um": 394.24, "grid": "level0 origin-anchored non-overlapping full tiles",
        "mask_target_level": 3, "he_qc_level": 4,
        "eligibility": "valid biological fraction >=0.50; artifact <=0.05; denominator >0; no locked-PNI overlap",
        "n_inventory_tiles": len(manifest), "n_eligible_tumor_tiles": int(eligible.sum()),
        "n_eligible_subjects": int(manifest.loc[eligible, "subject_id"].nunique()),
        "fold_subject_counts": {str(k): int(v) for k, v in manifest.loc[eligible].groupby("fold").subject_id.nunique().items()},
        "p0_g4_status": status, "all_m4_source_pre_post_hashes_match": True,
        "claim_limit": "descriptive tumor feasibility only; no confirmatory or stroma claim",
    }
    config["output_hashes_excluding_run_config"] = {
        path.name: sha256_file(path) for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"run_config.json", "PROTOCOL.md", "run_preexperiment.py"}
    }
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "P0-G4": decision, "status": status, "inventory_tiles": len(manifest),
        "eligible_tumor_tiles": int(eligible.sum()),
        "eligible_subjects": int(manifest.loc[eligible, "subject_id"].nunique()),
    }, indent=2))


def run_pre_g0() -> None:
    started = datetime.now(timezone.utc)
    specs = source_specs()
    missing = [str(spec["path"]) for spec in specs if not Path(spec["path"]).exists()]
    if missing:
        raise FileNotFoundError("required inventory sources missing:\n" + "\n".join(missing))
    pre_hashes = {str(spec["source_id"]): sha256_file(Path(spec["path"])) for spec in specs}
    if pre_hashes["precise_clinician_review"] != EXPECTED_CLINICIAN_SHA256:
        raise RuntimeError("immutable PRECISE clinician source hash mismatch; stop")

    common, membership, truth, leakage, exclusions = build_membership_tables()
    mask_hashes = [
        pre_hashes[str(spec["source_id"])]
        for spec in specs if spec["category"] == "pixel_annotation"
    ]
    metrics, provenance = metric_tables(mask_hashes)
    claims, deviations, gates, unlock = governance_tables()

    write_table("metric_eligibility.tsv", metrics)
    write_table("measurement_provenance.csv", provenance)
    write_table("common_sample_manifest.csv", common)
    write_table("membership_mismatch.csv", membership)
    write_table("truth_mismatch.csv", truth)
    write_table("leakage_audit.csv", leakage)
    write_table("exclusion_flow.csv", exclusions)
    write_table("claim_evidence_matrix.csv", claims)
    write_table("deviation_log.csv", deviations)
    write_table("p0_gate_matrix.csv", gates)
    write_table("main_study_unlock_matrix.csv", unlock)

    inventory_rows = [inspect_source(spec, pre_hashes[str(spec["source_id"])]) for spec in specs]
    for row, spec in zip(inventory_rows, specs, strict=True):
        post_hash = sha256_file(Path(spec["path"]))
        row["sha256_post"] = post_hash
        row["pre_post_match"] = post_hash == row["sha256_pre"]
    inventory = pd.DataFrame(inventory_rows, columns=TABLE_SCHEMAS["source_inventory.csv"])
    write_table("source_inventory.csv", inventory)
    if not inventory.pre_post_match.all():
        raise RuntimeError("one or more source hashes changed during the read-only audit")

    summary = {
        "nadt_grade": {
            "common_slides": int(((common.cohort_id == "NADT-Prostate") & (common.endpoint_id == "gleason_total")).sum()),
            "common_subjects": int(common.loc[(common.cohort_id == "NADT-Prostate") & (common.endpoint_id == "gleason_total"), "subject_id"].nunique()),
            "truth_mismatches": int(((truth.cohort_id == "NADT-Prostate") & (truth.endpoint_id == "gleason_total")).sum()) if len(truth) else 0,
        },
        "nadt_phenotype": {
            "common_slides": int(((common.cohort_id == "NADT-Prostate") & (common.endpoint_id == "tumor_vs_benign")).sum()),
            "common_subjects": int(common.loc[(common.cohort_id == "NADT-Prostate") & (common.endpoint_id == "tumor_vs_benign"), "subject_id"].nunique()),
            "truth_mismatches": int(((truth.cohort_id == "NADT-Prostate") & (truth.endpoint_id == "tumor_vs_benign")).sum()) if len(truth) else 0,
        },
        "panda": {
            "common_images": int(((common.cohort_id == "PANDA") & (common.endpoint_id == "isup_grade")).sum()),
            "conch_only": int((membership.membership_status == "conch_only").sum()),
            "virchow_only": int((membership.membership_status == "virchow_only").sum()),
            "neither_model": int((membership.membership_status == "neither_model").sum()),
            "truth_mismatches": int((truth.cohort_id == "PANDA").sum()) if len(truth) else 0,
            "common_tile_count_mismatches": int(common.loc[common.cohort_id == "PANDA", "notes"].eq("tile-count mismatch between encoders").sum()),
            "subject_linkage": "not_available",
        },
        "tcga_prad": {
            "common_slides_per_endpoint": int(((common.cohort_id == "TCGA-PRAD") & (common.endpoint_id == "pten")).sum()),
            "common_cases_per_endpoint": int(common.loc[(common.cohort_id == "TCGA-PRAD") & (common.endpoint_id == "pten"), "subject_id"].nunique()),
            "truth_mismatches": int((truth.cohort_id == "TCGA-PRAD").sum()) if len(truth) else 0,
        },
        "leopard": {
            "common_cases": int(((common.cohort_id == "LEOPARD") & (common.endpoint_id == "recurrence")).sum()),
            "truth_mismatches": int((truth.cohort_id == "LEOPARD").sum()) if len(truth) else 0,
        },
        "stability": {
            "design_cells": int(pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv").shape[0]),
            "result_cells": int(pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv").shape[0]),
            "fold_rows": int(pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv").shape[0]),
            "coordinate_manifest_rows": int(pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv").shape[0]),
        },
    }
    finished = datetime.now(timezone.utc)
    output_hashes = {
        name: sha256_file(OUT / name)
        for name in TABLE_SCHEMAS
        if (OUT / name).exists()
    }
    config = {
        "protocol_id": PROTOCOL_ID,
        "protocol_status": "approved_P0_G0_pass",
        "approval": APPROVAL,
        "stage_executed": "approved-P0-M0-M2-read-only-integrity-audit",
        "stage_not_executed": "P0-M3 predictive refit/permutation and all P0-M4+ work",
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
        "execution_seconds": (finished - started).total_seconds(), "random_seed_proposal": SEED,
        "python": sys.version.replace("\n", " "), "platform": platform.platform(),
        "packages": package_versions(), "git": git_context(),
        "models": {
            "CONCH": {
                "model_id": "conch_ViT-B-16 / MahmoodLab/conch", "revision": "f9ca9f877171a28ade80228fb195ac5d79003357",
                "weights_sha256": pre_hashes["conch_weights"], "embedding_dimension": 512,
                "input_pixels": [448, 448], "preprocessing": {"resize": 448, "center_crop": 448, "interpolation": "bicubic", "mean": [0.48145466, 0.4578275, 0.40821073], "std": [0.26862954, 0.26130258, 0.27577711]},
                "historical_native_target_mpp": 0.88, "historical_native_fov_um": 394.24,
            },
            "Virchow": {
                "model_id": "hf-hub:paige-ai/Virchow", "revision": "19eebc84ae33e79f1b2d866e6ff90ae50e522f9a",
                "weights_sha256": pre_hashes["virchow_weights"], "embedding_dimension": 2560,
                "embedding_definition": "concatenate CLS token and mean patch tokens",
                "input_pixels": [224, 224], "preprocessing": {"resize": 224, "center_crop": 224, "crop_pct": 1.0, "interpolation": "bicubic", "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
                "historical_native_target_mpp": 0.44, "historical_native_fov_um": 98.56,
            },
        },
        "approved_decision_sheet": {
            "primary_target": "PRECISE tumor fraction, conditional on expert-mask provenance confirmation",
            "primary_shared_fov_um": 394.24,
            "shared_fov_rule": "identical center and 394.24-µm square tissue extent; resize independently to each model input",
            "native_fov_sensitivity_um": {"CONCH": 394.24, "Virchow": 98.56},
            "outer_folds": 5, "fold_rule": "subject-grouped; existing locked assignments for P0-M3; seeded group shuffle for new PRECISE folds",
            "probe_family": "standardized L2-regularized linear models",
            "continuous_probe": "Ridge with nested grouped selection from 17 log-spaced alpha values 1e-4..1e4",
            "binary_probe": "L2 logistic regression with the reciprocal 17-value C grid and identical tuning budget",
            "continuous_metrics": ["MAE", "R2", "Spearman"],
            "permutation": {"unit": "subject/case", "replicates": 2000, "seed": SEED, "undefined_replicates_retained": True},
            "bootstrap": {"unit": "subject", "paired": True, "replicates": 2000, "seed": SEED + 1, "undefined_replicates_retained": True},
            "multiplicity": "BH-FDR within the approved primary model×target association family; raw and adjusted results both retained",
        },
        "inventory_summary": summary,
        "immutable_clinician_source_expected_sha256": EXPECTED_CLINICIAN_SHA256,
        "immutable_clinician_source_verified": pre_hashes["precise_clinician_review"] == EXPECTED_CLINICIAN_SHA256,
        "all_source_pre_post_hashes_match": bool(inventory.pre_post_match.all()),
        "output_hashes_excluding_run_config": output_hashes,
    }
    (OUT / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("P0-G0 PASS: existing frozen-embedding source-control P0-M3 is authorized.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=["pre-g0", "m3", "m4", "m5", "m6", "m7-native", "m7", "m8"],
        default="pre-g0",
    )
    parser.add_argument("--m5-encoder", choices=["conch", "virchow", "both"], default="both")
    parser.add_argument("--smoke-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "pre-g0":
        run_pre_g0()
    elif args.stage == "m3":
        run_m3()
    elif args.stage == "m4":
        run_m4()
    elif args.stage == "m5":
        encoders = ("conch", "virchow") if args.m5_encoder == "both" else (args.m5_encoder,)
        for encoder in encoders:
            run_m5_encoder(encoder, smoke_only=args.smoke_only)
    elif args.stage == "m6":
        run_m6()
    elif args.stage == "m7-native":
        run_m7_native_extraction(smoke_only=args.smoke_only)
    elif args.stage == "m7":
        run_m7()
    elif args.stage == "m8":
        run_m8()


if __name__ == "__main__":
    main()
