"""Generate auditable P0 artifacts for the MR-v1 completion plan.

This records a retrospective repository snapshot.  It never fabricates a historical Git
commit or labels the snapshot as prospective.  Outputs are deterministic except for the
explicit generation timestamp in protocol_provenance.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from projects.prostate_biomarker_validation.paper.figures.fig9_scale_tile_heatmap import validate_contrasts, validate_grid

PAPER = ROOT / "projects/prostate_biomarker_validation/paper"


def rel(path: Path) -> str:
    # Preserve the repository-facing path even when an opendataset directory is a symlink to
    # centrally managed storage outside the workspace.
    return str(path.relative_to(ROOT))


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def id_list_sha256(values) -> str:
    payload = "".join(f"{value}\n" for value in sorted(map(str, values))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_markdown_table(frame: pd.DataFrame, path: Path, title: str, note: str) -> None:
    def clean(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [f"# {title}", "", note, "", "| " + " | ".join(frame.columns) + " |",
             "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(clean(v) for v in row) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


STABILITY_MARKERS = ("gleason", "phenotype", "pten", "spop", "ar", "marker7")
EVIDENCE_STATES = {
    "transportable",
    "context_sensitive",
    "unsupported_in_frozen_design",
    "descriptive_framework",
}
SUBMISSION_SOURCE_SCHEMAS = {
    "fig1_qualification_map.csv": (
        "semantic_key", "claim_id", "display_order", "claim_label", "marker",
        "hierarchy", "evidence_state", "qualification_decision", "limitation",
        "primary_estimate", "missingness_status", "missingness_detail", "source_path",
        "source_field",
    ),
    "fig2_transportable_signals.csv": (
        "semantic_key", "signal", "cohort", "institution", "encoder", "metric",
        "analysis_unit", "n", "n_events", "primary_estimate", "ci_low", "ci_high",
        "evidence_state", "missingness_status", "missingness_detail", "source_path",
        "source_field",
    ),
    "fig3_molecular_qualification.csv": (
        "semantic_key", "target", "component", "cohort", "encoder", "metric",
        "analysis_unit", "patient_denominator", "event_count", "null_value",
        "primary_estimate", "interval_low", "interval_high", "interval_type",
        "range_low", "range_high", "n_correlated_cells", "evidence_state",
        "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
    "fig4_confounder_site_audit.csv": (
        "semantic_key", "target", "audit_type", "site", "encoder", "metric",
        "analysis_unit", "cluster_unit", "interval_type", "n_slides", "n_patients",
        "n_events", "primary_estimate", "ci_low", "ci_high", "null_value",
        "evidence_state", "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
    "fig5_marker7_transfer.csv": (
        "semantic_key", "endpoint_id", "endpoint_label", "result_type", "contrast_id",
        "metric", "n", "n_events", "primary_estimate", "ci_low", "ci_high",
        "null_value", "evidence_state", "missingness_status", "missingness_detail",
        "source_path", "source_field",
    ),
    "fig6_stability_overview.csv": (
        "semantic_key", "marker", "component", "metric", "null_value",
        "primary_estimate", "range_low", "range_high", "n_configurations",
        "n_correlated_cells", "n_null_crossings", "n_contrasts", "evidence_state",
        "missingness_status", "missingness_detail", "source_path", "source_field",
    ),
}
R2_R5_PROVENANCE_RELATIVE_PATHS = (
    "projects/prostate_biomarker_validation/code/legacy/run_marker7_common_source_sensitivity.py",
    "projects/prostate_biomarker_validation/tests/test_marker7_common_source_sensitivity.py",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_common_source_sensitivity_cells.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_common_source_sensitivity_paired_deltas.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_common_source_membership_manifest.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_common_source_sensitivity_run_config.json",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_common_source_sensitivity_run_manifest.csv",
    "projects/prostate_biomarker_validation/code/legacy/build_ar_spop_evidence_closure.py",
    "projects/prostate_biomarker_validation/tests/test_ar_spop_evidence_closure.py",
    "projects/prostate_biomarker_validation/outputs/legacy/ar_site_characteristics.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/ar_slide_metadata_availability.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/spop_site_summary.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/spop_power_summary.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/spop_site_predictions.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/ar_spop_evidence_run_config.json",
    "projects/prostate_biomarker_validation/outputs/legacy/ar_spop_evidence_manifest.csv",
)
R3_R4_PROVENANCE_RELATIVE_PATHS = (
    "projects/prostate_biomarker_validation/code/legacy/build_tcga_cdr_pfi_evidence.py",
    "projects/prostate_biomarker_validation/tests/test_tcga_cdr_pfi_evidence.py",
    "projects/prostate_biomarker_validation/outputs/legacy/tcga_cdr_pfi_mapping.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/pfi_endpoint_concordance.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/pfi_performance_summary.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/tcga_cdr_pfi_patient_predictions.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/tcga_cdr_pfi_run_config.json",
    "projects/prostate_biomarker_validation/outputs/legacy/tcga_cdr_pfi_run_manifest.csv",
    "projects/prostate_biomarker_validation/code/legacy/build_marker7_survival_paired_analysis.py",
    "projects/prostate_biomarker_validation/tests/test_marker7_survival_paired_analysis.py",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_common_cohort_summary.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_paired_deltas.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_bootstrap_replicates.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_oof_survival_predictions.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_fold_diagnostics.csv",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_paired_run_config.json",
    "projects/prostate_biomarker_validation/outputs/legacy/marker7_survival_paired_run_manifest.csv",
)


def validate_required_provenance_paths(paths) -> None:
    missing = [str(Path(path)) for path in paths if not Path(path).is_file()]
    if missing:
        raise ValueError(f"required provenance paths are missing: {missing}")


def _validate_manifest_bound_outputs(
    manifest_csv: Path,
    output_paths: tuple[Path, ...],
    *,
    label: str,
) -> None:
    """Bind every consumed frozen CSV to its producer manifest's exact output hash."""
    manifest_csv = Path(manifest_csv)
    if not manifest_csv.is_file():
        raise ValueError(f"{label}: producer run manifest is missing: {manifest_csv}")
    manifest = pd.read_csv(manifest_csv)
    required = {"artifact_kind", "artifact_path", "sha256_after"}
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"{label}: producer manifest is missing columns {missing}")
    outputs = manifest.loc[manifest["artifact_kind"].astype(str).eq("output")].copy()
    output_basenames = outputs["artifact_path"].astype(str).map(lambda value: Path(value).name)
    for path in map(Path, output_paths):
        matches = outputs.loc[output_basenames.eq(path.name)]
        if len(matches) != 1:
            raise ValueError(
                f"{label}: expected one manifest output row for {path.name}, found {len(matches)}"
            )
        row = matches.iloc[0]
        expected = str(row["sha256_after"]).strip().lower()
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise ValueError(f"{label}: invalid manifest SHA256 for {path.name}")
        if "included_in_output_hashes" in matches.columns:
            included = _bool_values(matches, "included_in_output_hashes", label).iloc[0]
            if not included:
                raise ValueError(f"{label}: {path.name} is not included in output hashes")
        if "hash_reconciled" in matches.columns:
            reconciled = _bool_values(matches, "hash_reconciled", label).iloc[0]
            if not reconciled:
                raise ValueError(f"{label}: {path.name} manifest hash is not reconciled")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(
                f"{label}: {path.name} SHA256 does not match producer manifest "
                f"({actual} != {expected})"
            )


def _read_csv_contract(
    path: Path,
    *,
    label: str,
    expected_rows: int,
    required_columns: tuple[str, ...],
    unique_columns: tuple[str, ...],
) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"{label}: required saved CSV is missing: {path}")
    frame = pd.read_csv(path)
    if len(frame) != expected_rows:
        raise ValueError(f"{label}: expected {expected_rows} rows, found {len(frame)}")
    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing required columns {missing}")
    if frame[list(unique_columns)].isna().any().any():
        raise ValueError(f"{label}: key columns contain missing values")
    if frame.duplicated(list(unique_columns)).any():
        raise ValueError(f"{label}: duplicate key rows")
    return frame


def _bool_values(frame: pd.DataFrame, column: str, label: str) -> pd.Series:
    values = frame[column]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.astype(bool)
    normalized = values.astype(str).str.strip().str.lower()
    if not normalized.isin({"true", "false"}).all():
        raise ValueError(f"{label}: {column} must contain only true/false")
    return normalized.eq("true")


