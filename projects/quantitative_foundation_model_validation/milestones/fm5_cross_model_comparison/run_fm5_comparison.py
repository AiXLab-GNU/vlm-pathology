#!/usr/bin/env python3
"""Run the approval-gated, descriptive-only FM5 cross-model comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STUDY = ROOT / "projects/quantitative_foundation_model_validation"
RECORDS = STUDY / "preexperiment/governance_records"
PRE = STUDY / "preexperiment"
FM3 = STUDY / "milestones/fm3_paired_embeddings/outputs"
FM4 = STUDY / "milestones/fm4_concept_benchmark/outputs"
OUT = Path(__file__).resolve().parent / "outputs"
ENTRY_CONFIG = OUT / "fm5_entry_run_config.json"
SEED = 20260811
BOOTSTRAP_REPLICATES = 2000
PROTOCOL_ID = "P0-QFMV-2026-08-11-APPROVED-001"

DETERMINISTIC_OUTPUTS = (
    "fm5_subject_comparison.csv",
    "fm5_tile_comparison.csv",
    "fm5_agreement_summary.csv",
    "fm5_representation_similarity.csv",
    "fm5_bootstrap_replicates.csv",
    "fm5_discordance_manifest.csv",
    "fm5_reproducibility_audit.csv",
    "fm5_claim_evidence.csv",
    "fm5-cross-model-comparison-report.md",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_entry() -> dict[str, object]:
    g8 = json.loads((RECORDS / "g8_approval_manifest.json").read_text(encoding="utf-8"))
    g9 = json.loads((RECORDS / "g9_handoff_manifest.json").read_text(encoding="utf-8"))
    fm4 = json.loads((RECORDS / "fm4_scope_approval_manifest.json").read_text(encoding="utf-8"))
    expected_combinations = {
        "CONCH–tumor_fraction–shared_394.24um–descriptive_only",
        "Virchow–tumor_fraction–shared_394.24um–descriptive_only",
    }
    if g8.get("decision") != "Conditional Go" or set(g8.get("approved_combinations", [])) != expected_combinations:
        raise RuntimeError("P0-G8 does not authorize the locked FM5 model-target-FOV combinations")
    if g9.get("status") != "pass_clean_rerun_handoff":
        raise RuntimeError("P0-G9 clean-rerun handoff has not passed")
    if fm4.get("status") != "approved_exploratory_descriptive_fm4":
        raise RuntimeError("FM4 scope approval is missing")
    if fm4.get("claim_ceiling") != "internal_descriptive_recoverability_only":
        raise RuntimeError("FM4 approval claim ceiling drift")
    entry = json.loads(ENTRY_CONFIG.read_text(encoding="utf-8"))
    if not entry.get("execution_authorized") or entry.get("status") != "ready_existing_approval_scope_locked":
        raise RuntimeError("FM5 entry contract is not ready")
    for relative, expected in entry["source_hashes"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"FM5 entry source drift: {relative}")
    for name, expected in entry["output_hashes_excluding_run_config"].items():
        path = OUT / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"FM5 entry contract drift: {name}")
    return {
        "g8_manifest_sha256": sha256(RECORDS / "g8_approval_manifest.json"),
        "g9_manifest_sha256": sha256(RECORDS / "g9_handoff_manifest.json"),
        "fm4_scope_approval_manifest_sha256": sha256(RECORDS / "fm4_scope_approval_manifest.json"),
    }


def centered_linear_cka(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    left -= left.mean(axis=0, keepdims=True)
    right -= right.mean(axis=0, keepdims=True)
    numerator = np.linalg.norm(left.T @ right, ord="fro") ** 2
    denominator = np.linalg.norm(left.T @ left, ord="fro") * np.linalg.norm(right.T @ right, ord="fro")
    return float(numerator / denominator) if denominator > 0 else float("nan")


def spearman(left: np.ndarray, right: np.ndarray) -> float:
    result = stats.spearmanr(left, right).statistic
    return float(result) if np.isfinite(result) else float("nan")


def percentile_ci(values: list[float]) -> tuple[float, float, int, int]:
    array = np.asarray(values, dtype=float)
    valid = array[np.isfinite(array)]
    if not len(valid):
        return float("nan"), float("nan"), 0, len(array)
    low, high = np.percentile(valid, [2.5, 97.5])
    return float(low), float(high), int(len(valid)), int(len(array) - len(valid))


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    oof = pd.read_csv(FM4 / "fm4_oof_predictions.csv")
    subject = pd.read_csv(FM4 / "fm4_subject_predictions.csv")
    bundle = pd.read_csv(FM3 / "embedding_bundle_manifest.csv")
    row_manifest = pd.read_csv(FM3 / "embedding_row_manifest.csv")
    arrays = {
        row.encoder: np.load(ROOT / row.array_path)
        for row in bundle.itertuples(index=False)
    }
    if len(row_manifest) != 1218 or set(arrays) != {"CONCH", "Virchow"}:
        raise RuntimeError("FM3 paired embedding bundle is incomplete")
    if any(array.shape[0] != 1218 or not np.isfinite(array).all() for array in arrays.values()):
        raise RuntimeError("FM3 embedding shape or nonfinite integrity failure")
    if len(oof) != 2436 or len(subject) != 50:
        raise RuntimeError("FM4 OOF prediction counts are not paired 1,218/25 per encoder")
    for frame, key, expected in ((oof, "sample_id", 1218), (subject, "subject_id", 25)):
        counts = frame.groupby("encoder")[key].nunique().to_dict()
        if counts != {"CONCH": expected, "Virchow": expected}:
            raise RuntimeError(f"FM4 {key} pairing failure: {counts}")
    if not np.isfinite(oof[["truth", "prediction"]].to_numpy(float)).all():
        raise RuntimeError("FM4 OOF predictions contain nonfinite values")
    return oof, subject, {**arrays, "row_manifest": row_manifest}


def paired_tables(oof: pd.DataFrame, subject: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tile = oof.pivot(index=["sample_id", "subject_id", "outer_fold", "truth"], columns="encoder", values="prediction").reset_index()
    tile.columns.name = None
    tile = tile.rename(columns={"CONCH": "conch_prediction", "Virchow": "virchow_prediction"})
    tile["conch_residual"] = tile.conch_prediction - tile.truth
    tile["virchow_residual"] = tile.virchow_prediction - tile.truth
    tile["prediction_difference_conch_minus_virchow"] = tile.conch_prediction - tile.virchow_prediction
    tile["absolute_error_delta_conch_minus_virchow"] = tile.conch_residual.abs() - tile.virchow_residual.abs()
    tile = tile.sort_values("sample_id").reset_index(drop=True)

    paired = subject.pivot(
        index=["subject_id", "outer_fold", "n_tiles", "truth_subject_mean"],
        columns="encoder", values="prediction_subject_mean",
    ).reset_index()
    paired.columns.name = None
    paired = paired.rename(columns={"CONCH": "conch_prediction", "Virchow": "virchow_prediction"})
    paired["conch_residual"] = paired.conch_prediction - paired.truth_subject_mean
    paired["virchow_residual"] = paired.virchow_prediction - paired.truth_subject_mean
    paired["prediction_difference_conch_minus_virchow"] = paired.conch_prediction - paired.virchow_prediction
    paired["absolute_error_delta_conch_minus_virchow"] = paired.conch_residual.abs() - paired.virchow_residual.abs()
    paired = paired.sort_values("subject_id").reset_index(drop=True)
    return tile, paired


def subject_mean_embeddings(arrays: dict[str, np.ndarray], row_manifest: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    subjects = sorted(row_manifest.subject_id.unique())
    indices = {subject: np.flatnonzero(row_manifest.subject_id.to_numpy() == subject) for subject in subjects}
    conch = np.stack([arrays["CONCH"][indices[subject]].mean(axis=0) for subject in subjects])
    virchow = np.stack([arrays["Virchow"][indices[subject]].mean(axis=0) for subject in subjects])
    return conch, virchow, subjects


def bootstrap_metrics(
    tile: pd.DataFrame,
    subject: pd.DataFrame,
    subject_conch: np.ndarray,
    subject_virchow: np.ndarray,
) -> tuple[pd.DataFrame, dict[str, list[float]]]:
    rng = np.random.default_rng(SEED)
    subject_ids = subject.subject_id.tolist()
    tile_groups = {key: frame.index.to_numpy() for key, frame in tile.groupby("subject_id", sort=True)}
    values: dict[str, list[float]] = {
        "subject_prediction_spearman": [],
        "subject_residual_spearman": [],
        "subject_mean_absolute_error_delta": [],
        "subject_mean_embedding_linear_cka": [],
        "tile_prediction_spearman": [],
        "tile_residual_spearman": [],
    }
    rows = []
    for replicate in range(BOOTSTRAP_REPLICATES):
        draw = rng.integers(0, len(subject_ids), size=len(subject_ids))
        sampled_subjects = [subject_ids[index] for index in draw]
        sampled_tile_indices = np.concatenate([tile_groups[item] for item in sampled_subjects])
        subject_sample = subject.iloc[draw]
        tile_sample = tile.loc[sampled_tile_indices]
        replicate_values = {
            "subject_prediction_spearman": spearman(subject_sample.conch_prediction, subject_sample.virchow_prediction),
            "subject_residual_spearman": spearman(subject_sample.conch_residual, subject_sample.virchow_residual),
            "subject_mean_absolute_error_delta": float(subject_sample.absolute_error_delta_conch_minus_virchow.mean()),
            "subject_mean_embedding_linear_cka": centered_linear_cka(subject_conch[draw], subject_virchow[draw]),
            "tile_prediction_spearman": spearman(tile_sample.conch_prediction, tile_sample.virchow_prediction),
            "tile_residual_spearman": spearman(tile_sample.conch_residual, tile_sample.virchow_residual),
        }
        for metric, value in replicate_values.items():
            values[metric].append(value)
            rows.append({
                "replicate": replicate,
                "metric": metric,
                "estimate": value if np.isfinite(value) else np.nan,
                "defined": bool(np.isfinite(value)),
                "bootstrap_unit": "subject",
                "seed": SEED,
            })
    return pd.DataFrame(rows), values


def write_outputs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    oof, subject_source, arrays = load_inputs()
    tile, subject = paired_tables(oof, subject_source)
    subject_conch, subject_virchow, embedding_subjects = subject_mean_embeddings(arrays, arrays["row_manifest"])
    if embedding_subjects != subject.subject_id.tolist():
        raise RuntimeError("subject embedding and FM4 prediction order mismatch")
    bootstrap, bootstrap_values = bootstrap_metrics(tile, subject, subject_conch, subject_virchow)

    point_metrics = {
        "subject_prediction_spearman": spearman(subject.conch_prediction, subject.virchow_prediction),
        "subject_residual_spearman": spearman(subject.conch_residual, subject.virchow_residual),
        "subject_mean_absolute_error_delta": float(subject.absolute_error_delta_conch_minus_virchow.mean()),
        "subject_mean_embedding_linear_cka": centered_linear_cka(subject_conch, subject_virchow),
        "tile_prediction_spearman": spearman(tile.conch_prediction, tile.virchow_prediction),
        "tile_residual_spearman": spearman(tile.conch_residual, tile.virchow_residual),
    }
    summary_rows = []
    for metric, estimate in point_metrics.items():
        low, high, valid, undefined = percentile_ci(bootstrap_values[metric])
        summary_rows.append({
            "family_id": "FM5-PRIMARY-DESCRIPTIVE" if metric.startswith("subject_") else "FM5-SECONDARY-DESCRIPTIVE",
            "metric": metric,
            "estimate": estimate,
            "ci_low": low,
            "ci_high": high,
            "n_subjects": 25,
            "n_tiles": 1218,
            "n_valid_bootstrap": valid,
            "n_undefined_bootstrap": undefined,
            "multiplicity": "descriptive_only_no_p_or_q_values",
            "interpretation": "paired_descriptive_not_encoder_superiority",
            "protocol_id": PROTOCOL_ID,
        })
    summary = pd.DataFrame(summary_rows)
    if (summary[summary.family_id.eq("FM5-PRIMARY-DESCRIPTIVE")].n_undefined_bootstrap / BOOTSTRAP_REPLICATES > 0.05).any():
        raise RuntimeError("primary FM5 bootstrap undefined rate exceeds the pre-specified 5% stop threshold")

    representation = pd.DataFrame([
        {
            "analysis_unit": "subject_mean",
            "n_units": 25,
            "metric": "centered_linear_CKA",
            "estimate": point_metrics["subject_mean_embedding_linear_cka"],
            "ci_low": summary.loc[summary.metric.eq("subject_mean_embedding_linear_cka"), "ci_low"].iloc[0],
            "ci_high": summary.loc[summary.metric.eq("subject_mean_embedding_linear_cka"), "ci_high"].iloc[0],
            "uncertainty": "paired_subject_bootstrap",
            "interpretation": "descriptive_representation_similarity_not_superiority",
        },
        {
            "analysis_unit": "tile",
            "n_units": 1218,
            "metric": "centered_linear_CKA",
            "estimate": centered_linear_cka(arrays["CONCH"], arrays["Virchow"]),
            "ci_low": np.nan,
            "ci_high": np.nan,
            "uncertainty": "point_estimate_only_secondary",
            "interpretation": "descriptive_representation_similarity_not_superiority",
        },
    ])

    conch_median = float(subject.conch_prediction.median())
    virchow_median = float(subject.virchow_prediction.median())
    conch_high = subject.conch_prediction >= conch_median
    virchow_high = subject.virchow_prediction >= virchow_median
    subject["discordance_class"] = np.select(
        [conch_high & virchow_high, ~conch_high & ~virchow_high, conch_high & ~virchow_high],
        ["concordant_high", "concordant_low", "conch_only"],
        default="virchow_only",
    )
    subject["conch_median_cutoff"] = conch_median
    subject["virchow_median_cutoff"] = virchow_median
    subject["discordance_interpretation"] = "technical_rank_stratum_not_model_specific_biology_or_superiority"

    p0_representation = pd.read_csv(PRE / "representation_similarity.csv")
    audit_rows = []
    for unit, observed in (
        ("tile", representation.loc[representation.analysis_unit.eq("tile"), "estimate"].iloc[0]),
        ("subject_mean", representation.loc[representation.analysis_unit.eq("subject_mean"), "estimate"].iloc[0]),
    ):
        expected = float(p0_representation[
            p0_representation.representation_a.eq("CONCH_shared_394.24um")
            & p0_representation.representation_b.eq("Virchow_shared_394.24um")
            & p0_representation.analysis_unit.eq(unit)
            & p0_representation.metric_name.eq("centered_linear_CKA")
        ].estimate.iloc[0])
        audit_rows.append({
            "source": "P0-M7 representation_similarity.csv",
            "analysis_unit": unit,
            "metric": "centered_linear_CKA",
            "source_estimate": expected,
            "fm5_recomputed_estimate": observed,
            "absolute_difference": abs(expected - observed),
            "within_tolerance_1e_12": bool(abs(expected - observed) <= 1e-12),
        })
    audit = pd.DataFrame(audit_rows)
    if not audit.within_tolerance_1e_12.all():
        raise RuntimeError("FM5 did not reproduce the P0-M7 CKA source values within tolerance")

    claims = pd.DataFrame([
        {
            "claim_id": "FM5-C1",
            "claim": "paired internal cross-encoder prediction/residual agreement can be described",
            "status": "supported_descriptive_only",
            "evidence": "fm5_agreement_summary.csv; fm5_bootstrap_replicates.csv",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "claim_id": "FM5-C2",
            "claim": "paired internal representation similarity can be described with centered linear CKA",
            "status": "supported_descriptive_only",
            "evidence": "fm5_representation_similarity.csv; fm5_reproducibility_audit.csv",
            "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        },
        {
            "claim_id": "FM5-C3",
            "claim": "encoder superiority, robustness, transport, H2, clinical/PNI and general model-specific concepts",
            "status": "prohibited_not_tested",
            "evidence": "fm5-entry-packet.md",
            "claim_ceiling": "not_authorized",
        },
    ])

    tile.to_csv(output_dir / "fm5_tile_comparison.csv", index=False, lineterminator="\n")
    subject.to_csv(output_dir / "fm5_subject_comparison.csv", index=False, lineterminator="\n")
    summary.to_csv(output_dir / "fm5_agreement_summary.csv", index=False, lineterminator="\n")
    representation.to_csv(output_dir / "fm5_representation_similarity.csv", index=False, lineterminator="\n")
    bootstrap.to_csv(output_dir / "fm5_bootstrap_replicates.csv", index=False, lineterminator="\n")
    subject.to_csv(output_dir / "fm5_discordance_manifest.csv", index=False, lineterminator="\n")
    audit.to_csv(output_dir / "fm5_reproducibility_audit.csv", index=False, lineterminator="\n")
    claims.to_csv(output_dir / "fm5_claim_evidence.csv", index=False, lineterminator="\n")

    metric_map = summary.set_index("metric")
    cka = representation.set_index("analysis_unit")
    counts = subject.discordance_class.value_counts().to_dict()
    report = [
        "---",
        "document_id: fm5-cross-model-comparison-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: generated",
        "created: 2026-08-14",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs/fm5-cross-model-comparison-report.md",
        "---", "", "# FM5 cross-model comparison report", "",
        "- Scope: internal descriptive cross-encoder consistency only",
        "- Samples: 1,218 paired tiles / 25 subjects / shared 394.24 µm",
        f"- Subject prediction Spearman: {metric_map.loc['subject_prediction_spearman', 'estimate']:.4f} [{metric_map.loc['subject_prediction_spearman', 'ci_low']:.4f}, {metric_map.loc['subject_prediction_spearman', 'ci_high']:.4f}]",
        f"- Subject residual Spearman: {metric_map.loc['subject_residual_spearman', 'estimate']:.4f} [{metric_map.loc['subject_residual_spearman', 'ci_low']:.4f}, {metric_map.loc['subject_residual_spearman', 'ci_high']:.4f}]",
        f"- Mean paired absolute-error delta (CONCH−Virchow): {metric_map.loc['subject_mean_absolute_error_delta', 'estimate']:.6f} [{metric_map.loc['subject_mean_absolute_error_delta', 'ci_low']:.6f}, {metric_map.loc['subject_mean_absolute_error_delta', 'ci_high']:.6f}]",
        f"- Linear CKA: subject mean {cka.loc['subject_mean', 'estimate']:.4f}, tile {cka.loc['tile', 'estimate']:.4f}",
        f"- Discordance strata: {json.dumps(counts, sort_keys=True)}", "",
        "All intervals are descriptive paired-bootstrap precision intervals, not superiority tests. No result establishes scanner/stain robustness, external transport, disease prediction/H2, clinical or whole-slide PNI performance, or a general model-specific concept.",
    ]
    (output_dir / "fm5-cross-model-comparison-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    started = utc_now()
    approval = verify_entry()
    write_outputs(args.output_dir)
    if args.worker:
        return

    with tempfile.TemporaryDirectory(prefix="fm5-clean-rerun-", dir="/tmp") as directory:
        clean_dir = Path(directory)
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", "--output-dir", str(clean_dir)],
            cwd=ROOT,
            check=True,
        )
        comparison_rows = []
        for name in DETERMINISTIC_OUTPUTS:
            reference_hash = sha256(args.output_dir / name)
            clean_hash = sha256(clean_dir / name)
            comparison_rows.append({
                "output_file": name,
                "reference_sha256": reference_hash,
                "clean_rerun_sha256": clean_hash,
                "exact_match": reference_hash == clean_hash,
            })
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(args.output_dir / "fm5_clean_rerun_comparison.csv", index=False, lineterminator="\n")
    mismatches = int((~comparison.exact_match).sum())
    if mismatches:
        raise RuntimeError(f"FM5 clean rerun mismatch count: {mismatches}")

    config = {
        "schema_version": "fm5-comparison-1.0",
        "protocol_id": PROTOCOL_ID,
        "status": "complete_approved_amber_scope_descriptive_fm5",
        "started_at_utc": started,
        "generated_at_utc": utc_now(),
        "execution_authorized": True,
        "approval_basis": approval,
        "seed": SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "counts": {"paired_tiles": 1218, "subjects": 25, "encoders": 2, "targets": 1},
        "claim_ceiling": "internal_descriptive_cross_encoder_consistency_only",
        "clean_rerun": {
            "deterministic_outputs_compared": len(DETERMINISTIC_OUTPUTS),
            "mismatch_count": mismatches,
            "status": "pass",
        },
        "source_hashes": json.loads(ENTRY_CONFIG.read_text(encoding="utf-8"))["source_hashes"],
        "output_hashes_excluding_run_config": {
            path.name: sha256(path)
            for path in sorted(args.output_dir.iterdir())
            if path.is_file() and path.name != "fm5_run_config.json"
        },
    }
    (args.output_dir / "fm5_run_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": config["status"], "clean_mismatches": mismatches}, sort_keys=True))


if __name__ == "__main__":
    main()