def _finite_values(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{label}: {column} must be finite numeric")


def null_relation_crossing(
    values_a: pd.Series,
    values_b: pd.Series,
    *,
    null_value: float,
) -> pd.Series:
    a = pd.to_numeric(values_a, errors="coerce")
    b = pd.to_numeric(values_b, errors="coerce")
    if a.isna().any() or b.isna().any():
        raise ValueError("null-relation inputs must be numeric")
    relation_a = np.where(a > null_value, 1, np.where(a < null_value, -1, 0))
    relation_b = np.where(b > null_value, 1, np.where(b < null_value, -1, 0))
    return pd.Series(relation_a != relation_b, index=a.index, dtype=bool)


def _binary_auc(labels: pd.Series, scores: pd.Series) -> float:
    y = pd.to_numeric(labels, errors="coerce")
    s = pd.to_numeric(scores, errors="coerce")
    if y.isna().any() or s.isna().any() or not y.isin({0, 1}).all():
        raise ValueError("binary AUROC inputs must be finite with labels in {0,1}")
    n_positive = int(y.sum())
    n_negative = int(len(y) - n_positive)
    if n_positive == 0 or n_negative == 0:
        return float("nan")
    ranks = s.rank(method="average")
    positive_rank_sum = float(ranks.loc[y.eq(1)].sum())
    return (
        positive_rank_sum - n_positive * (n_positive + 1) / 2
    ) / (n_positive * n_negative)


def _validate_bootstrap_accounting(frame: pd.DataFrame, label: str) -> None:
    _finite_values(
        frame,
        (
            "n_bootstrap_requested", "n_bootstrap_valid", "n_bootstrap_undefined",
            "bootstrap_undefined_fraction",
        ),
        label,
    )
    requested = pd.to_numeric(frame["n_bootstrap_requested"])
    valid = pd.to_numeric(frame["n_bootstrap_valid"])
    undefined = pd.to_numeric(frame["n_bootstrap_undefined"])
    fraction = pd.to_numeric(frame["bootstrap_undefined_fraction"])
    if not requested.eq(2000).all():
        raise ValueError(f"{label}: every row must request 2000 bootstrap replicates")
    if not np.array_equal((valid + undefined).to_numpy(), requested.to_numpy()):
        raise ValueError(f"{label}: valid plus undefined bootstrap counts do not reconcile")
    expected_fraction = undefined / requested
    if not np.allclose(fraction, expected_fraction, atol=5e-15, rtol=0):
        raise ValueError(f"{label}: undefined bootstrap fraction does not reconcile")


def load_r3_sources(
    mapping_csv: Path,
    concordance_csv: Path,
    performance_csv: Path,
    manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_run_manifest.csv",
) -> dict[str, object]:
    """Validate the frozen official-PFI audit before reusing its reported values."""
    _validate_manifest_bound_outputs(
        manifest_csv,
        (Path(mapping_csv), Path(concordance_csv), Path(performance_csv)),
        label="R3 frozen outputs",
    )
    mapping = _read_csv_contract(
        mapping_csv,
        label="R3 official-PFI mapping",
        expected_rows=270,
        required_columns=(
            "case_id", "marker7_risk", "official_pfi_event", "official_pfi_time_days",
            "official_pfi_time_years", "mapping_status", "endpoint_status",
        ),
        unique_columns=("case_id",),
    )
    _finite_values(
        mapping,
        ("marker7_risk", "official_pfi_event", "official_pfi_time_days", "official_pfi_time_years"),
        "R3 official-PFI mapping",
    )
    events = pd.to_numeric(mapping["official_pfi_event"])
    if not events.isin({0, 1}).all() or int(events.sum()) != 42:
        raise ValueError("R3 official-PFI mapping: expected 42 binary events")
    if not pd.to_numeric(mapping["official_pfi_time_days"]).gt(0).all():
        raise ValueError("R3 official-PFI mapping: follow-up time must be positive")
    if not mapping["mapping_status"].astype(str).eq("one_to_one").all():
        raise ValueError("R3 official-PFI mapping: every mapping must be one_to_one")
    if not mapping["endpoint_status"].astype(str).eq("evaluable").all():
        raise ValueError("R3 official-PFI mapping: every endpoint must be evaluable")

    performance = _read_csv_contract(
        performance_csv,
        label="R3 endpoint performance",
        expected_rows=5,
        required_columns=(
            "endpoint_id", "n_frozen_risk_patients", "n_evaluable", "n_events", "c_index",
            "n_bootstrap_requested", "n_bootstrap_valid", "n_bootstrap_undefined",
            "bootstrap_undefined_fraction", "c_index_ci_low", "c_index_ci_high", "status",
        ),
        unique_columns=("endpoint_id",),
    )
    expected_endpoints = {
        "official_tcga_cdr_pfi", "reconstructed_gdc_disease_response",
        "cbioportal_tcga_cdr_pfs", "cbioportal_tcga_cdr_dfs",
        "gdc_recurrence_only_after_tumor_free",
    }
    if set(performance["endpoint_id"].astype(str)) != expected_endpoints:
        raise ValueError("R3 endpoint performance: endpoint identity set does not reconcile")
    _finite_values(
        performance,
        ("n_frozen_risk_patients", "n_evaluable", "n_events", "c_index", "c_index_ci_low", "c_index_ci_high"),
        "R3 endpoint performance",
    )
    if not pd.to_numeric(performance["n_frozen_risk_patients"]).eq(270).all():
        raise ValueError("R3 endpoint performance: frozen risk cohort must contain 270 patients")
    if not performance["status"].astype(str).eq("complete").all():
        raise ValueError("R3 endpoint performance: every endpoint must be complete")
    _validate_bootstrap_accounting(performance, "R3 endpoint performance")

    concordance = _read_csv_contract(
        concordance_csv,
        label="R3 endpoint concordance",
        expected_rows=4,
        required_columns=(
            "reference_endpoint_id", "comparison_endpoint_id", "n_common_evaluable",
            "event_agreement", "cohen_kappa", "n_time_pairs", "time_spearman_rho", "status",
        ),
        unique_columns=("reference_endpoint_id", "comparison_endpoint_id"),
    )
    if not concordance["reference_endpoint_id"].astype(str).eq("official_tcga_cdr_pfi").all():
        raise ValueError("R3 endpoint concordance: official PFI must be the reference")
    expected_comparisons = expected_endpoints - {"official_tcga_cdr_pfi"}
    if set(concordance["comparison_endpoint_id"].astype(str)) != expected_comparisons:
        raise ValueError("R3 endpoint concordance: comparison identity set does not reconcile")
    _finite_values(
        concordance,
        ("n_common_evaluable", "event_agreement", "cohen_kappa", "n_time_pairs", "time_spearman_rho"),
        "R3 endpoint concordance",
    )
    if not concordance["status"].astype(str).eq("complete").all():
        raise ValueError("R3 endpoint concordance: every comparison must be complete")

    official = performance.set_index("endpoint_id").loc["official_tcga_cdr_pfi"]
    pfs = concordance.set_index("comparison_endpoint_id").loc["cbioportal_tcga_cdr_pfs"]
    return {"mapping": mapping, "performance": performance, "concordance": concordance,
            "official": official, "pfs": pfs}


def load_r4_sources(
    summary_csv: Path,
    deltas_csv: Path,
    manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_run_manifest.csv",
) -> dict[str, object]:
    """Validate the frozen same-patient/same-draw paired survival analysis."""
    _validate_manifest_bound_outputs(
        manifest_csv, (Path(summary_csv), Path(deltas_csv)), label="R4 frozen outputs"
    )
    endpoints = {"E04_reconstructed_with_tumor": 30, "E08_official_pfi": 15}
    models = {
        "H_M0", "H_M1", "H_M2", "H_M3", "H_M4", "H_M5", "N_IMAGE",
        "N_GRADE_CLINICAL", "N_GRADE_COMBINED", "N_FULL_CLINICAL", "N_FULL_COMBINED",
    }
    metrics = {"c_index", "ibs_0.5_5y"}
    summary = _read_csv_contract(
        summary_csv,
        label="R4 common-cohort summary",
        expected_rows=44,
        required_columns=(
            "endpoint_id", "model_id", "n_patients", "n_events", "metric", "estimate",
            "ci_low", "ci_high", "n_bootstrap_requested", "n_bootstrap_valid",
            "n_bootstrap_undefined", "bootstrap_undefined_fraction",
        ),
        unique_columns=("endpoint_id", "model_id", "metric"),
    )
    expected_summary_keys = {(e, m, metric) for e in endpoints for m in models for metric in metrics}
    if set(map(tuple, summary[["endpoint_id", "model_id", "metric"]].astype(str).to_numpy())) != expected_summary_keys:
        raise ValueError("R4 common-cohort summary: model/endpoint/metric keys do not reconcile")
    _finite_values(summary, ("n_patients", "n_events", "estimate", "ci_low", "ci_high"),
                   "R4 common-cohort summary")
    for endpoint, n_events in endpoints.items():
        rows = summary["endpoint_id"].astype(str).eq(endpoint)
        if not pd.to_numeric(summary.loc[rows, "n_patients"]).eq(153).all():
            raise ValueError(f"R4 common-cohort summary: {endpoint} must use 153 patients")
        if not pd.to_numeric(summary.loc[rows, "n_events"]).eq(n_events).all():
            raise ValueError(f"R4 common-cohort summary: {endpoint} event count does not reconcile")
    _validate_bootstrap_accounting(summary, "R4 common-cohort summary")

    contrasts = {
        "IMAGE_VS_GRADE", "GRADE_COMBINED_VS_GRADE", "IMAGE_VS_FULL",
        "FULL_COMBINED_VS_FULL", "M5_VS_M4",
    }
    deltas = _read_csv_contract(
        deltas_csv,
        label="R4 paired deltas",
        expected_rows=20,
        required_columns=(
            "endpoint_id", "contrast_id", "metric", "metric_a", "metric_b",
            "raw_delta_b_minus_a", "improvement_delta", "improvement_ci_low",
            "improvement_ci_high", "n_patients", "n_events", "n_bootstrap_requested",
            "n_bootstrap_valid", "n_bootstrap_undefined", "bootstrap_undefined_fraction",
            "delta_definition",
        ),
        unique_columns=("endpoint_id", "contrast_id", "metric"),
    )
    expected_delta_keys = {(e, c, metric) for e in endpoints for c in contrasts for metric in metrics}
    if set(map(tuple, deltas[["endpoint_id", "contrast_id", "metric"]].astype(str).to_numpy())) != expected_delta_keys:
        raise ValueError("R4 paired deltas: contrast/endpoint/metric keys do not reconcile")
    _finite_values(
        deltas,
        ("metric_a", "metric_b", "raw_delta_b_minus_a", "improvement_delta",
         "improvement_ci_low", "improvement_ci_high", "n_patients", "n_events"),
        "R4 paired deltas",
    )
    raw_expected = pd.to_numeric(deltas["metric_b"]) - pd.to_numeric(deltas["metric_a"])
    if not np.allclose(raw_expected, pd.to_numeric(deltas["raw_delta_b_minus_a"]), atol=5e-15, rtol=0):
        raise ValueError("R4 paired deltas: raw delta arithmetic does not reconcile")
    c_rows = deltas["metric"].astype(str).eq("c_index")
    ibs_rows = ~c_rows
    if not np.allclose(
        pd.to_numeric(deltas.loc[c_rows, "improvement_delta"]), raw_expected.loc[c_rows],
        atol=5e-15, rtol=0,
    ) or not np.allclose(
        pd.to_numeric(deltas.loc[ibs_rows, "improvement_delta"]), -raw_expected.loc[ibs_rows],
        atol=5e-15, rtol=0,
    ):
        raise ValueError("R4 paired deltas: improvement direction arithmetic does not reconcile")
    if not deltas.loc[c_rows, "delta_definition"].astype(str).eq("model_b-model_a").all():
        raise ValueError("R4 paired deltas: C-index delta definition is invalid")
    if not deltas.loc[ibs_rows, "delta_definition"].astype(str).eq("IBS_a-IBS_b").all():
        raise ValueError("R4 paired deltas: IBS delta definition is invalid")
    for endpoint, n_events in endpoints.items():
        rows = deltas["endpoint_id"].astype(str).eq(endpoint)
        if not pd.to_numeric(deltas.loc[rows, "n_patients"]).eq(153).all():
            raise ValueError(f"R4 paired deltas: {endpoint} must use 153 patients")
        if not pd.to_numeric(deltas.loc[rows, "n_events"]).eq(n_events).all():
            raise ValueError(f"R4 paired deltas: {endpoint} event count does not reconcile")
    _validate_bootstrap_accounting(deltas, "R4 paired deltas")
    indexed = deltas.set_index(["endpoint_id", "contrast_id", "metric"])
    return {"summary": summary, "deltas": deltas, "indexed": indexed}


def load_r2_sources(
    cells_csv: Path,
    deltas_csv: Path,
    membership_csv: Path,
    manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_run_manifest.csv",
) -> dict[str, object]:
    _validate_manifest_bound_outputs(
        manifest_csv,
        (Path(cells_csv), Path(deltas_csv), Path(membership_csv)),
        label="R2 frozen outputs",
    )
    cells = _read_csv_contract(
        cells_csv,
        label="R2 cells",
        expected_rows=60,
        required_columns=(
            "cell_id", "marker", "canonical_cohort", "outcome_type", "primary_metric",
            "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
            "source_configuration_id", "n_common_source_patients", "n_source_events",
            "n_original_source_patients",
            "n_target_slides", "n_target_patients", "n_target_events", "n_target_folds",
            "saved_raw_c_index", "integrated_raw_c_index", "recomputed_raw_c_index",
            "raw_reproduction_error_vs_saved", "raw_reproduction_error_vs_integrated",
            "common_source_c_index", "common_minus_saved_raw",
            "raw_relation_to_null", "common_relation_to_null",
            "raw_common_null_crossing", "status",
        ),
        unique_columns=("cell_id",),
    )
    expected_cells: dict[str, tuple[str, int, int, float, str]] = {}
    expected_source_configs: dict[str, tuple[str, int, float]] = {}
    for encoder, mpps in (("CONCH", (0.88, 1.76)), ("Virchow", (0.44, 1.76))):
        for seed in range(5):
            for mpp in mpps:
                config_id = f"{encoder.lower()}__s{seed}__mpp{mpp:.2f}"
                expected_source_configs[config_id] = (encoder, seed, mpp)
                for tiles in (16, 32, 64):
                    cell_id = (
                        f"marker7__{encoder.lower()}__s{seed}__t{tiles}__mpp{mpp:.2f}"
                    )
                    expected_cells[cell_id] = (encoder, seed, tiles, mpp, config_id)
    if set(cells["cell_id"].astype(str)) != set(expected_cells):
        raise ValueError("R2 cells: exact 60-cell identity set does not reconcile")
    categorical_contract = {
        "marker": "marker7",
        "canonical_cohort": "LEOPARD-to-TCGA-PRAD",
        "outcome_type": "survival",
        "primary_metric": "patient_c_index",
    }
    for column, expected in categorical_contract.items():
        if not cells[column].astype(str).eq(expected).all():
            raise ValueError(f"R2 cells: {column} must be {expected}")
    for row in cells[[
        "cell_id", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
        "source_configuration_id",
    ]].itertuples(index=False):
        expected_encoder, expected_seed, expected_tiles, expected_mpp, expected_config = (
            expected_cells[str(row.cell_id)]
        )
        if (
            str(row.encoder) != expected_encoder
            or float(row.sampling_seed) != expected_seed
            or float(row.tiles_per_slide) != expected_tiles
            or not np.isclose(float(row.target_mpp), expected_mpp, atol=1e-12, rtol=0)
            or str(row.source_configuration_id) != expected_config
        ):
            raise ValueError(f"R2 cells: axes/configuration do not match {row.cell_id}")
    _finite_values(
        cells,
        (
            "sampling_seed", "tiles_per_slide", "target_mpp",
            "n_original_source_patients", "n_common_source_patients", "n_source_events", "n_target_slides",
            "n_target_patients", "n_target_events", "n_target_folds",
            "saved_raw_c_index", "integrated_raw_c_index", "recomputed_raw_c_index",
            "raw_reproduction_error_vs_saved", "raw_reproduction_error_vs_integrated",
            "common_source_c_index", "common_minus_saved_raw",
        ),
        "R2 cells",
    )
    exact_counts = {
        "n_common_source_patients": 498,
        "n_source_events": 85,
        "n_target_slides": 297,
        "n_target_patients": 270,
        "n_target_events": 57,
        "n_target_folds": 5,
    }
    for column, expected in exact_counts.items():
        if not pd.to_numeric(cells[column]).eq(expected).all():
            raise ValueError(f"R2 cells: {column} must be {expected} for all 60 cells")
    if not cells["status"].astype(str).eq("complete").all():
        raise ValueError("R2 cells: every status must be complete")
    recomputed = pd.to_numeric(cells["recomputed_raw_c_index"])
    expected_error_saved = (recomputed - pd.to_numeric(cells["saved_raw_c_index"])).abs()
    expected_error_integrated = (
        recomputed - pd.to_numeric(cells["integrated_raw_c_index"])
    ).abs()
    for column, expected_error in (
        ("raw_reproduction_error_vs_saved", expected_error_saved),
        ("raw_reproduction_error_vs_integrated", expected_error_integrated),
    ):
        recorded = pd.to_numeric(cells[column])
        if not np.allclose(recorded, expected_error, atol=5e-15, rtol=0):
            raise ValueError(f"R2 cells: {column} arithmetic does not reconcile")
        if recorded.gt(1e-15).any():
            raise ValueError(f"R2 cells: {column} exceeds frozen reproduction tolerance")
    calculated_shift = cells["common_source_c_index"] - cells["saved_raw_c_index"]
    if not np.allclose(
        calculated_shift.to_numpy(dtype=float),
        cells["common_minus_saved_raw"].to_numpy(dtype=float),
        atol=5e-15,
        rtol=0,
    ):
        raise ValueError("R2 cells: common-minus-raw arithmetic does not reconcile")
    raw_relation = np.where(cells["saved_raw_c_index"] > 0.5, "above_null", np.where(
        cells["saved_raw_c_index"] < 0.5, "below_null", "at_null"
    ))
    common_relation = np.where(cells["common_source_c_index"] > 0.5, "above_null", np.where(
        cells["common_source_c_index"] < 0.5, "below_null", "at_null"
    ))
    if not np.array_equal(raw_relation, cells["raw_relation_to_null"].astype(str).to_numpy()):
        raise ValueError("R2 cells: saved raw null relation does not reconcile")
    if not np.array_equal(
        common_relation, cells["common_relation_to_null"].astype(str).to_numpy()
    ):
        raise ValueError("R2 cells: common-source null relation does not reconcile")
    crossings = _bool_values(cells, "raw_common_null_crossing", "R2 cells")
    calculated_crossing = null_relation_crossing(
        cells["saved_raw_c_index"], cells["common_source_c_index"], null_value=0.5
    )
    if not np.array_equal(crossings.to_numpy(), calculated_crossing.to_numpy()) or crossings.any():
        raise ValueError("R2 cells: audited raw-to-common null crossing count must be zero")

    deltas = _read_csv_contract(
        deltas_csv,
        label="R2 paired deltas",
        expected_rows=65,
        required_columns=(
            "contrast", "pair_id", "cell_id_a", "cell_id_b", "raw_metric_a",
            "raw_metric_b", "raw_delta_b_minus_a", "common498_metric_a",
            "common498_metric_b", "common498_delta_b_minus_a", "raw_direction",
            "common498_direction", "direction_status", "raw_null_crossing",
            "common498_null_crossing", "raw_exact_tie", "common498_exact_tie",
        ),
        unique_columns=("pair_id",),
    )
    expected_contrast_counts = {
        "native_vs_1.76": 30,
        "tile64_vs16": 20,
        "virchow_vs_conch_at_1.76": 15,
    }
    if deltas.groupby("contrast").size().to_dict() != expected_contrast_counts:
        raise ValueError("R2 paired deltas: expected 30 scale, 20 tile, and 15 encoder rows")
    expected_pairs: dict[str, tuple[str, str, str]] = {}
    for encoder, native_mpp in (("conch", 0.88), ("virchow", 0.44)):
        for seed in range(5):
            for tiles in (16, 32, 64):
                pair_id = f"native_vs_1.76__marker7__{encoder}__s{seed}__t{tiles}"
                expected_pairs[pair_id] = (
                    "native_vs_1.76",
                    f"marker7__{encoder}__s{seed}__t{tiles}__mpp{native_mpp:.2f}",
                    f"marker7__{encoder}__s{seed}__t{tiles}__mpp1.76",
                )
    for seed in range(5):
        for tiles in (16, 32, 64):
            pair_id = f"virchow_vs_conch_at_1.76__marker7__s{seed}__t{tiles}"
            expected_pairs[pair_id] = (
                "virchow_vs_conch_at_1.76",
                f"marker7__conch__s{seed}__t{tiles}__mpp1.76",
                f"marker7__virchow__s{seed}__t{tiles}__mpp1.76",
            )
    for encoder, mpps in (("conch", (0.88, 1.76)), ("virchow", (0.44, 1.76))):
        for seed in range(5):
            for mpp in mpps:
                pair_id = f"tile64_vs16__marker7__{encoder}__s{seed}__mpp{mpp:.2f}"
                expected_pairs[pair_id] = (
                    "tile64_vs16",
                    f"marker7__{encoder}__s{seed}__t16__mpp{mpp:.2f}",
                    f"marker7__{encoder}__s{seed}__t64__mpp{mpp:.2f}",
                )
    if set(deltas["pair_id"].astype(str)) != set(expected_pairs):
        raise ValueError("R2 paired deltas: exact prespecified 65-pair identity set does not reconcile")
    if deltas.duplicated(["contrast", "cell_id_a", "cell_id_b"]).any():
        raise ValueError("R2 paired deltas: duplicate contrast/cell pair")
    for row in deltas[["pair_id", "contrast", "cell_id_a", "cell_id_b"]].itertuples(index=False):
        if (row.contrast, row.cell_id_a, row.cell_id_b) != expected_pairs[row.pair_id]:
            raise ValueError(f"R2 paired deltas: canonical cells do not match {row.pair_id}")
    if not deltas["direction_status"].astype(str).eq("preserved").all():
        raise ValueError("R2 paired deltas: all audited directions must be preserved")
    if not set(deltas["cell_id_a"]).issubset(expected_cells) or not set(
        deltas["cell_id_b"]
    ).issubset(expected_cells):
        raise ValueError("R2 paired deltas: cell references do not reconcile to R2 cells")
    _finite_values(
        deltas,
        (
            "raw_metric_a", "raw_metric_b", "raw_delta_b_minus_a",
            "common498_metric_a", "common498_metric_b", "common498_delta_b_minus_a",
        ),
        "R2 paired deltas",
    )
    raw_delta = deltas["raw_metric_b"] - deltas["raw_metric_a"]
    common_delta = deltas["common498_metric_b"] - deltas["common498_metric_a"]
    if not np.allclose(
        raw_delta.to_numpy(dtype=float), deltas["raw_delta_b_minus_a"].to_numpy(dtype=float),
        atol=5e-15, rtol=0,
    ):
        raise ValueError("R2 paired deltas: raw delta arithmetic does not reconcile")
    if not np.allclose(
        common_delta.to_numpy(dtype=float),
        deltas["common498_delta_b_minus_a"].to_numpy(dtype=float),
        atol=5e-15, rtol=0,
    ):
        raise ValueError("R2 paired deltas: common-498 delta arithmetic does not reconcile")
    cell_lookup = cells.set_index("cell_id")
    for side in ("a", "b"):
        cell_ids = deltas[f"cell_id_{side}"]
        expected_raw = cell_ids.map(cell_lookup["saved_raw_c_index"])
        expected_common = cell_ids.map(cell_lookup["common_source_c_index"])
        if expected_raw.isna().any() or expected_common.isna().any():
            raise ValueError("R2 paired deltas: referenced cell is absent")
        if not np.allclose(
            expected_raw.to_numpy(dtype=float),
            deltas[f"raw_metric_{side}"].to_numpy(dtype=float),
            atol=5e-15,
            rtol=0,
        ):
            raise ValueError(f"R2 paired deltas: raw metric {side} does not match referenced cell")
        if not np.allclose(
            expected_common.to_numpy(dtype=float),
            deltas[f"common498_metric_{side}"].to_numpy(dtype=float),
            atol=5e-15,
            rtol=0,
        ):
            raise ValueError(
                f"R2 paired deltas: common-498 metric {side} does not match referenced cell"
            )
    raw_direction = np.where(raw_delta > 0, "positive", np.where(raw_delta < 0, "negative", "tie"))
    common_direction = np.where(
        common_delta > 0, "positive", np.where(common_delta < 0, "negative", "tie")
    )
    if not np.array_equal(raw_direction, deltas["raw_direction"].astype(str).to_numpy()):
        raise ValueError("R2 paired deltas: raw direction does not match delta sign")
    if not np.array_equal(
        common_direction, deltas["common498_direction"].astype(str).to_numpy()
    ):
        raise ValueError("R2 paired deltas: common-498 direction does not match delta sign")
    calculated_status = np.where(raw_direction == common_direction, "preserved", "reversed")
    if not np.array_equal(calculated_status, deltas["direction_status"].astype(str).to_numpy()):
        raise ValueError("R2 paired deltas: direction status does not reconcile")
    raw_crossing = null_relation_crossing(
        deltas["raw_metric_a"], deltas["raw_metric_b"], null_value=0.5
    )
    common_crossing = null_relation_crossing(
        deltas["common498_metric_a"], deltas["common498_metric_b"], null_value=0.5
    )
    if not np.array_equal(
        raw_crossing.to_numpy(),
        _bool_values(deltas, "raw_null_crossing", "R2 paired deltas").to_numpy(),
    ):
        raise ValueError("R2 paired deltas: raw null-crossing flag does not reconcile")
    if not np.array_equal(
        common_crossing.to_numpy(),
        _bool_values(deltas, "common498_null_crossing", "R2 paired deltas").to_numpy(),
    ):
        raise ValueError("R2 paired deltas: common-498 null-crossing flag does not reconcile")
    raw_tie = deltas["raw_metric_a"].eq(deltas["raw_metric_b"])
    common_tie = deltas["common498_metric_a"].eq(deltas["common498_metric_b"])
    if not np.array_equal(
        raw_tie.to_numpy(),
        _bool_values(deltas, "raw_exact_tie", "R2 paired deltas").to_numpy(),
    ):
        raise ValueError("R2 paired deltas: raw exact-tie flag does not reconcile")
    if not np.array_equal(
        common_tie.to_numpy(),
        _bool_values(deltas, "common498_exact_tie", "R2 paired deltas").to_numpy(),
    ):
        raise ValueError("R2 paired deltas: common-498 exact-tie flag does not reconcile")

    membership = _read_csv_contract(
        membership_csv,
        label="R2 membership",
        expected_rows=10_040,
        required_columns=(
            "source_configuration_id", "encoder", "sampling_seed", "target_mpp",
            "source_case_id", "retained_in_config", "source_row_index",
            "common_source_member", "common_row_index", "event", "follow_up_years",
            "outcome_consistency_status",
        ),
        unique_columns=("source_configuration_id", "source_case_id"),
    )
    actual_configs = set(membership["source_configuration_id"].astype(str))
    if actual_configs != set(expected_source_configs):
        raise ValueError("R2 membership: exact 20 source configurations do not reconcile")
    if not membership.groupby("source_configuration_id").size().eq(502).all():
        raise ValueError("R2 membership: every source configuration must enumerate 502 union IDs")
    common = _bool_values(membership, "common_source_member", "R2 membership")
    retained = _bool_values(membership, "retained_in_config", "R2 membership")
    _finite_values(membership, ("event", "follow_up_years"), "R2 membership")
    events = pd.to_numeric(membership["event"])
    if not events.isin({0, 1}).all():
        raise ValueError("R2 membership: source events must be binary")
    follow_up = pd.to_numeric(membership["follow_up_years"])
    if not follow_up.gt(0).all():
        raise ValueError("R2 membership: follow-up years must be positive")
    expected_status = np.where(retained, "consistent", "not_retained")
    if not np.array_equal(
        expected_status, membership["outcome_consistency_status"].astype(str).to_numpy()
    ):
        raise ValueError("R2 membership: outcome consistency status does not match retention")
    if membership.groupby("source_case_id")["event"].nunique().max() != 1 or membership.groupby(
        "source_case_id"
    )["follow_up_years"].nunique().max() != 1:
        raise ValueError("R2 membership: source outcomes differ across configurations")

    canonical_union: list[str] | None = None
    canonical_common_order: list[str] | None = None
    retained_counts: dict[str, int] = {}
    for config_id, group in membership.groupby("source_configuration_id", sort=False):
        expected_encoder, expected_seed, expected_mpp = expected_source_configs[str(config_id)]
        if (
            not group["encoder"].astype(str).eq(expected_encoder).all()
            or not pd.to_numeric(group["sampling_seed"], errors="coerce").eq(expected_seed).all()
            or not np.allclose(
                pd.to_numeric(group["target_mpp"], errors="coerce"),
                expected_mpp,
                atol=1e-12,
                rtol=0,
            )
        ):
            raise ValueError(f"R2 membership: axes do not match {config_id}")
        union_ids = group["source_case_id"].astype(str).tolist()
        if union_ids != sorted(union_ids) or id_list_sha256(union_ids) != (
            "d1f366c5cbb682454711ab25743cf8470dc0c17666a737f82bf8a8ac295b43b6"
        ):
            raise ValueError(f"R2 membership: union identity/order does not match {config_id}")
        if canonical_union is None:
            canonical_union = union_ids
        elif union_ids != canonical_union:
            raise ValueError("R2 membership: union identities differ across configurations")

        group_retained = retained.loc[group.index]
        group_common = common.loc[group.index]
        retained_group = group.loc[group_retained]
        common_group = group.loc[group_common]
        retained_counts[str(config_id)] = len(retained_group)
        if id_list_sha256(common_group["source_case_id"].astype(str)) != (
            "3bf830ff8e7cdc0701c026a4d1425207661ce78e56812f532a5763e4b6eef32a"
        ):
            raise ValueError(f"R2 membership: common identity hash does not match {config_id}")

        source_index = pd.to_numeric(retained_group["source_row_index"], errors="coerce")
        if source_index.isna().any() or sorted(source_index.astype(int).tolist()) != list(
            range(len(retained_group))
        ) or not np.equal(source_index, np.floor(source_index)).all():
            raise ValueError(f"R2 membership: source row indices do not reconcile for {config_id}")
        if pd.to_numeric(
            group.loc[~group_retained, "source_row_index"], errors="coerce"
        ).notna().any():
            raise ValueError(f"R2 membership: non-retained row has source index for {config_id}")

        common_index = pd.to_numeric(common_group["common_row_index"], errors="coerce")
        if common_index.isna().any() or not np.equal(common_index, np.floor(common_index)).all():
            raise ValueError(f"R2 membership: common row indices are invalid for {config_id}")
        ordered_common = common_group.assign(
            _source_index=pd.to_numeric(common_group["source_row_index"], errors="raise"),
            _common_index=common_index,
        ).sort_values("_source_index")
        if ordered_common["_common_index"].astype(int).tolist() != list(range(498)):
            raise ValueError(f"R2 membership: common row order is not preserved for {config_id}")
        common_order = ordered_common["source_case_id"].astype(str).tolist()
        if canonical_common_order is None:
            canonical_common_order = common_order
        elif common_order != canonical_common_order:
            raise ValueError("R2 membership: filtered common order differs across configurations")
        if pd.to_numeric(
            group.loc[~group_common, "common_row_index"], errors="coerce"
        ).notna().any():
            raise ValueError(f"R2 membership: non-common row has common index for {config_id}")

    cell_original_counts = cells.groupby("source_configuration_id")[
        "n_original_source_patients"
    ].agg(["nunique", "first"])
    if not cell_original_counts["nunique"].eq(1).all() or (
        cell_original_counts["first"].astype(int).to_dict() != retained_counts
    ):
        raise ValueError("R2 cells/membership: original source counts do not reconcile")
    if int(common.sum()) != 9_960 or int(retained.sum()) != 9_992:
        raise ValueError("R2 membership: audited common/retained membership counts do not reconcile")
    if not retained[common].all():
        raise ValueError("R2 membership: every common-source row must be retained")
    common_rows = membership.loc[common, ["source_case_id", "event"]]
    if common_rows["source_case_id"].nunique() != 498:
        raise ValueError("R2 membership: expected exactly 498 common source IDs")
    common_outcomes = common_rows.drop_duplicates()
    if len(common_outcomes) != 498 or int(pd.to_numeric(common_outcomes["event"]).sum()) != 85:
        raise ValueError("R2 membership: common-source outcomes or 85-event count do not reconcile")

    return {
        "cells": cells,
        "deltas": deltas,
        "membership": membership,
        "shift_min": float(cells["common_minus_saved_raw"].min()),
        "shift_max": float(cells["common_minus_saved_raw"].max()),
        "contrast_counts": expected_contrast_counts,
    }


def load_r5_sources(
    ar_csv: Path,
    metadata_csv: Path,
    spop_csv: Path,
    power_csv: Path,
    predictions_csv: Path,
    manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_spop_evidence_manifest.csv",
) -> dict[str, object]:
    _validate_manifest_bound_outputs(
        manifest_csv,
        (
            Path(ar_csv), Path(metadata_csv), Path(spop_csv), Path(power_csv),
            Path(predictions_csv),
        ),
        label="R5 frozen outputs",
    )
    ar = _read_csv_contract(
        ar_csv,
        label="R5 AR sites",
        expected_rows=22,
        required_columns=(
            "site", "n_slides", "n_patients", "forest_eligible", "ar_median",
            "loo_rho", "loo_ci_low", "loo_ci_high", "loo_metric_unit",
            "bootstrap_unit", "n_bootstrap_requested", "n_bootstrap_valid",
            "n_bootstrap_undefined", "bootstrap_undefined_fraction",
        ),
        unique_columns=("site",),
    )
    expected_all_sites = {
        "2A", "CH", "EJ", "FC", "G9", "H9", "HC", "HI", "J4", "KK", "M7",
        "QU", "SU", "TK", "V1", "VP", "WW", "XA", "XJ", "XQ", "Y6", "YL",
    }
    if set(ar["site"].astype(str)) != expected_all_sites:
        raise ValueError("R5 AR sites: exact 22-site identity set does not reconcile")
    forest = ar.loc[_bool_values(ar, "forest_eligible", "R5 AR sites")].copy()
    expected_sites = {"CH", "EJ", "G9", "HC", "KK", "YL"}
    if set(forest["site"]) != expected_sites:
        raise ValueError("R5 AR sites: expected the audited six-site forest frame")
    _finite_values(
        forest,
        (
            "n_slides", "n_patients", "ar_median", "loo_rho", "loo_ci_low", "loo_ci_high",
            "n_bootstrap_requested", "n_bootstrap_valid", "n_bootstrap_undefined",
            "bootstrap_undefined_fraction",
        ),
        "R5 AR forest",
    )
    if int(forest["n_slides"].sum()) != 224 or int(forest["n_patients"].sum()) != 209:
        raise ValueError("R5 AR sites: six-site frame must contain 224 slides and 209 patients")
    if not ((forest["loo_ci_low"] <= 0) & (forest["loo_ci_high"] >= 0)).all():
        raise ValueError("R5 AR sites: all six audited LOO intervals must include zero")
    if not forest["loo_metric_unit"].astype(str).eq("slide").all():
        raise ValueError("R5 AR sites: LOO effect metric must be labeled slide-level")
    if not forest["bootstrap_unit"].astype(str).eq("patient_cluster").all():
        raise ValueError("R5 AR sites: LOO intervals must be labeled patient-cluster bootstrap")
    expected_ar = {
        "CH": (-0.1284584980237154, -0.561442533263868, 0.3503727619388085),
        "EJ": (0.1271205014820309, -0.1207242603819796, 0.3625409500409496),
        "G9": (0.1953601953601953, -0.2575173715982134, 0.59829033086366),
        "HC": (0.2173913043478261, -0.0718141016279708, 0.4708831666253087),
        "KK": (0.2653493309180169, -0.0866922957115325, 0.5577740895780862),
        "YL": (0.2269656916704352, -0.1354546423947803, 0.5400530375753029),
    }
    forest_by_site = forest.set_index("site")
    for site, expected_values in expected_ar.items():
        actual_values = forest_by_site.loc[site, ["loo_rho", "loo_ci_low", "loo_ci_high"]].to_numpy(
            dtype=float
        )
        if not np.allclose(actual_values, expected_values, atol=5e-15, rtol=0):
            raise ValueError(f"R5 AR sites: {site} LOO estimate/interval does not reconcile")
    if not (
        pd.to_numeric(forest["n_bootstrap_requested"]).eq(2000).all()
        and pd.to_numeric(forest["n_bootstrap_valid"]).eq(2000).all()
        and pd.to_numeric(forest["n_bootstrap_undefined"]).eq(0).all()
        and pd.to_numeric(forest["bootstrap_undefined_fraction"]).eq(0).all()
    ):
        raise ValueError("R5 AR sites: six-site bootstrap accounting must be 2000/2000/0/0")

    metadata = _read_csv_contract(
        metadata_csv,
        label="R5 slide metadata",
        expected_rows=300,
        required_columns=(
            "file_name", "case_id", "site", "gdc_file_id", "header_read_status",
            "scanscope_id_available", "explicit_stain_field_available",
            "stain_metadata_status", "canonical_header_sha256",
        ),
        unique_columns=("file_name",),
    )
    if not metadata["header_read_status"].astype(str).eq("complete").all():
        raise ValueError("R5 slide metadata: all 300 page-0 header reads must be complete")
    if set(metadata["site"].astype(str)) != expected_all_sites:
        raise ValueError("R5 slide metadata: exact 22-site identity set does not reconcile")
    if not metadata["canonical_header_sha256"].astype(str).str.fullmatch(
        r"[0-9a-f]{64}"
    ).all():
        raise ValueError("R5 slide metadata: canonical page-0 hashes must be lowercase SHA256")
    if metadata["gdc_file_id"].isna().any() or metadata["gdc_file_id"].duplicated().any():
        raise ValueError("R5 slide metadata: GDC file IDs must be complete and unique")
    scanscope = _bool_values(metadata, "scanscope_id_available", "R5 slide metadata")
    stain = _bool_values(metadata, "explicit_stain_field_available", "R5 slide metadata")
    if int(scanscope.sum()) != 280 or int(stain.sum()) != 0:
        raise ValueError("R5 slide metadata: expected ScanScope raw IDs 280/300 and stain fields 0/300")
    if not metadata["stain_metadata_status"].astype(str).eq("not_available").all():
        raise ValueError("R5 slide metadata: unavailable stain metadata must remain explicit")

    spop = _read_csv_contract(
        spop_csv,
        label="R5 SPOP sites",
        expected_rows=22,
        required_columns=(
            "site", "n_slides", "n_patients", "large_site_eligible",
            "n_positive_patients", "n_negative_patients", "historical_slide_reportable",
            "patient_metric_defined", "patient_auroc",
            "n_bootstrap_requested", "n_bootstrap_valid", "n_bootstrap_undefined",
            "bootstrap_undefined_fraction", "patient_ci_low", "patient_ci_high", "status_reason",
            "small_class_warning", "reconstruction_status",
        ),
        unique_columns=("site",),
    )
    if set(spop["site"].astype(str)) != expected_all_sites:
        raise ValueError("R5 SPOP sites: exact 22-site identity set does not reconcile")
    large = spop.loc[_bool_values(spop, "large_site_eligible", "R5 SPOP sites")].set_index("site")
    if set(large.index) != expected_sites:
        raise ValueError("R5 SPOP sites: expected the audited six-site frame")
    reportable = _bool_values(large, "historical_slide_reportable", "R5 SPOP sites")
    if set(large.index[reportable]) != {"EJ", "KK", "YL"}:
        raise ValueError("R5 SPOP sites: historical slide-reportability rule does not reconcile")
    metric_defined = _bool_values(large, "patient_metric_defined", "R5 SPOP sites")
    if set(large.index[metric_defined]) != {"EJ", "G9", "HC", "KK", "YL"}:
        raise ValueError("R5 SPOP sites: expected CH single-class undefined and five defined sites")
    expected_auc = {"EJ": 0.61263736, "G9": 0.7, "HC": 0.75757576, "KK": 0.57333333, "YL": 0.625}
    expected_ci = {
        "EJ": (0.41823756432246995, 0.7982894736842103),
        "G9": (0.42307692307692313, 0.9230769230769231),
        "HC": (0.5, 0.9393939393939393),
        "KK": (0.27291666666666675, 0.8401944444444446),
        "YL": (0.2823529411764706, 1.0),
    }
    expected_undefined = {"CH": 2000, "EJ": 0, "G9": 234, "HC": 92, "KK": 2, "YL": 31}
    for site, expected in expected_auc.items():
        if not np.isclose(float(large.loc[site, "patient_auroc"]), expected, atol=5e-8, rtol=0):
            raise ValueError(f"R5 SPOP sites: {site} patient AUROC does not reconcile")
        low, high = float(large.loc[site, "patient_ci_low"]), float(large.loc[site, "patient_ci_high"])
        if not np.allclose((low, high), expected_ci[site], atol=5e-15, rtol=0):
            raise ValueError(f"R5 SPOP sites: {site} patient interval does not reconcile")
        if not low <= 0.5 <= high:
            raise ValueError(f"R5 SPOP sites: {site} interval must include or touch 0.5")
    if not pd.isna(large.loc["CH", "patient_auroc"]):
        raise ValueError("R5 SPOP sites: CH patient AUROC must remain undefined")
    if not pd.isna(large.loc["CH", "patient_ci_low"]) or not pd.isna(
        large.loc["CH", "patient_ci_high"]
    ):
        raise ValueError("R5 SPOP sites: CH interval must remain undefined")
    if str(large.loc["CH", "status_reason"]) != "undefined_single_class" or str(
        large.loc["CH", "reconstruction_status"]
    ) != "undefined_single_class":
        raise ValueError("R5 SPOP sites: CH must remain explicitly single-class undefined")
    expected_site_status = {
        "EJ": "complete", "G9": "complete_with_small_class_warning",
        "HC": "complete_with_small_class_warning", "KK": "complete",
        "YL": "complete_with_small_class_warning",
    }
    expected_small_class_warning = {
        "CH": "single_patient_class", "EJ": "none",
        "G9": "min_patient_class_lt_5", "HC": "min_patient_class_lt_5",
        "KK": "none", "YL": "min_patient_class_lt_5",
    }
    for site, expected_warning in expected_small_class_warning.items():
        if str(large.loc[site, "small_class_warning"]) != expected_warning:
            raise ValueError(f"R5 SPOP sites: {site} small-class warning does not reconcile")
    for site, expected_status in expected_site_status.items():
        if str(large.loc[site, "status_reason"]) != expected_status or str(
            large.loc[site, "reconstruction_status"]
        ) != expected_status:
            raise ValueError(f"R5 SPOP sites: {site} status does not reconcile")
    for site, expected in expected_undefined.items():
        if int(large.loc[site, "n_bootstrap_requested"]) != 2000:
            raise ValueError(f"R5 SPOP sites: {site} must retain 2,000 requested bootstrap draws")
        if int(large.loc[site, "n_bootstrap_undefined"]) != expected:
            raise ValueError(f"R5 SPOP sites: {site} undefined bootstrap count does not reconcile")
        valid = int(large.loc[site, "n_bootstrap_valid"])
        if valid + expected != 2000:
            raise ValueError(f"R5 SPOP sites: {site} valid/undefined draws do not sum to 2,000")
        fraction = float(large.loc[site, "bootstrap_undefined_fraction"])
        if not np.isclose(fraction, expected / 2000, atol=1e-15, rtol=0):
            raise ValueError(f"R5 SPOP sites: {site} undefined bootstrap fraction does not reconcile")

    metadata_site_counts = metadata.groupby("site").agg(
        n_slides=("file_name", "size"), n_patients=("case_id", "nunique")
    ).sort_index()
    for label, summary in (("AR", ar), ("SPOP", spop)):
        reported = summary.set_index("site")[["n_slides", "n_patients"]].sort_index().astype(int)
        if not reported.equals(metadata_site_counts.astype(int)):
            raise ValueError(f"R5 {label}/metadata: 22-site slide/patient counts do not reconcile")

    power = _read_csv_contract(
        power_csv,
        label="R5 SPOP power",
        expected_rows=2,
        required_columns=(
            "cohort", "analysis_unit", "n_positive", "n_negative", "null_auroc", "alpha",
            "alternative", "target_power", "minimum_detectable_auroc", "variance_method",
            "approximation_scope", "limitation",
        ),
        unique_columns=("target_power",),
    )
    _finite_values(
        power,
        (
            "n_positive", "n_negative", "null_auroc", "alpha", "target_power",
            "minimum_detectable_auroc",
        ),
        "R5 SPOP power",
    )
    by_power = power.set_index("target_power")
    expected_mde = {0.8: 0.6613666946979635, 0.9: 0.6847459836958563}
    if set(round(float(value), 10) for value in by_power.index) != {0.8, 0.9}:
        raise ValueError("R5 SPOP power: expected 80% and 90% target-power rows")
    for target, expected in expected_mde.items():
        row = by_power.loc[target]
        if (
            str(row["cohort"]) != "TCGA-PRAD"
            or str(row["analysis_unit"]) != "patient"
            or not np.isclose(float(row["null_auroc"]), 0.5, atol=1e-15, rtol=0)
            or not np.isclose(float(row["alpha"]), 0.05, atol=1e-15, rtol=0)
            or str(row["alternative"]) != "two_sided"
            or str(row["variance_method"]) != "Hanley-McNeil AUROC variance"
        ):
            raise ValueError("R5 SPOP power: cohort/unit/null/alpha/method contract changed")
        if int(row["n_positive"]) != 29 or int(row["n_negative"]) != 244:
            raise ValueError("R5 SPOP power: patient class counts must be 29 positive/244 negative")
        if not np.isclose(float(row["minimum_detectable_auroc"]), expected, atol=1e-14, rtol=0):
            raise ValueError(f"R5 SPOP power: {target:.0%} MDE does not reconcile")
        if str(row["approximation_scope"]) != "fixed_score_normal_approximation":
            raise ValueError("R5 SPOP power: approximation must remain labeled fixed-score")
        if "not an effect-exclusion bound" not in str(row["limitation"]):
            raise ValueError("R5 SPOP power: effect-exclusion limitation is missing")

    predictions = _read_csv_contract(
        predictions_csv,
        label="R5 SPOP predictions",
        expected_rows=433,
        required_columns=(
            "record_level", "held_out_site", "file_name", "case_id", "true_label",
            "predicted_probability", "n_component_slides", "reconstruction_status",
        ),
        unique_columns=("record_level", "held_out_site", "case_id", "predicted_probability"),
    )
    if predictions.groupby("record_level").size().to_dict() != {"patient": 209, "slide": 224}:
        raise ValueError("R5 SPOP predictions: expected 224 slide and 209 patient predictions")
    _finite_values(
        predictions,
        ("true_label", "predicted_probability", "n_component_slides"),
        "R5 SPOP predictions",
    )
    labels = pd.to_numeric(predictions["true_label"])
    probabilities = pd.to_numeric(predictions["predicted_probability"])
    if not labels.isin({0, 1}).all():
        raise ValueError("R5 SPOP predictions: true labels must be binary")
    if not probabilities.between(0, 1, inclusive="both").all():
        raise ValueError("R5 SPOP predictions: probabilities must lie in [0, 1]")
    expected_prediction_counts = {
        ("slide", "CH"): 23, ("slide", "EJ"): 59, ("slide", "G9"): 27,
        ("slide", "HC"): 47, ("slide", "KK"): 31, ("slide", "YL"): 37,
        ("patient", "CH"): 23, ("patient", "EJ"): 59, ("patient", "G9"): 27,
        ("patient", "HC"): 47, ("patient", "KK"): 31, ("patient", "YL"): 22,
    }
    if predictions.groupby(["record_level", "held_out_site"]).size().to_dict() != expected_prediction_counts:
        raise ValueError("R5 SPOP predictions: held-out site/record-level counts do not reconcile")
    slide_predictions = predictions.loc[predictions["record_level"].eq("slide")].copy()
    patient_predictions = predictions.loc[predictions["record_level"].eq("patient")].copy()
    expected_slide_metadata = metadata.loc[metadata["site"].isin(expected_sites), [
        "file_name", "case_id", "site",
    ]]
    if slide_predictions["file_name"].isna().any() or slide_predictions["file_name"].duplicated().any():
        raise ValueError("R5 SPOP predictions: slide filenames must be complete and unique")
    linked = slide_predictions.merge(
        expected_slide_metadata,
        on="file_name",
        how="outer",
        indicator=True,
        suffixes=("_prediction", "_metadata"),
    )
    if not linked["_merge"].eq("both").all() or not (
        linked["held_out_site"].astype(str).eq(linked["site"].astype(str)).all()
        and linked["case_id_prediction"].astype(str).eq(linked["case_id_metadata"].astype(str)).all()
    ):
        raise ValueError("R5 SPOP predictions: slide keys do not reconcile to page-0 metadata")
    if not pd.to_numeric(slide_predictions["n_component_slides"]).eq(1).all():
        raise ValueError("R5 SPOP predictions: slide rows must have one component slide")

    slide_aggregation = slide_predictions.groupby(["held_out_site", "case_id"], sort=True).agg(
        true_label=("true_label", "first"),
        n_true_labels=("true_label", "nunique"),
        predicted_probability=("predicted_probability", "mean"),
        n_component_slides=("file_name", "size"),
    )
    patient_keyed = patient_predictions.set_index(["held_out_site", "case_id"]).sort_index()
    if patient_keyed.index.has_duplicates or not patient_keyed.index.equals(slide_aggregation.index):
        raise ValueError("R5 SPOP predictions: patient keys do not match aggregated slide keys")
    if not slide_aggregation["n_true_labels"].eq(1).all():
        raise ValueError("R5 SPOP predictions: slide labels differ within a patient")
    if not (
        pd.to_numeric(patient_keyed["true_label"]).eq(slide_aggregation["true_label"]).all()
        and pd.to_numeric(patient_keyed["n_component_slides"]).eq(
            slide_aggregation["n_component_slides"]
        ).all()
        and np.allclose(
            pd.to_numeric(patient_keyed["predicted_probability"]),
            slide_aggregation["predicted_probability"],
            atol=1e-7,
            rtol=0,
        )
    ):
        raise ValueError("R5 SPOP predictions: patient aggregation does not reconcile")
    expected_reconstruction_status = {
        "slide": "reconstructed_from_frozen_conch_embedding",
        "patient": "mean_slide_probability_patient_aggregation",
    }
    for record_level, expected_status in expected_reconstruction_status.items():
        statuses = set(
            predictions.loc[
                predictions["record_level"].eq(record_level), "reconstruction_status"
            ].astype(str)
        )
        if statuses != {expected_status}:
            raise ValueError(
                f"R5 SPOP predictions: {record_level} reconstruction status does not reconcile"
            )
    for site in sorted(expected_sites):
        rows = patient_predictions.loc[patient_predictions["held_out_site"].eq(site)]
        summary_row = large.loc[site]
        n_positive = int(rows["true_label"].sum())
        n_negative = int(len(rows) - n_positive)
        if n_positive != int(summary_row["n_positive_patients"]) or n_negative != int(
            summary_row["n_negative_patients"]
        ):
            raise ValueError(f"R5 SPOP predictions: {site} class counts do not match summary")
        auc = _binary_auc(rows["true_label"], rows["predicted_probability"])
        summary_auc = float(summary_row["patient_auroc"])
        if site == "CH":
            if not np.isnan(auc) or not np.isnan(summary_auc):
                raise ValueError("R5 SPOP predictions: CH AUROC must be undefined in both sources")
        elif not np.isclose(auc, summary_auc, atol=5e-15, rtol=0):
            raise ValueError(f"R5 SPOP predictions: {site} AUROC does not match site summary")

    return {
        "ar": ar,
        "metadata": metadata,
        "spop": spop,
        "power": power,
        "predictions": predictions,
        "ar_median_min": float(forest["ar_median"].min()),
        "ar_median_max": float(forest["ar_median"].max()),
        "spop_auc": expected_auc,
        "undefined": expected_undefined,
        "mde": expected_mde,
    }


def load_stability_sources(summary_csv: Path, contrast_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    # The manuscript table and Figure 9 share one fail-closed semantic contract for the
    # complete 72-configuration/390-contrast frozen design.
    return validate_grid(pd.read_csv(summary_csv)), validate_contrasts(pd.read_csv(contrast_csv))


def _marker_numbers(summary: pd.DataFrame, contrasts: pd.DataFrame, marker: str) -> dict:
    rows = summary[summary["marker"] == marker]
    marker_contrasts = contrasts[contrasts["marker"] == marker]
    crossing_counts = marker_contrasts.groupby("contrast")["null_crossing"].apply(
        lambda values: int(values.astype(bool).sum())
    )
    return {
        "metric": str(rows["metric"].iloc[0]),
        "observed_min": float(rows["min"].min()),
        "observed_max": float(rows["max"].max()),
        "mean_min": float(rows["mean"].min()),
        "mean_max": float(rows["mean"].max()),
        "chance": int(rows["n_chance_or_worse"].sum()),
        "chance_denominator": int(rows["n_seeds"].sum()),
        "straddles": int(rows["seed_null_straddle"].astype(bool).sum()),
        "straddle_denominator": int(len(rows)),
        "native_crossings": int(crossing_counts.get("native_vs_1.76", 0)),
        "native_denominator": int((marker_contrasts["contrast"] == "native_vs_1.76").sum()),
        "shared_crossings": int(crossing_counts.get("virchow_vs_conch_at_1.76", 0)),
        "shared_denominator": int((marker_contrasts["contrast"] == "virchow_vs_conch_at_1.76").sum()),
    }


def build_claim_evidence(
    output_dir: Path = PAPER,
    stability_summary_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",
    stability_contrast_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
    stability_qc_json: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json",
    r2_cells_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv",
    r2_deltas_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv",
    r2_membership_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_membership_manifest.csv",
    r2_manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_run_manifest.csv",
    r5_ar_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv",
    r5_metadata_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv",
    r5_spop_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv",
    r5_power_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv",
    r5_predictions_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_predictions.csv",
    r5_manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_spop_evidence_manifest.csv",
    r3_mapping_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv",
    r3_concordance_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv",
    r3_performance_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv",
    r3_manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_run_manifest.csv",
    r4_summary_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv",
    r4_deltas_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv",
    r4_manifest_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_run_manifest.csv",
    confounder_nested_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv",
    confounder_refit_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_summary.csv",
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, contrasts = load_stability_sources(stability_summary_csv, stability_contrast_csv)
    qc = json.loads(Path(stability_qc_json).read_text(encoding="utf-8"))
    r2 = load_r2_sources(
        r2_cells_csv, r2_deltas_csv, r2_membership_csv, manifest_csv=r2_manifest_csv
    )
    r5 = load_r5_sources(
        r5_ar_csv, r5_metadata_csv, r5_spop_csv, r5_power_csv, r5_predictions_csv,
        manifest_csv=r5_manifest_csv,
    )
    r3 = load_r3_sources(
        r3_mapping_csv, r3_concordance_csv, r3_performance_csv, manifest_csv=r3_manifest_csv
    )
    r4 = load_r4_sources(r4_summary_csv, r4_deltas_csv, manifest_csv=r4_manifest_csv)
    confounder = _read_csv_contract(
        confounder_nested_csv,
        label="claim confounder summary",
        expected_rows=6,
        required_columns=(
            "marker", "analysis", "scope", "n", "metric", "delta", "ci_low", "ci_high",
        ),
        unique_columns=("marker", "analysis", "scope"),
    )
    refit = _read_csv_contract(
        confounder_refit_csv,
        label="claim refit permutation summary",
        expected_rows=4,
        required_columns=(
            "marker", "analysis", "metric", "observed_delta", "n_requested", "n_valid",
            "permutation_p_one_sided",
        ),
        unique_columns=("marker", "analysis"),
    )
    pten_rows = confounder.loc[
        confounder["marker"].astype(str).eq("marker4_pten")
        & confounder["analysis"].astype(str).eq("grade_only")
        & confounder["scope"].astype(str).eq("patient")
    ]
    pten_refit_rows = refit.loc[
        refit["marker"].astype(str).eq("marker4_pten")
        & refit["analysis"].astype(str).eq("grade_only")
    ]
    if len(pten_rows) != 1 or len(pten_refit_rows) != 1:
        raise ValueError("claim PTEN confounder/refit rows do not reconcile")
    pten_row = pten_rows.iloc[0]
    pten_refit = pten_refit_rows.iloc[0]
    _finite_values(
        pten_rows, ("delta", "ci_low", "ci_high"), "claim PTEN confounder summary"
    )
    _finite_values(
        pten_refit_rows, ("observed_delta", "permutation_p_one_sided"),
        "claim PTEN refit summary",
    )
    if not np.isclose(
        float(pten_row["delta"]), float(pten_refit["observed_delta"]), atol=5e-15, rtol=0
    ):
        raise ValueError("claim PTEN nested and refit observed deltas do not reconcile")
    numbers = {marker: _marker_numbers(summary, contrasts, marker) for marker in STABILITY_MARKERS}
    spop = numbers["spop"]
    ar = numbers["ar"]
    marker7 = numbers["marker7"]
    marker7_summary = summary[summary["marker"] == "marker7"]
    marker7_conch = marker7_summary[marker7_summary["encoder"] == "CONCH"]
    marker7_virchow = marker7_summary[marker7_summary["encoder"] == "Virchow"]
    spop_sites = r5["spop"].loc[
        _bool_values(r5["spop"], "large_site_eligible", "claim SPOP sites")
    ].sort_values("site")
    spop_site_parts = []
    for site_row in spop_sites.itertuples(index=False):
        if bool(site_row.patient_metric_defined):
            spop_site_parts.append(f"{site_row.site} {float(site_row.patient_auroc):.3f}")
        else:
            spop_site_parts.append(f"{site_row.site} undefined (single class)")
    spop_undefined = "/".join(
        str(int(value)) for value in spop_sites["n_bootstrap_undefined"]
    )
    power_rows = r5["power"].sort_values("target_power")
    mde_parts = " and ".join(
        f"{float(row.minimum_detectable_auroc):.3f} ({float(row.target_power):.0%})"
        for row in power_rows.itertuples(index=False)
    )
    ar_forest = r5["ar"].loc[
        _bool_values(r5["ar"], "forest_eligible", "claim AR sites")
    ]
    ar_slides = int(pd.to_numeric(ar_forest["n_slides"]).sum())
    ar_patients = int(pd.to_numeric(ar_forest["n_patients"]).sum())
    ar_zero_intervals = int(
        ((pd.to_numeric(ar_forest["loo_ci_low"]) <= 0)
         & (pd.to_numeric(ar_forest["loo_ci_high"]) >= 0)).sum()
    )
    ar_zero_interval_label = {6: "six"}.get(ar_zero_intervals, str(ar_zero_intervals))
    scanscope_count = int(
        _bool_values(r5["metadata"], "scanscope_id_available", "claim AR metadata").sum()
    )
    stain_count = int(
        _bool_values(r5["metadata"], "explicit_stain_field_available", "claim AR metadata").sum()
    )
    metadata_count = len(r5["metadata"])
    r2_first = r2["cells"].iloc[0]
    raw_common_preserved = int(
        (~_bool_values(r2["cells"], "raw_common_null_crossing", "claim R2 cells")).sum()
    )
    r2_direction_parts = []
    for contrast, count in r2["contrast_counts"].items():
        rows_for_contrast = r2["deltas"].loc[r2["deltas"]["contrast"].eq(contrast)]
        preserved = int(rows_for_contrast["direction_status"].astype(str).eq("preserved").sum())
        label = {
            "native_vs_1.76": "scale",
            "tile64_vs16": "tile",
            "virchow_vs_conch_at_1.76": "encoder",
        }[contrast]
        r2_direction_parts.append(f"{preserved}/{count} {label}")
    r4_n_patients = int(pd.to_numeric(r4["deltas"]["n_patients"]).iloc[0])
    columns = [
        "claim_id", "claim", "hierarchy", "marker", "cohort", "encoder", "endpoint",
        "validation_type", "effect_summary", "source_csv", "source_script",
        "manuscript_location", "reliability_tier", "limitation", "mr_v1_item", "status",
    ]
    rows = [
        ["C01", "Qualification framework separates transportable, context-sensitive, and unsupported signals",
         "primary", "markers 1-6", "multi-cohort", "CONCH+Virchow", "marker-specific",
         "patient-level qualification gates", "17-test BH-FDR family and five-tier map",
         "resources/projects/prostate_biomarker_validation/model_workspace/revision_global_fdr_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/build_revision_global_fdr.py",
         "sections/results.tex; sections/discussion.tex",
         "marker-specific", "The historical protocol label was 'unsupported/null'; unsupported means statistical non-support under the tested design, not proof of a biological null. Framework utility is operational rather than a new statistical method",
         "goal 1; stage 6", "supported"],
        ["C02", "Gleason and phenotype signals transfer zero-shot across institutions",
         "primary", "Gleason; phenotype", "NADT to PANDA", "CONCH+Virchow",
         "grade/phenotype", "zero-shot cross-cohort transfer",
         f"completed five-seed grid: Gleason {numbers['gleason']['chance']}/{numbers['gleason']['chance_denominator']} and phenotype {numbers['phenotype']['chance']}/{numbers['phenotype']['chance_denominator']} chance-or-worse cells",
         "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_panda_external.py; resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py",
         "sections/results.tex; sections/discussion.tex", "Externally transportable",
         "The correlated grid shares frozen cohorts/folds and is not independent external replication", "goal 2; stage 4.1", "supported"],
        ["C03", "PTEN is multisite-stable within TCGA-PRAD but lacks supported held-out increment over grade",
         "primary", "PTEN", "TCGA-PRAD", "CONCH+Virchow", "PTEN loss",
         "nested patient-disjoint audit and site validation",
         f"all {numbers['pten']['chance_denominator']} grid cells above chance; CONCH delta AUROC {float(pten_row['delta']):+.3f} [{float(pten_row['ci_low']):+.3f},{float(pten_row['ci_high']):+.3f}], refit p={float(pten_refit['permutation_p_one_sided']):.3f}",
         "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py; resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_refit_permutation.py; resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py",
         "sections/results.tex; sections/discussion.tex", "Internally supported; multisite-stable",
         "Not cross-cohort validated; the completed grid does not elevate the reliability tier", "goals 3; stages 2 and 4", "supported_with_downgraded_claim"],
        ["C04", "SPOP is unsupported in the frozen primary configuration and configuration-sensitive in the correlated audit; neither a consistently positive effect nor a definitive absence is established",
         "primary", "SPOP", "TCGA-PRAD", "CONCH+Virchow", "SPOP mutation",
         "frozen primary patient-disjoint CV plus completed correlated sensitivity and site/power audits",
         f"AUROC {spop['observed_min']:.3f}-{spop['observed_max']:.3f}; {spop['chance']}/{spop['chance_denominator']} chance-or-worse; {spop['straddles']}/{spop['straddle_denominator']} seed-null straddles; {spop['native_crossings']}/{spop['native_denominator']} native and {spop['shared_crossings']}/{spop['shared_denominator']} shared-scale crossings; patient-site AUROC: {', '.join(spop_site_parts)}; undefined bootstrap counts {'/'.join(spop_sites['site'].astype(str))} = {spop_undefined}; fixed-score approximation MDE {mde_parts}",
         "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json; resources/projects/prostate_biomarker_validation/model_workspace/spop_classweight_ablation_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/spop_site_predictions.csv", "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py; resources/projects/prostate_biomarker_validation/model_workspace/pilot_spop_classweight_ablation.py; resources/projects/prostate_biomarker_validation/model_workspace/build_ar_spop_evidence_closure.py",
         "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex", "Primary unsupported; configuration-sensitive",
         "All defined site intervals include or touch 0.5. The fixed-score MDE approximation excludes training, OOF, site, configuration-selection, and multiplicity uncertainty and is not an effect-exclusion bound. A modest effect and tumor dilution remain unresolved after C04 evidence closure", "goal 4; stage 4.3; R5", "r5_complete_interpretation_unresolved"],
        ["C05", "AR's positive pooled direction is consistent across correlated Gate A settings; site heterogeneity and transportability are neither supported nor refuted",
         "primary", "AR", "TCGA-PRAD", "CONCH+Virchow", "AR activity score",
         "completed correlated sensitivity, nested, leave-one-site-out, and metadata audits",
         f"{ar['chance_denominator']-ar['chance']}/{ar['chance_denominator']} positive rho; observed range {ar['observed_min']:.3f}-{ar['observed_max']:.3f}; six-site frame {ar_slides} slides/{ar_patients} patients; patient-level site median AR {r5['ar_median_min']:.2f} to {r5['ar_median_max']:.2f}; {ar_zero_interval_label} LOO intervals include zero; ScanScope raw ID {scanscope_count}/{metadata_count}; explicit stain field {stain_count}/{metadata_count}",
         "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json; resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv; resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv", "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py; resources/projects/prostate_biomarker_validation/model_workspace/pilot_ar_site_forest.py; resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py; resources/projects/prostate_biomarker_validation/model_workspace/build_ar_spop_evidence_closure.py",
         "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex", "Pooled direction supported; site transportability unresolved",
         "AR descriptors are patient-level, whereas each LOO rho is slide-level with a patient-cluster bootstrap interval. Raw ScanScope IDs are not scanner models and are confounded with site; explicit stain metadata is unavailable. Grade-independent increment remains unresolved. No scanner, stain, or site causality is inferred", "goal 5; stages 2 and 4.2; R5", "r5_complete_transportability_unresolved"],
        ["C06", "Post-hoc endpoint-specific exploratory signal remains, with effect-size and transfer generalizability limited by endpoint, encoder, and scale",
         "exploratory", "marker 7", "LEOPARD to TCGA-PRAD", "CONCH+Virchow",
         "official PFI; reconstructed recurrence; PFS; DFS; strict recurrence",
         "post-hoc correlated sensitivity, common-source sensitivity, and endpoint sensitivity",
         f"CONCH means {marker7_conch['mean'].min():.3f}-{marker7_conch['mean'].max():.3f}; Virchow {marker7_virchow['mean'].min():.3f}-{marker7_virchow['mean'].max():.3f}; {marker7['chance']}/{marker7['chance_denominator']} chance-or-worse; CONCH is higher in the current grid; Virchow improves at shared 1.76 mpp; common-{int(r2_first['n_common_source_patients'])} R2 complete: {int(r2_first['n_common_source_patients'])} source patients/{int(r2_first['n_source_events'])} events and {int(r2_first['n_target_patients'])} target patients/{int(r2_first['n_target_events'])} events; {raw_common_preserved}/{len(r2['cells'])} raw-to-common null relation preserved; {', '.join(r2_direction_parts)} directions preserved; individual common-minus-raw shifts {r2['shift_min']:+.4f} to {r2['shift_max']:+.4f}; official PFI n={int(r3['official']['n_evaluable'])}/{int(r3['official']['n_events'])} events; C-index {float(r3['official']['c_index']):.3f} [{float(r3['official']['c_index_ci_low']):.3f},{float(r3['official']['c_index_ci_high']):.3f}]; cBioPortal PFS event agreement {float(r3['pfs']['event_agreement']):.3f}",
         "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json; resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_membership_manifest.csv; resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv; resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv; resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py; resources/projects/prostate_biomarker_validation/model_workspace/run_marker7_common_source_sensitivity.py; resources/projects/prostate_biomarker_validation/model_workspace/build_tcga_cdr_pfi_evidence.py",
         "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex", "Post-hoc exploratory; endpoint/encoder/scale-limited",
         "The common-498 result is a correlated source-constant sensitivity, not a causal scale effect, universal encoder ranking, or independent replication. Effect size and transfer generalizability remain limited by endpoint, encoder, and scale; official PFI interval includes 0.5 and does not provide strong confirmatory support", "goal 6; stages 3 and 5; R2/R3", "r3_complete_endpoint_conditioned_exploratory"],
        ["C07", "Marker 7 shows no robust incremental value in the completed paired common-cohort analysis",
         "exploratory", "marker 7", "TCGA-PRAD", "CONCH", "reconstructed recurrence; official PFI",
         "same-patient/same-draw paired common-cohort ΔC and ΔIBS",
         f"reconstructed grade+image delta C {float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_delta']):+.3f} [{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_ci_low']):+.3f},{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_ci_high']):+.3f}]; official PFI grade+image delta C {float(r4['indexed'].loc[('E08_official_pfi', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_delta']):+.3f} [{float(r4['indexed'].loc[('E08_official_pfi', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_ci_low']):+.3f},{float(r4['indexed'].loc[('E08_official_pfi', 'GRADE_COMBINED_VS_GRADE', 'c_index'), 'improvement_ci_high']):+.3f}]; full+image delta C {float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'FULL_COMBINED_VS_FULL', 'c_index'), 'improvement_delta']):+.3f} [{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'FULL_COMBINED_VS_FULL', 'c_index'), 'improvement_ci_low']):+.3f},{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'FULL_COMBINED_VS_FULL', 'c_index'), 'improvement_ci_high']):+.3f}]; M5-M4 delta C {float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'M5_VS_M4', 'c_index'), 'improvement_delta']):+.3f} [{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'M5_VS_M4', 'c_index'), 'improvement_ci_low']):+.3f},{float(r4['indexed'].loc[('E04_reconstructed_with_tumor', 'M5_VS_M4', 'c_index'), 'improvement_ci_high']):+.3f}]",
         "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv", "resources/projects/prostate_biomarker_validation/model_workspace/build_marker7_survival_paired_analysis.py",
         "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex", "Exploratory; endpoint-conditioned",
         f"all official-PFI paired C-index and IBS intervals include zero; the analysis uses a {r4_n_patients}-patient complete-case cohort and multiple imputation was not performed. The reconstructed grade-level C-index interval is positive, but its paired IBS interval, full-model contrasts, hierarchy contrast, and official-PFI contrasts do not establish robust independent or incremental prognostic value", "stages 2.3 and 5; R4", "r4_complete_no_robust_increment"],
        ["C08", "The completed grid is a descriptive correlated sensitivity audit",
         "supporting", "markers 1, 2, 4, 5, 6, and 7", "frozen marker-specific cohorts", "CONCH+Virchow",
         "marker-specific", "descriptive correlated sensitivity audit",
         f"{int(pd.to_numeric(summary['n_seeds']).sum())} correlated cells summarized into {len(summary)} five-seed configurations and {len(contrasts)} paired contrasts",
         "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv", "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py",
         "sections/results.tex; sections/discussion.tex; sections/supplementary_information.tex",
         "Descriptive sensitivity evidence", "Gate A did not overturn prior directional observations; it bounded generalizability across configuration, endpoint, encoder, and site. Insufficient evidence remains unresolved rather than contrary evidence; the same cohorts and folds make this neither external validation nor independent replication",
         "R1 Gate A", "complete_descriptive"],
    ]
    frame = pd.DataFrame(rows, columns=columns)
    completion_status = frame["status"].copy()
    evidence_states = {
        "C01": "descriptive_framework",
        "C02": "transportable",
        "C03": "context_sensitive",
        "C04": "unsupported_in_frozen_design",
        "C05": "context_sensitive",
        "C06": "context_sensitive",
        "C07": "context_sensitive",
        "C08": "descriptive_framework",
    }
    frame.insert(1, "display_order", np.arange(1, len(frame) + 1, dtype=int))
    frame.insert(len(frame.columns) - 1, "completion_status", completion_status)
    frame["status"] = frame["claim_id"].map(evidence_states)
    if frame["status"].isna().any() or not set(frame["status"]).issubset(EVIDENCE_STATES):
        raise ValueError("claim evidence states do not satisfy the submission contract")
    frame.to_csv(output_dir / "claim_evidence_matrix.csv", index=False)
    write_markdown_table(frame, output_dir / "claim_evidence_matrix.md", "Claim–evidence matrix",
                         "MR-v1 핵심 주장과 실제 근거 파일의 추적표. 경로는 저장소 루트 기준이다.")
    return frame


def build_stability_grid_marker_summary(
    summary_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",
    contrast_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
    output_tex: Path = PAPER / "generated/stability_grid_marker_summary.tex",
) -> pd.DataFrame:
    summary, contrasts = load_stability_sources(summary_csv, contrast_csv)
    rows = []
    for marker in STABILITY_MARKERS:
        values = _marker_numbers(summary, contrasts, marker)
        rows.append({
            "marker": marker,
            "metric": values["metric"],
            "observed_cell_min": values["observed_min"],
            "observed_cell_max": values["observed_max"],
            "chance_or_worse_cells": values["chance"],
            "chance_or_worse_denominator": values["chance_denominator"],
            "seed_null_straddles": values["straddles"],
            "seed_null_straddle_denominator": values["straddle_denominator"],
            "native_scale_null_crossings": values["native_crossings"],
            "native_scale_denominator": values["native_denominator"],
            "shared_scale_encoder_null_crossings": values["shared_crossings"],
            "shared_scale_encoder_denominator": values["shared_denominator"],
        })
    frame = pd.DataFrame(rows)
    marker_labels = {
        "gleason": "Gleason", "phenotype": "Phenotype", "pten": "PTEN",
        "spop": "SPOP", "ar": "AR", "marker7": "Marker 7",
    }
    metric_labels = {
        "patient_spearman_rho": r"Spearman $\rho$",
        "patient_auroc": "AUROC",
        "patient_c_index": "C-index",
    }
    lines = [
        r"\begin{table}[htbp]", r"\centering", r"\scriptsize",
        r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llccccc}", r"\toprule",
        r"Marker & Metric & Observed cell range & Chance-or-worse & Seed-null straddle & Native-scale crossing & Shared-scale encoder crossing \\" ,
        r"\midrule",
    ]
    for row in frame.itertuples(index=False):
        lines.append(
            f"{marker_labels[row.marker]} & {metric_labels[row.metric]} & "
            f"{row.observed_cell_min:.3f}--{row.observed_cell_max:.3f} & "
            f"{row.chance_or_worse_cells}/{row.chance_or_worse_denominator} & "
            f"{row.seed_null_straddles}/{row.seed_null_straddle_denominator} & "
            f"{row.native_scale_null_crossings}/{row.native_scale_denominator} & "
            f"{row.shared_scale_encoder_null_crossings}/{row.shared_scale_encoder_denominator} \\\\"
        )
    lines.extend([
        r"\bottomrule", r"\end{tabular}%", r"}",
        r"\caption{Frozen Gate A stability-grid summary derived from the saved 72-configuration and 390-contrast CSVs. Observed ranges span the 60 seed-level cells per marker. Seed-null straddles summarize 12 five-seed configurations; sampling seeds reuse the same frozen cohorts and folds and are not patient-level confidence intervals.}",
        r"\label{tab:supp-stability-grid}", r"\end{table}", "",
    ])
    output_tex = Path(output_tex)
    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(lines), encoding="utf-8")
    return frame


def build_endpoint_hierarchy(
    output_dir: Path = PAPER,
    benchmark_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv",
    recurrence_only_csv: Path = ROOT / "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv",
    r3_performance_csv: Path = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv",
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark = _read_csv_contract(
        benchmark_csv,
        label="endpoint benchmark summary",
        expected_rows=7,
        required_columns=("check", "n", "outcome", "n_events"),
        unique_columns=("check",),
    )
    recurrence = _read_csv_contract(
        recurrence_only_csv,
        label="strict recurrence endpoint",
        expected_rows=393,
        required_columns=("case_id", "event", "follow_up_y"),
        unique_columns=("case_id",),
    )
    recurrence_events = pd.to_numeric(recurrence["event"], errors="coerce")
    if recurrence_events.isna().any() or not recurrence_events.isin({0, 1}).all():
        raise ValueError("strict recurrence endpoint events must be binary")
    dfs_rows = benchmark.loc[benchmark["check"].astype(str).eq("zeroshot_DFS")]
    recurrence_benchmark_rows = benchmark.loc[
        benchmark["check"].astype(str).eq("zeroshot_recurrence_only")
    ]
    if len(dfs_rows) != 1 or not np.isfinite(float(dfs_rows.iloc[0]["n_events"])):
        raise ValueError("endpoint benchmark must contain one finite DFS event count")
    if len(recurrence_benchmark_rows) != 1 or not np.isfinite(
        float(recurrence_benchmark_rows.iloc[0]["n_events"])
    ):
        raise ValueError("endpoint benchmark must contain one finite recurrence event count")
    performance = _read_csv_contract(
        r3_performance_csv,
        label="endpoint official-PFI performance",
        expected_rows=5,
        required_columns=("endpoint_id", "n_events", "c_index_ci_low", "c_index_ci_high"),
        unique_columns=("endpoint_id",),
    )
    official_rows = performance.loc[
        performance["endpoint_id"].astype(str).eq("official_tcga_cdr_pfi")
    ]
    if len(official_rows) != 1:
        raise ValueError("endpoint hierarchy requires one official-PFI performance row")
    official = official_rows.iloc[0]
    official_interval_relation = (
        "includes 0.5"
        if float(official["c_index_ci_low"]) <= 0.5 <= float(official["c_index_ci_high"])
        else "excludes 0.5"
    )
    columns = ["endpoint_id", "hierarchy", "endpoint", "cohort", "event_definition",
               "censoring_or_exclusion", "primary_metric", "multiplicity", "source",
               "status", "limitation"]
    rows = [
        ["E01", "primary", "continuous marker qualification", "marker-specific canonical cohort",
         "observed continuous target", "complete target cases", "patient Spearman rho",
         "17-test BH-FDR family", "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv", "complete", "none"],
        ["E02", "primary", "binary marker qualification", "marker-specific canonical cohort",
         "observed binary target", "complete target cases", "patient AUROC",
         "17-test BH-FDR family", "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv", "complete", "none"],
        ["E03", "secondary", "PTEN/AR held-out increment", "TCGA-PRAD",
         "PTEN loss or AR activity", "complete grade and target", "delta AUROC or delta R2",
         "17-test BH-FDR family", "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv", "complete", "multiple imputation not applicable"],
        ["E04_reconstructed_with_tumor", "exploratory", "reconstructed with-tumor endpoint", "TCGA-PRAD",
         "any valid follow-up recorded wt-with tumor", "latest valid non-event follow-up censors",
         "C-index; td-AUC; IBS; calibration", "confirmatory transfer excluded from 17-test family",
         "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_label_provenance.csv", "complete", "includes persistent disease"],
        ["E05", "exploratory", "strict recurrence-only endpoint", "TCGA-PRAD",
         "tumor-free visit strictly precedes later with-tumor visit",
         "persistent/indeterminate cases excluded", "C-index; td-AUC",
         "sensitivity analysis", "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv; resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv",
         "complete_but_underpowered", f"embedded cohort has {int(float(recurrence_benchmark_rows.iloc[0]['n_events']))} events"],
        ["E06", "exploratory", "TCGA-CDR PFS", "TCGA-PRAD",
         "cBioPortal PFS_STATUS", "PFS_MONTHS", "C-index; td-AUC; landmark AUC",
         "endpoint sensitivity", "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv", "complete", "PFS is not relabeled as PFI"],
        ["E07", "exploratory", "TCGA-CDR DFS", "TCGA-PRAD",
         "cBioPortal DFS_STATUS", "DFS_MONTHS", "C-index; td-AUC; landmark AUC",
         "endpoint sensitivity", "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv", "complete_but_underpowered", f"{int(float(dfs_rows.iloc[0]['n_events']))} events"],
        ["E08_official_pfi", "exploratory", "official TCGA-CDR PFI", "TCGA-PRAD",
         "official PFI event field", "official PFI time field", "C-index; endpoint concordance",
         "endpoint sensitivity", "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv; resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv", "complete_but_uncertain", f"{int(float(official['n_events']))} events; C-index interval {official_interval_relation}"],
        ["E09", "secondary", "3-year and 5-year landmark", "LEOPARD; TCGA-PRAD",
         "event by horizon among definitively known outcomes", "censored before horizon excluded",
         "landmark C-index/AUROC", "sensitivity analysis", "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv",
         "complete", "endpoint-specific sample size varies"],
    ]
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_csv(output_dir / "endpoint_hierarchy.csv", index=False)
    write_markdown_table(frame, output_dir / "endpoint_hierarchy.md", "Endpoint hierarchy",
                         "Primary, secondary, exploratory endpoint와 official-PFI 상태를 명시한다.")
    return frame


def _submission_csv(root: Path, relative: str) -> pd.DataFrame:
    path = Path(root) / relative
    if not path.is_file():
        raise ValueError(f"required submission source is missing: {relative}")
    return pd.read_csv(path)


def _evidence_state_for_marker(marker: str) -> str:
    normalized = str(marker).strip().lower().replace(" ", "")
    if normalized in {"gleason", "phenotype"}:
        return "transportable"
    if normalized == "spop":
        return "unsupported_in_frozen_design"
    return "context_sensitive"


def build_qualification_map(root: Path, claim_csv: Path | None = None) -> pd.DataFrame:
    source = "paper/claim_evidence_matrix.csv"
    claims = pd.read_csv(claim_csv) if claim_csv is not None else _submission_csv(root, source)
    required = {
        "claim_id", "display_order", "claim", "marker", "hierarchy", "status",
        "reliability_tier", "limitation",
    }
    missing = sorted(required - set(claims.columns))
    if missing:
        raise ValueError(f"qualification map claim source missing columns {missing}")
    if claims["claim_id"].duplicated().any():
        raise ValueError("qualification map claim IDs must be unique")
    rows = []
    for row in claims.sort_values("display_order").itertuples(index=False):
        rows.append({
            "semantic_key": str(row.claim_id),
            "claim_id": str(row.claim_id),
            "display_order": int(row.display_order),
            "claim_label": str(row.claim),
            "marker": str(row.marker),
            "hierarchy": str(row.hierarchy),
            "evidence_state": str(row.status),
            "qualification_decision": str(row.reliability_tier),
            "limitation": str(row.limitation),
            "primary_estimate": float(row.display_order),
            "missingness_status": "not_applicable",
            "missingness_detail": "framework layout index; no numeric endpoint is implied",
            "source_path": source,
            "source_field": "claim_id|display_order|claim|marker|hierarchy|status|reliability_tier|limitation",
        })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig1_qualification_map.csv"])


def build_transportable_signals(root: Path) -> pd.DataFrame:
    statistical_path = "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv"
    statistical = _submission_csv(root, statistical_path)
    rows = []
    internal_specs = (
        ("gleason:nadt", "Gleason", "① NADT H&E -> Gleason", "spearman_rho"),
        ("phenotype:nadt", "Phenotype", "② NADT H&E -> Phenotype", "spearman_rho"),
    )
    for key, signal, test_name, metric in internal_specs:
        matches = statistical.loc[statistical["test"].astype(str).eq(test_name)]
        if len(matches) != 1:
            raise ValueError(f"transportable signal source expected one row for {test_name}")
        row = matches.iloc[0]
        rows.append({
            "semantic_key": key,
            "signal": signal,
            "cohort": "NADT",
            "institution": "NADT",
            "encoder": str(row["encoder"]),
            "metric": metric,
            "analysis_unit": "patient",
            "n": int(row["n_patient"]),
            "n_events": pd.NA,
            "primary_estimate": float(row["patient_metric"]),
            "ci_low": float(row["patient_ci_lo"]),
            "ci_high": float(row["patient_ci_hi"]),
            "evidence_state": "transportable",
            "missingness_status": "replicate_accounting_not_saved",
            "missingness_detail": (
                "patient-level interval saved; 2,000 requested in source script; "
                "valid and undefined replicate counts not retained"
            ),
            "source_path": statistical_path,
            "source_field": "test|encoder|n_patient|patient_metric|patient_ci_lo|patient_ci_hi",
        })

    panda_sources = (
        ("Gleason", "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/panda_results.csv", "isup_grade", "pred_zeroshot_nadt", "spearman_rho"),
        ("Phenotype", "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/panda_phenotype_results.csv", "y_tumor", "pred_zeroshot_nadt", "auroc"),
    )
    for signal, source, outcome, prediction, metric in panda_sources:
        frame = _submission_csv(root, source)
        for institution, group in frame.groupby("data_provider", sort=True):
            if metric == "spearman_rho":
                estimate = float(group[outcome].corr(group[prediction], method="spearman"))
                n_events = pd.NA
            else:
                estimate = _binary_auc(group[outcome], group[prediction])
                n_events = int(pd.to_numeric(group[outcome]).sum())
            rows.append({
                "semantic_key": f"{signal.lower()}_panda:{institution}",
                "signal": signal,
                "cohort": "PANDA",
                "institution": str(institution),
                "encoder": "CONCH",
                "metric": metric,
                "analysis_unit": "case_image",
                "n": int(len(group)),
                "n_events": n_events,
                "primary_estimate": estimate,
                "ci_low": np.nan,
                "ci_high": np.nan,
                "evidence_state": "transportable",
                "missingness_status": "interval_not_saved",
                "missingness_detail": "frozen result table contains predictions but no saved interval",
                "source_path": source,
                "source_field": f"data_provider|{outcome}|{prediction}",
            })

    precise_results_path = "resources/data/shared/opendataset/PRECISE/spatial_facevalidity_results_150um.csv"
    precise_participants_path = "resources/data/shared/opendataset/PRECISE/participants.csv"
    precise = _submission_csv(root, precise_results_path)
    participants = _submission_csv(root, precise_participants_path).set_index("IMAGE_NAME")
    tumor = precise.loc[pd.to_numeric(precise["label_class"]).eq(1)]
    predictions = tumor.groupby("image_id")["marker1_gleason"].mean()
    pairs = []
    for image_id, prediction in predictions.items():
        if image_id not in participants.index:
            continue
        match = re.match(r"(\d)\+(\d)=(\d+)", str(participants.loc[image_id, "Gleason_score"]))
        if match:
            pairs.append((float(prediction), int(match.group(3))))
    precise_pairs = pd.DataFrame(pairs, columns=["prediction", "outcome"])
    if len(precise_pairs) == 0:
        raise ValueError("PRECISE transport source has no evaluable real-Gleason pairs")
    rows.append({
        "semantic_key": "gleason_precise:all",
        "signal": "Gleason",
        "cohort": "PRECISE",
        "institution": "multi-session cohort",
        "encoder": "CONCH",
        "metric": "spearman_rho",
        "analysis_unit": "session",
        "n": int(len(precise_pairs)),
        "n_events": pd.NA,
        "primary_estimate": float(precise_pairs["outcome"].corr(precise_pairs["prediction"], method="spearman")),
        "ci_low": np.nan,
        "ci_high": np.nan,
        "evidence_state": "transportable",
        "missingness_status": "interval_not_saved",
        "missingness_detail": "frozen result and label tables contain no saved interval",
        "source_path": f"{precise_results_path};{precise_participants_path}",
        "source_field": "image_id|label_class|marker1_gleason;IMAGE_NAME|Gleason_score",
    })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig2_transportable_signals.csv"])


def build_molecular_qualification(root: Path) -> pd.DataFrame:
    statistical_path = "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv"
    stability_path = "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv"
    spop_site_path = "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv"
    statistical = _submission_csv(root, statistical_path)
    stability = _submission_csv(root, stability_path)
    spop_sites = _submission_csv(root, spop_site_path)
    targets = {
        "PTEN": ("PTEN loss", "pten", 0.5, "context_sensitive"),
        "SPOP": ("SPOP mutation", "spop", 0.5, "unsupported_in_frozen_design"),
        "AR": ("AR score", "ar", 0.0, "context_sensitive"),
    }
    rows = []
    for target, (test_fragment, marker, null_value, state) in targets.items():
        if marker in {"pten", "spop"}:
            event_missingness_status = "event_count_not_recorded_in_source"
            event_missingness_detail = (
                "binary endpoint event count is applicable but not recorded in the saved source rows"
            )
        else:
            event_missingness_status = "event_count_not_applicable"
            event_missingness_detail = "continuous endpoint; event count not applicable"
        matches = statistical.loc[statistical["test"].astype(str).str.contains(test_fragment, regex=False)]
        if len(matches) != 1:
            raise ValueError(f"molecular source expected one frozen primary row for {target}")
        primary = matches.iloc[0]
        rows.append({
            "semantic_key": f"{marker}:frozen_primary",
            "target": target,
            "component": "frozen_primary",
            "cohort": "TCGA-PRAD",
            "encoder": str(primary["encoder"]),
            "metric": "auroc" if marker != "ar" else "spearman_rho",
            "analysis_unit": "patient",
            "patient_denominator": int(primary["n_patient"]),
            "event_count": pd.NA,
            "null_value": null_value,
            "primary_estimate": float(primary["patient_metric"]),
            "interval_low": float(primary["patient_ci_lo"]),
            "interval_high": float(primary["patient_ci_hi"]),
            "interval_type": "patient_bootstrap",
            "range_low": np.nan,
            "range_high": np.nan,
            "n_correlated_cells": 0,
            "evidence_state": state,
            "missingness_status": event_missingness_status,
            "missingness_detail": (
                f"{event_missingness_detail}; interval endpoints retained; "
                "replicate accounting not saved"
            ),
            "source_path": statistical_path,
            "source_field": "test|encoder|n_patient|patient_metric|patient_ci_lo|patient_ci_hi",
        })
        marker_rows = stability.loc[stability["marker"].astype(str).eq(marker)]
        if len(marker_rows) != 12:
            raise ValueError(f"molecular stability source expected 12 configurations for {marker}")
        rows.append({
            "semantic_key": f"{marker}:configuration_summary",
            "target": target,
            "component": "configuration_summary",
            "cohort": "TCGA-PRAD",
            "encoder": "CONCH+Virchow",
            "metric": str(marker_rows["metric"].iloc[0]),
            "analysis_unit": "patient",
            "patient_denominator": int(primary["n_patient"]),
            "event_count": pd.NA,
            "null_value": float(marker_rows["null_value"].iloc[0]),
            "primary_estimate": float(marker_rows["mean"].mean()),
            "interval_low": np.nan,
            "interval_high": np.nan,
            "interval_type": "global_correlated_seed_cell_range",
            "range_low": float(marker_rows["min"].min()),
            "range_high": float(marker_rows["max"].max()),
            "n_correlated_cells": int(marker_rows["n_seeds"].sum()),
            "evidence_state": state,
            "missingness_status": event_missingness_status,
            "missingness_detail": event_missingness_detail,
            "source_path": f"{stability_path};{statistical_path}",
            "source_field": "marker|metric|null_value|mean|min|max|n_seeds;test|n_patient",
        })

    eligible = spop_sites.loc[spop_sites["large_site_eligible"].astype(str).str.lower().eq("true")]
    if set(eligible["site"].astype(str)) != {"CH", "EJ", "G9", "HC", "KK", "YL"}:
        raise ValueError("SPOP site qualification requires the exact six-site frame")
    for site_row in eligible.sort_values("site").itertuples(index=False):
        if bool(site_row.patient_metric_defined):
            metric = "patient_auroc"
            estimate = float(site_row.patient_auroc)
            ci_low = float(site_row.patient_ci_low)
            ci_high = float(site_row.patient_ci_high)
            missingness_status = "bootstrap_accounted"
            missingness_detail = f"{int(site_row.n_bootstrap_undefined)} of {int(site_row.n_bootstrap_requested)} bootstrap replicates undefined"
            source_field = "site|patient_auroc|patient_ci_low|patient_ci_high|n_patients|n_positive_patients|n_bootstrap_requested|n_bootstrap_undefined"
        else:
            metric = "bootstrap_undefined_fraction"
            estimate = float(site_row.bootstrap_undefined_fraction)
            ci_low = np.nan
            ci_high = np.nan
            missingness_status = "primary_metric_undefined"
            missingness_detail = str(site_row.status_reason)
            source_field = "site|bootstrap_undefined_fraction|n_patients|n_positive_patients|status_reason"
        rows.append({
            "semantic_key": f"spop:site:{site_row.site}",
            "target": "SPOP",
            "component": "site_audit",
            "cohort": "TCGA-PRAD",
            "encoder": "CONCH",
            "metric": metric,
            "analysis_unit": "patient",
            "patient_denominator": int(site_row.n_patients),
            "event_count": int(site_row.n_positive_patients),
            "null_value": 0.5 if metric == "patient_auroc" else 0.0,
            "primary_estimate": estimate,
            "interval_low": ci_low,
            "interval_high": ci_high,
            "interval_type": (
                "patient_bootstrap" if metric == "patient_auroc"
                else "not_applicable_primary_metric_undefined"
            ),
            "range_low": np.nan,
            "range_high": np.nan,
            "n_correlated_cells": 0,
            "evidence_state": "unsupported_in_frozen_design",
            "missingness_status": missingness_status,
            "missingness_detail": missingness_detail,
            "source_path": spop_site_path,
            "source_field": source_field,
        })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig3_molecular_qualification.csv"])


def build_confounder_site_audit(root: Path) -> pd.DataFrame:
    nested_sources = (
        ("CONCH", "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv"),
        ("Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_virchow_summary.csv"),
    )
    rows = []
    for encoder, source in nested_sources:
        frame = _submission_csv(root, source)
        patient = frame.loc[
            frame["scope"].astype(str).eq("patient")
            & frame["analysis"].astype(str).eq("grade_only")
            & frame["marker"].astype(str).str.contains("marker4_pten|marker6_ar", regex=True)
        ]
        if len(patient) != 2:
            raise ValueError(f"{encoder} nested audit must contain PTEN and AR patient rows")
        for row in patient.itertuples(index=False):
            target = "PTEN" if "pten" in str(row.marker).lower() else "AR"
            if pd.notna(row.n_events):
                missingness_status = "none"
                missingness_detail = "none"
            elif target == "PTEN":
                missingness_status = "event_count_not_recorded_in_source"
                missingness_detail = (
                    "binary endpoint event count is applicable but not recorded in the saved source rows"
                )
            else:
                missingness_status = "event_count_not_applicable"
                missingness_detail = "continuous endpoint; event count not applicable"
            rows.append({
                "semantic_key": f"{target.lower()}:{encoder}:increment",
                "target": target,
                "audit_type": "grade_adjusted_increment",
                "site": "Pooled",
                "encoder": encoder,
                "metric": str(row.metric),
                "analysis_unit": "patient",
                "cluster_unit": "patient",
                "interval_type": "patient_bootstrap",
                "n_slides": pd.NA,
                "n_patients": int(row.n),
                "n_events": row.n_events,
                "primary_estimate": float(row.delta),
                "ci_low": float(row.ci_low),
                "ci_high": float(row.ci_high),
                "null_value": 0.0,
                "evidence_state": "context_sensitive",
                "missingness_status": missingness_status,
                "missingness_detail": (
                    f"{missingness_detail}; interval endpoints retained; "
                    "replicate accounting not saved"
                ),
                "source_path": source,
                "source_field": "marker|analysis|scope|n|n_events|metric|delta|ci_low|ci_high",
            })

    forest_path = "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv"
    forest = _submission_csv(root, forest_path)
    if len(forest) != 7:
        raise ValueError("AR site forest must contain six held-out sites and one pooled row")
    for row in forest.itertuples(index=False):
        site = "Pooled" if str(row.kind) == "pooled" else str(row.site)
        is_pooled = str(row.kind) == "pooled"
        rows.append({
            "semantic_key": f"ar:site:{site}",
            "target": "AR",
            "audit_type": "ar_site_transport",
            "site": site,
            "encoder": "CONCH",
            "metric": "spearman_rho",
            "analysis_unit": "patient" if is_pooled else "slide",
            "cluster_unit": "patient",
            "interval_type": "patient_bootstrap" if is_pooled else "patient_cluster_bootstrap",
            "n_slides": int(row.n_slides),
            "n_patients": int(row.n_patients),
            "n_events": pd.NA,
            "primary_estimate": float(row.rho),
            "ci_low": float(row.ci_lo),
            "ci_high": float(row.ci_hi),
            "null_value": 0.0,
            "evidence_state": "context_sensitive",
            "missingness_status": "event_count_not_applicable",
            "missingness_detail": (
                "continuous endpoint; event count not applicable; interval endpoints "
                "retained; replicate accounting not saved"
            ),
            "source_path": forest_path,
            "source_field": "site|n_slides|n_patients|rho|ci_lo|ci_hi|kind",
        })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig4_confounder_site_audit.csv"])


def build_marker7_transfer(root: Path) -> pd.DataFrame:
    performance_path = "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv"
    deltas_path = "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv"
    performance = _submission_csv(root, performance_path)
    deltas = _submission_csv(root, deltas_path)
    endpoint_map = {
        "official_tcga_cdr_pfi": "E08_official_pfi",
        "reconstructed_gdc_disease_response": "E04_reconstructed_with_tumor",
    }
    labels = {
        "E08_official_pfi": "Official TCGA-CDR PFI",
        "E04_reconstructed_with_tumor": "Reconstructed with-tumor endpoint",
    }
    rows = []
    selected = performance.loc[performance["endpoint_id"].isin(endpoint_map)]
    if set(selected["endpoint_id"].astype(str)) != set(endpoint_map):
        raise ValueError("marker 7 endpoint performance must preserve official and reconstructed endpoints")
    for row in selected.itertuples(index=False):
        endpoint_id = endpoint_map[str(row.endpoint_id)]
        rows.append({
            "semantic_key": f"{endpoint_id}:frozen_risk:c_index",
            "endpoint_id": endpoint_id,
            "endpoint_label": labels[endpoint_id],
            "result_type": "frozen_risk_performance",
            "contrast_id": "not_applicable",
            "metric": "c_index",
            "n": int(row.n_evaluable),
            "n_events": int(row.n_events),
            "primary_estimate": float(row.c_index),
            "ci_low": float(row.c_index_ci_low),
            "ci_high": float(row.c_index_ci_high),
            "null_value": 0.5,
            "evidence_state": "context_sensitive",
            "missingness_status": "bootstrap_accounted",
            "missingness_detail": f"{int(row.n_bootstrap_undefined)} of {int(row.n_bootstrap_requested)} bootstrap replicates undefined",
            "source_path": performance_path,
            "source_field": "endpoint_id|n_evaluable|n_events|c_index|c_index_ci_low|c_index_ci_high|n_bootstrap_requested|n_bootstrap_undefined",
        })
    expected_endpoints = set(labels)
    if set(deltas["endpoint_id"].astype(str)) != expected_endpoints:
        raise ValueError("paired marker 7 deltas substituted or dropped an endpoint")
    for row in deltas.sort_values(["endpoint_id", "contrast_id", "metric"]).itertuples(index=False):
        rows.append({
            "semantic_key": f"{row.endpoint_id}:{row.contrast_id}:{row.metric}",
            "endpoint_id": str(row.endpoint_id),
            "endpoint_label": labels[str(row.endpoint_id)],
            "result_type": "same_patient_same_draw_delta",
            "contrast_id": str(row.contrast_id),
            "metric": str(row.metric),
            "n": int(row.n_patients),
            "n_events": int(row.n_events),
            "primary_estimate": float(row.improvement_delta),
            "ci_low": float(row.improvement_ci_low),
            "ci_high": float(row.improvement_ci_high),
            "null_value": 0.0,
            "evidence_state": "context_sensitive",
            "missingness_status": "bootstrap_accounted",
            "missingness_detail": f"{int(row.n_bootstrap_undefined)} of {int(row.n_bootstrap_requested)} paired bootstrap draws undefined",
            "source_path": deltas_path,
            "source_field": "endpoint_id|contrast_id|metric|n_patients|n_events|improvement_delta|improvement_ci_low|improvement_ci_high|n_bootstrap_requested|n_bootstrap_undefined|delta_definition",
        })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig5_marker7_transfer.csv"])


def build_stability_overview(root: Path) -> pd.DataFrame:
    summary_path = "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv"
    contrast_path = "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv"
    summary, contrasts = load_stability_sources(
        Path(root) / summary_path, Path(root) / contrast_path
    )
    rows = []
    for marker in STABILITY_MARKERS:
        marker_summary = summary.loc[summary["marker"].astype(str).eq(marker)]
        marker_contrasts = contrasts.loc[contrasts["marker"].astype(str).eq(marker)]
        if len(marker_summary) != 12 or len(marker_contrasts) != 65:
            raise ValueError(f"stability overview source counts do not reconcile for {marker}")
        state = _evidence_state_for_marker(marker)
        rows.append({
            "semantic_key": f"{marker}:configuration_range",
            "marker": marker,
            "component": "configuration_range",
            "metric": str(marker_summary["metric"].iloc[0]),
            "null_value": float(marker_summary["null_value"].iloc[0]),
            "primary_estimate": float(marker_summary["mean"].mean()),
            "range_low": float(marker_summary["min"].min()),
            "range_high": float(marker_summary["max"].max()),
            "n_configurations": int(len(marker_summary)),
            "n_correlated_cells": int(marker_summary["n_seeds"].sum()),
            "n_null_crossings": int(marker_summary["seed_null_straddle"].astype(bool).sum()),
            "n_contrasts": 0,
            "evidence_state": state,
            "missingness_status": "none",
            "missingness_detail": "sampling-seed intervals are descriptive and correlated",
            "source_path": summary_path,
            "source_field": "marker|metric|null_value|mean|min|max|n_seeds|seed_null_straddle",
        })
        crossing_count = int(marker_contrasts["null_crossing"].astype(bool).sum())
        rows.append({
            "semantic_key": f"{marker}:contrast_sensitivity",
            "marker": marker,
            "component": "contrast_sensitivity",
            "metric": "paired_delta",
            "null_value": 0.0,
            "primary_estimate": crossing_count / len(marker_contrasts),
            "range_low": float(marker_contrasts["delta_b_minus_a"].min()),
            "range_high": float(marker_contrasts["delta_b_minus_a"].max()),
            "n_configurations": 0,
            "n_correlated_cells": 0,
            "n_null_crossings": crossing_count,
            "n_contrasts": int(len(marker_contrasts)),
            "evidence_state": state,
            "missingness_status": "none",
            "missingness_detail": "paired contrasts reuse the same frozen cohorts and folds",
            "source_path": contrast_path,
            "source_field": "marker|delta_b_minus_a|null_crossing|contrast",
        })
    return pd.DataFrame(rows, columns=SUBMISSION_SOURCE_SCHEMAS["fig6_stability_overview.csv"])


def validate_submission_source(
    filename: str,
    frame: pd.DataFrame,
    root: Path,
    source_overrides: dict[str, Path] | None = None,
) -> None:
    if filename not in SUBMISSION_SOURCE_SCHEMAS:
        raise ValueError(f"unknown submission source filename: {filename}")
    expected = SUBMISSION_SOURCE_SCHEMAS[filename]
    if tuple(frame.columns) != expected:
        raise ValueError(f"{filename}: schema does not match the submission contract")
    if frame.empty:
        raise ValueError(f"{filename}: source must not be empty")
    if frame["semantic_key"].isna().any() or frame["semantic_key"].astype(str).str.strip().eq("").any():
        raise ValueError(f"{filename}: semantic keys must be present")
    if frame["semantic_key"].duplicated().any():
        raise ValueError(f"{filename}: semantic keys must be unique")
    if not frame["evidence_state"].isin(EVIDENCE_STATES).all():
        raise ValueError(f"{filename}: evidence state is outside the approved hierarchy")
    estimates = pd.to_numeric(frame["primary_estimate"], errors="coerce")
    if estimates.isna().any() or not np.isfinite(estimates.to_numpy(dtype=float)).all():
        raise ValueError(f"{filename}: primary estimates must be finite")
    for column in ("missingness_status", "missingness_detail"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"{filename}: {column} must be explicit")
    if filename == "fig1_qualification_map.csv":
        required_claim_fields = {
            "claim_id", "display_order", "claim", "marker", "hierarchy", "status",
            "reliability_tier", "limitation",
        }
        for fields in frame["source_field"].astype(str):
            if not required_claim_fields.issubset(set(fields.split("|"))):
                raise ValueError(
                    f"{filename}: presentation lineage does not cover every claim column"
                )
    if filename == "fig3_molecular_qualification.csv":
        configuration = frame.loc[frame["component"].astype(str).eq("configuration_summary")]
        if set(configuration["target"].astype(str)) != {"PTEN", "SPOP", "AR"}:
            raise ValueError(f"{filename}: configuration targets do not reconcile")
        if (
            configuration[["interval_low", "interval_high"]].notna().any().any()
            or configuration[["range_low", "range_high"]].isna().any().any()
            or not pd.to_numeric(configuration["n_correlated_cells"]).eq(60).all()
            or not configuration["interval_type"].astype(str).eq(
                "global_correlated_seed_cell_range"
            ).all()
        ):
            raise ValueError(
                f"{filename}: global correlated seed-cell ranges are mislabeled"
            )
    if filename == "fig4_confounder_site_audit.csv":
        held_out = frame.loc[
            frame["audit_type"].astype(str).eq("ar_site_transport")
            & frame["site"].astype(str).ne("Pooled")
        ]
        if set(held_out["site"].astype(str)) != {"CH", "EJ", "G9", "HC", "KK", "YL"}:
            raise ValueError(f"{filename}: AR held-out site set does not reconcile")
        if not (
            held_out["analysis_unit"].astype(str).eq("slide").all()
            and held_out["cluster_unit"].astype(str).eq("patient").all()
            and held_out["interval_type"].astype(str).eq("patient_cluster_bootstrap").all()
        ):
            raise ValueError(f"{filename}: AR site estimate/cluster/interval units are invalid")
    root = Path(root)
    for row in frame.itertuples(index=False):
        relative_paths = str(row.source_path).split(";")
        field_groups = str(row.source_field).split(";")
        if len(relative_paths) != len(field_groups):
            raise ValueError(f"{filename}: source path/field lineage groups do not align")
        for relative, field_group in zip(relative_paths, field_groups):
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts or str(relative_path) != relative:
                raise ValueError(f"{filename}: source paths must be normalized repository-relative paths")
            source = (source_overrides or {}).get(relative, root / relative_path)
            if not source.is_file() or source.suffix.lower() != ".csv":
                raise ValueError(f"{filename}: lineage source does not exist as CSV: {relative}")
            columns = set(pd.read_csv(source, nrows=0).columns)
            fields = field_group.split("|")
            if any(not field or field not in columns for field in fields):
                raise ValueError(f"{filename}: lineage field absent from {relative}: {field_group}")


def build_submission_figure_sources(
    root: Path,
    output_dir: Path,
    claim_csv: Path | None = None,
    source_overrides: dict[str, Path] | None = None,
) -> dict[str, Path]:
    root = Path(root)
    output_dir = Path(output_dir)
    builders = {
        "fig1_qualification_map.csv": lambda source_root: build_qualification_map(
            source_root, claim_csv=claim_csv
        ),
        "fig2_transportable_signals.csv": build_transportable_signals,
        "fig3_molecular_qualification.csv": build_molecular_qualification,
        "fig4_confounder_site_audit.csv": build_confounder_site_audit,
        "fig5_marker7_transfer.csv": build_marker7_transfer,
        "fig6_stability_overview.csv": build_stability_overview,
    }
    frames = {filename: builder(root) for filename, builder in builders.items()}
    for filename, frame in frames.items():
        validate_submission_source(filename, frame, root, source_overrides=source_overrides)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="submission_sources_", dir=output_dir.parent) as temp:
        temporary = Path(temp)
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False)
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in builders:
            destination = output_dir / filename
            os.replace(temporary / filename, destination)
            written[filename] = destination
    return written


SUBMISSION_PACKAGE_RELATIVE_PATHS = (
    "claim_evidence_matrix.csv",
    "claim_evidence_matrix.md",
    "endpoint_hierarchy.csv",
    "endpoint_hierarchy.md",
    "figure_data/fig1_qualification_map.csv",
    "figure_data/fig2_transportable_signals.csv",
    "figure_data/fig3_molecular_qualification.csv",
    "figure_data/fig4_confounder_site_audit.csv",
    "figure_data/fig5_marker7_transfer.csv",
    "figure_data/fig6_stability_overview.csv",
)


def build_revision_submission_package(
    root: Path,
    paper_dir: Path,
    *,
    replace_fn=None,
) -> dict[str, Path]:
    """Build, validate, and transactionally publish all ten Task 2 artifacts."""
    root = Path(root)
    paper_dir = Path(paper_dir)
    paper_dir.parent.mkdir(parents=True, exist_ok=True)
    replace = os.replace if replace_fn is None else replace_fn
    with tempfile.TemporaryDirectory(
        prefix="revision_submission_package_", dir=paper_dir.parent
    ) as temp:
        transaction = Path(temp)
        staged_paper = transaction / "paper"
        staged_paper.mkdir(parents=True)
        build_claim_evidence(
            output_dir=staged_paper,
            stability_summary_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",
            stability_contrast_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
            stability_qc_json=root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json",
            r2_cells_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv",
            r2_deltas_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv",
            r2_membership_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_membership_manifest.csv",
            r2_manifest_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_run_manifest.csv",
            r5_ar_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv",
            r5_metadata_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv",
            r5_spop_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv",
            r5_power_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv",
            r5_predictions_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/spop_site_predictions.csv",
            r5_manifest_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/ar_spop_evidence_manifest.csv",
            r3_mapping_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_mapping.csv",
            r3_concordance_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv",
            r3_performance_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv",
            r3_manifest_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_cdr_pfi_run_manifest.csv",
            r4_summary_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv",
            r4_deltas_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv",
            r4_manifest_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_run_manifest.csv",
            confounder_nested_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv",
            confounder_refit_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_refit_permutation_final2000_summary.csv",
        )
        build_endpoint_hierarchy(
            output_dir=staged_paper,
            benchmark_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_label_benchmark_summary.csv",
            recurrence_only_csv=root / "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv",
            r3_performance_csv=root / "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv",
        )
        staged_claim = staged_paper / "claim_evidence_matrix.csv"
        source_overrides = {"paper/claim_evidence_matrix.csv": staged_claim}
        build_submission_figure_sources(
            root,
            staged_paper / "figure_data",
            claim_csv=staged_claim,
            source_overrides=source_overrides,
        )

        claims = pd.read_csv(staged_claim)
        if not claims["status"].isin(EVIDENCE_STATES).all():
            raise ValueError("staged claim evidence states are invalid")
        endpoints = pd.read_csv(staged_paper / "endpoint_hierarchy.csv")
        endpoint_ids = set(endpoints["endpoint_id"].astype(str))
        if not {"E04_reconstructed_with_tumor", "E08_official_pfi"}.issubset(endpoint_ids):
            raise ValueError("staged endpoint identities do not preserve official PFI")
        staged = {relative: staged_paper / relative for relative in SUBMISSION_PACKAGE_RELATIVE_PATHS}
        if any(not path.is_file() for path in staged.values()):
            raise ValueError("staged submission package is incomplete")

        backup = transaction / "backup"
        backup.mkdir()
        existed = {}
        before_hashes = {}
        for relative in SUBMISSION_PACKAGE_RELATIVE_PATHS:
            destination = paper_dir / relative
            existed[relative] = destination.is_file()
            if existed[relative]:
                backup_path = backup / relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(destination, backup_path)
                before_hashes[relative] = sha256(destination)

        written: dict[str, Path] = {}
        try:
            for relative in SUBMISSION_PACKAGE_RELATIVE_PATHS:
                destination = paper_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                replace(staged[relative], destination)
                written[relative] = destination
        except Exception:
            for relative in SUBMISSION_PACKAGE_RELATIVE_PATHS:
                destination = paper_dir / relative
                if existed[relative]:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(backup / relative, destination)
                elif destination.exists():
                    destination.unlink()
            for relative, expected_hash in before_hashes.items():
                if sha256(paper_dir / relative) != expected_hash:
                    raise RuntimeError(
                        f"submission package rollback failed for {relative}"
                    )
            raise
        return written


def git_state() -> dict:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        return {"available": True, "top_level": top, "commit": commit}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"available": False, "commit": None,
                "reason": "workspace is not a Git working tree; no historical freeze hash can be recovered"}


def build_protocol_provenance(
    output_json: Path = PAPER / "protocol_provenance.json",
    change_log_csv: Path = PAPER / "protocol_change_log.csv",
) -> None:
    required_r2_r5_paths = [ROOT / path for path in R2_R5_PROVENANCE_RELATIVE_PATHS]
    required_r3_r4_paths = [ROOT / path for path in R3_R4_PROVENANCE_RELATIVE_PATHS]
    validate_required_provenance_paths([*required_r2_r5_paths, *required_r3_r4_paths])
    paths = [
        PAPER / "MajorRevision-v1.md", PAPER / "MajorRevision-v1-completion-plan.md",
        PAPER / "revision_analysis_plan.md", ROOT / "docs/10_protocol_freeze.md",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_refit_permutation.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_marker7_clinical_hierarchy.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_label_benchmark.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_scale_tile_sensitivity.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/build_revision_p0_artifacts.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/build_stability_grid_spec.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_tcga.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_nadt.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_marker7.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json",
        *required_r2_r5_paths,
        *required_r3_r4_paths,
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/spop_classweight_ablation_summary.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_spop_classweight_ablation.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/pilot_ar_site_forest.py",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv",
        ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig3_primary_snapshot.csv",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.py",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.pdf",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig3_conch_vs_virchow.png",
        ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_grid.csv",
        ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_contrasts.csv",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig9_scale_tile_heatmap.py",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig9_scale_tile_heatmap.pdf",
        ROOT / "projects/prostate_biomarker_validation/paper/figures/fig9_scale_tile_heatmap.png",
        ROOT / "projects/prostate_biomarker_validation/paper/generated/stability_grid_marker_summary.tex",
        ROOT / "environment.yml", ROOT / "requirements-lock.txt",
        ROOT / "resources/data/shared/opendataset/TCGA-PRAD-BCR/build_bcr_labels.py",
    ]
    records = []
    for path in paths:
        if not path.exists():
            continue
        resolved = path.resolve()
        records.append({
            "path": rel(path),
            "resolved_path": str(resolved),
            "outside_workspace": not resolved.is_relative_to(ROOT.resolve()),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
        })
    payload = {
        "snapshot_type": "retrospective_repository_snapshot",
        "generated_at": datetime.now().astimezone().isoformat(),
        "warning": "This snapshot does not establish historical prespecification and does not replace a missing protocol-freeze commit.",
        "git": git_state(),
        "files": records,
    }
    output_json = Path(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    build_protocol_change_log(change_log_csv)


def build_protocol_change_log(
    output_csv: Path = PAPER / "protocol_change_log.csv",
) -> pd.DataFrame:
    changes = [
        ["2026-07-30", "initial protocol freeze documented", "docs/10_protocol_freeze.md", "historical document; commit unavailable"],
        ["2026-07-31", "first confounder and molecular concordance results recorded", "docs/10_protocol_freeze.md section 9", "rules reported unchanged"],
        ["2026-08-03", "nested/refit reanalysis downgraded PTEN/AR incremental claims", "resources/projects/prostate_biomarker_validation/model_workspace/confounder_nested_summary.csv", "results propagated to manuscript"],
        ["2026-08-03", "MR-v1 completion plan and retrospective checksums created", "paper/protocol_provenance.json", "not a prospective freeze"],
        ["2026-08-06", "Gate B claim framing approved after frozen Gate A aggregation",
         "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json; paper/figure_data/fig9_stability_grid.csv; paper/claim_evidence_matrix.csv",
         "Gate A did not overturn prior directional observations; it bounded generalizability. C04/C05 evidence closure remains pending R5; C06 remains pending common-498/R3"],
        ["2026-08-06", "R2/R5 CPU evidence closure integrated",
         "resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_cells.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_common_source_sensitivity_paired_deltas.csv; resources/projects/prostate_biomarker_validation/model_workspace/ar_site_characteristics.csv; resources/projects/prostate_biomarker_validation/model_workspace/ar_slide_metadata_availability.csv; resources/projects/prostate_biomarker_validation/model_workspace/spop_site_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/spop_power_summary.csv",
         "R2 common-498 complete and R5 evidence closure complete; scientific uncertainty is retained. Official-PFI R3 and paired common-cohort R4 remain pending"],
        ["2026-08-06", "Figure 3 saved-source and analysis-unit correction",
         "paper/figure_data/fig3_primary_snapshot.csv; resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/per_patient_ERG_results.csv; paper/figures/fig3_conch_vs_virchow.py",
         "The legacy marker-3 CONCH hard-code 0.585 lacked an exact saved upstream result and was corrected to the saved 39-patient Spearman value 0.524416; patient/slide analysis units are now explicit and the renderer is CSV-bound"],
        ["2026-08-07", "R3/R4 official endpoint and paired common-cohort closure integrated",
         "resources/projects/prostate_biomarker_validation/model_workspace/pfi_performance_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_common_cohort_summary.csv; resources/projects/prostate_biomarker_validation/model_workspace/marker7_survival_paired_deltas.csv",
         "official PFI complete with an interval including 0.5; the paired endpoint-conditioned analysis provides no robust independent or incremental prognostic value"],
    ]
    frame = pd.DataFrame(changes, columns=["date", "change", "evidence", "interpretation"])
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_csv, index=False)
    return frame


def first_existing(frame: pd.DataFrame, candidates: list[str], default=""):
    for name in candidates:
        if name in frame:
            return frame[name].astype(str)
    return pd.Series([default] * len(frame), index=frame.index, dtype=str)


def build_cohort_manifest() -> None:
    specs = [
        ("NADT-Prostate", "CONCH", "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta.csv", "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/X.npy"),
        ("NADT-Prostate", "Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/meta.csv", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache/X.npy"),
        ("PANDA", "CONCH", "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/meta_panda.csv", "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/X_panda.npy"),
        ("PANDA", "Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache/meta_panda.csv", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache/X_panda.npy"),
        ("TCGA-PRAD", "CONCH", "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/meta.csv", "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/X.npy"),
        ("TCGA-PRAD-SPOP", "Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/meta_spop.csv", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/X_spop.npy"),
        ("TCGA-PRAD-scale-match", "Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/meta_scalematch_0.97mpp.csv", "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/X_scalematch_0.97mpp.npy"),
        ("LEOPARD", "CONCH", "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/meta.csv", "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/X.npy"),
        ("LEOPARD", "Virchow", "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/meta.csv", "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/X.npy"),
    ]
    parts = []
    for cohort, encoder, meta_rel, embedding_rel in specs:
        meta_path, embedding_path = ROOT / meta_rel, ROOT / embedding_rel
        if not meta_path.exists():
            continue
        data = pd.read_csv(meta_path)
        part = pd.DataFrame({
            "cohort": cohort,
            "encoder": encoder,
            "case_id": first_existing(data, ["case_id", "patient_id", "image_id"]),
            "slide_id": first_existing(data, ["file_name", "image_id", "case_id"]),
            "n_tiles": pd.to_numeric(data["n_tiles"], errors="coerce") if "n_tiles" in data else pd.NA,
            "metadata_path": meta_rel,
            "embedding_path": embedding_rel,
            "metadata_sha256": sha256(meta_path),
            "embedding_size_bytes": embedding_path.stat().st_size if embedding_path.exists() else pd.NA,
            "available_label_columns": ";".join(c for c in data.columns if c not in {"file_name", "image_id", "case_id", "patient_id", "n_tiles"}),
            "inclusion_status": "included_in_cached_representation",
        })
        parts.append(part)
    manifest = pd.concat(parts, ignore_index=True)
    manifest.to_csv(ROOT / "cohort_manifest.csv", index=False)


def main() -> None:
    build_revision_submission_package(ROOT, PAPER)
    print("generated claim, endpoint, and submission figure-source artifacts under paper/")


if __name__ == "__main__":
    main()
