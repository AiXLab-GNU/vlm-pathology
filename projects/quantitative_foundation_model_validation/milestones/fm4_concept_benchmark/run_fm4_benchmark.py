#!/usr/bin/env python3
"""Run the approved, scope-capped FM4 descriptive concept benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from projects.quantitative_foundation_model_validation.governance_portal.governance import (
    fm4_scope_status,
)


STUDY = ROOT / "projects/quantitative_foundation_model_validation"
RECORDS = STUDY / "preexperiment/governance_records"
FM2 = STUDY / "milestones/fm2_paired_manifest/outputs"
FM3 = STUDY / "milestones/fm3_paired_embeddings/outputs"
FM4 = Path(__file__).resolve().parent
PREPARATION = FM4 / "outputs"
DEFAULT_OUT = PREPARATION

PROTOCOL_ID = "P0-QFMV-2026-08-11-APPROVED-001"
SEED = 20260811
ALPHA_GRID = np.logspace(-4, 4, 17)
BOOTSTRAP_REPLICATES = 2000
PERMUTATION_REPLICATES = 2000
CAPACITY_RANK = 64
CLAIM_CEILING = "internal_descriptive_recoverability_only"
APPROVED_SCOPE = (
    "tumor_fraction × CONCH/Virchow × shared 394.24um; exploratory descriptive H1 only"
)

DETERMINISTIC_OUTPUTS = (
    "fm4_oof_predictions.csv",
    "fm4_subject_predictions.csv",
    "fm4_summary.csv",
    "fm4_paired_deltas.csv",
    "fm4_permutation_null.csv",
    "fm4_bootstrap_replicates.csv",
    "fm4_fold_diagnostics.csv",
    "fm4_capacity_oof_predictions.csv",
    "fm4_capacity_sensitivity.csv",
    "fm4_claim_evidence.csv",
    "fm4-concept-benchmark-report.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty output: {path.name}")
    pd.DataFrame(rows).to_csv(path, index=False, lineterminator="\n")


def safe_metric(metric: str, truth: np.ndarray, prediction: np.ndarray) -> tuple[float, str]:
    truth = np.asarray(truth, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    valid = np.isfinite(truth) & np.isfinite(prediction)
    truth, prediction = truth[valid], prediction[valid]
    if len(truth) < 2:
        return np.nan, "fewer_than_two_evaluable_units"
    if metric == "spearman":
        value = stats.spearmanr(truth, prediction).statistic
    elif metric == "mae":
        value = mean_absolute_error(truth, prediction)
    elif metric == "r2":
        value = r2_score(truth, prediction)
    else:
        raise ValueError(f"unknown metric: {metric}")
    if not np.isfinite(value):
        return np.nan, "nonfinite_statistic"
    return float(value), ""


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


def fit_transform(
    train_x: np.ndarray,
    valid_x: np.ndarray,
    *,
    rank: int | None,
) -> tuple[np.ndarray, np.ndarray, StandardScaler, PCA | None]:
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_x)
    valid_scaled = scaler.transform(valid_x)
    reducer = None
    if rank is not None:
        effective_rank = min(rank, train_scaled.shape[0] - 1, train_scaled.shape[1])
        if effective_rank < 2:
            raise RuntimeError("insufficient rank for capacity sensitivity")
        reducer = PCA(
            n_components=effective_rank,
            svd_solver="randomized",
            random_state=SEED,
        )
        train_scaled = reducer.fit_transform(train_scaled)
        valid_scaled = reducer.transform(valid_scaled)
    return train_scaled, valid_scaled, scaler, reducer


def nested_oof(
    x: np.ndarray,
    y: np.ndarray,
    folds: np.ndarray,
    groups: np.ndarray,
    *,
    rank: int | None,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    predictions = np.full(len(y), np.nan)
    selected = np.full(len(y), np.nan)
    diagnostics: list[dict[str, object]] = []
    for outer in sorted(np.unique(folds)):
        outer_train = folds != outer
        outer_test = folds == outer
        losses = {float(alpha): [] for alpha in ALPHA_GRID}
        for inner in sorted(np.unique(folds[outer_train])):
            inner_train = outer_train & (folds != inner)
            inner_valid = outer_train & (folds == inner)
            train_x, valid_x, _, _ = fit_transform(
                x[inner_train], x[inner_valid], rank=rank
            )
            for alpha in ALPHA_GRID:
                model = Ridge(alpha=float(alpha), solver="lsqr")
                model.fit(train_x, y[inner_train])
                inner_prediction = model.predict(valid_x)
                losses[float(alpha)].append(
                    float(np.mean((y[inner_valid] - inner_prediction) ** 2))
                )
        candidates = [
            (float(np.mean(values)), alpha)
            for alpha, values in losses.items()
            if values
        ]
        if not candidates:
            raise RuntimeError(f"no inner-fold candidate for outer fold {outer}")
        best_alpha = min(candidates, key=lambda item: (item[0], item[1]))[1]
        train_x, test_x, _, _ = fit_transform(
            x[outer_train], x[outer_test], rank=rank
        )
        model = Ridge(alpha=best_alpha, solver="lsqr")
        model.fit(train_x, y[outer_train])
        train_prediction = model.predict(train_x)
        test_prediction = model.predict(test_x)
        predictions[outer_test] = test_prediction
        selected[outer_test] = best_alpha
        values: dict[str, float] = {}
        reasons: list[str] = []
        for split, truth, prediction in (
            ("train", y[outer_train], train_prediction),
            ("test", y[outer_test], test_prediction),
        ):
            for metric in ("mae", "r2", "spearman"):
                estimate, reason = safe_metric(metric, truth, prediction)
                values[f"{split}_{metric}"] = estimate
                if reason:
                    reasons.append(f"{split}_{metric}:{reason}")
        diagnostics.append(
            {
                "outer_fold": int(outer),
                "selected_alpha": best_alpha,
                "n_train_tiles": int(outer_train.sum()),
                "n_test_tiles": int(outer_test.sum()),
                "n_train_subjects": int(len(np.unique(groups[outer_train]))),
                "n_test_subjects": int(len(np.unique(groups[outer_test]))),
                "train_target_min": float(y[outer_train].min()),
                "train_target_max": float(y[outer_train].max()),
                "test_target_min": float(y[outer_test].min()),
                "test_target_max": float(y[outer_test].max()),
                "train_mae": values["train_mae"],
                "test_mae": values["test_mae"],
                "train_r2": values["train_r2"],
                "test_r2": values["test_r2"],
                "train_spearman": values["train_spearman"],
                "test_spearman": values["test_spearman"],
                "spearman_generalization_gap": (
                    values["train_spearman"] - values["test_spearman"]
                ),
                "diagnostic_status": "pass" if not reasons else "undefined:" + "|".join(reasons),
            }
        )
    if not np.isfinite(predictions).all() or not np.isfinite(selected).all():
        raise RuntimeError("OOF coverage is incomplete")
    return predictions, selected, diagnostics


def analysis_frame(
    manifest: pd.DataFrame,
    prediction: np.ndarray,
    unit: str,
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "group_id": manifest.subject_id.astype(str),
            "truth": manifest.tumor_fraction.to_numpy(float),
            "prediction": prediction,
        }
    )
    if unit == "tile_clustered_by_subject":
        return frame
    if unit == "subject_mean":
        return frame.groupby("group_id", as_index=False).agg(
            truth=("truth", "mean"), prediction=("prediction", "mean")
        )
    raise ValueError(unit)


def resampled_metric(
    frame: pd.DataFrame,
    metric: str,
    sampled_groups: np.ndarray,
) -> tuple[float, str]:
    group_values = frame.group_id.to_numpy()
    group_indices = {
        group: np.flatnonzero(group_values == group)
        for group in pd.unique(group_values)
    }
    indices = np.concatenate([group_indices[group] for group in sampled_groups])
    return safe_metric(
        metric,
        frame.truth.to_numpy()[indices],
        frame.prediction.to_numpy()[indices],
    )


def load_inputs() -> tuple[
    pd.DataFrame,
    dict[str, np.ndarray],
    dict[str, dict[str, str]],
    dict[str, object],
]:
    approval = fm4_scope_status()
    if not approval["finalized"] or not approval["evidence_current"]:
        raise RuntimeError("FM4 approval is absent or does not match the current evidence snapshot")
    approved_manifest = approval["manifest"]
    if (
        approved_manifest.get("status") != "approved_exploratory_descriptive_fm4"
        or approved_manifest.get("approved_scope") != APPROVED_SCOPE
        or approved_manifest.get("claim_ceiling") != CLAIM_CEILING
    ):
        raise RuntimeError("FM4 approval scope does not match the executable contract")

    manifest = pd.read_csv(FM2 / "paired_sample_manifest.csv", keep_default_na=False)
    row_manifest = pd.read_csv(FM3 / "embedding_row_manifest.csv", keep_default_na=False)
    bundle = pd.read_csv(FM3 / "embedding_bundle_manifest.csv", keep_default_na=False)
    if len(manifest) != 1218 or len(row_manifest) != 1218:
        raise RuntimeError("FM2/FM3 row count changed")
    if not manifest.sample_id.equals(row_manifest.sample_id):
        raise RuntimeError("FM2/FM3 sample order changed")
    if not manifest.subject_id.equals(row_manifest.subject_id):
        raise RuntimeError("FM2/FM3 subject order changed")
    if not np.array_equal(manifest.fold.to_numpy(int), row_manifest.fold.to_numpy(int)):
        raise RuntimeError("FM2/FM3 fold assignment changed")
    if not np.allclose(
        manifest.tumor_fraction.to_numpy(float),
        row_manifest.tumor_fraction.to_numpy(float),
        rtol=0,
        atol=0,
    ):
        raise RuntimeError("FM2/FM3 tumor truth changed")
    if manifest.subject_id.nunique() != 25 or set(manifest.fold.astype(int)) != set(range(5)):
        raise RuntimeError("FM4 requires the frozen 25-subject, five-fold cohort")
    if int(manifest.groupby("subject_id").fold.nunique().max()) != 1:
        raise RuntimeError("subject leakage detected across outer folds")
    if set(manifest.allowed_role) != {"shared_394.24um_descriptive_tumor_H1"}:
        raise RuntimeError("manifest contains a row outside the approved target/FOV role")
    observed_fov = manifest.shared_fov_um.to_numpy(float)
    observed_error = manifest.fov_error_um.to_numpy(float)
    if (
        np.max(np.abs(observed_fov - 394.24)) > 0.15
        or not np.allclose(observed_error, observed_fov - 394.24, rtol=0, atol=1e-9)
    ):
        raise RuntimeError("shared physical FOV is outside the frozen nominal tolerance")

    arrays: dict[str, np.ndarray] = {}
    bundle_rows: dict[str, dict[str, str]] = {}
    for encoder in ("CONCH", "Virchow"):
        match = bundle[bundle.encoder.eq(encoder)]
        if len(match) != 1:
            raise RuntimeError(f"FM3 bundle must contain exactly one {encoder} row")
        row = match.iloc[0].to_dict()
        path = ROOT / str(row["array_path"])
        if not path.is_file() or sha256(path) != row["array_sha256"]:
            raise RuntimeError(f"{encoder} embedding source hash mismatch")
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        expected = (1218, 512 if encoder == "CONCH" else 2560)
        if array.shape != expected or not np.isfinite(array).all():
            raise RuntimeError(f"{encoder} embedding array failed shape/finite audit")
        arrays[encoder] = np.asarray(array, dtype=np.float32)
        bundle_rows[encoder] = row
    return manifest, arrays, bundle_rows, approved_manifest


def run_once(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    manifest, arrays, bundle, approval = load_inputs()
    truth = manifest.tumor_fraction.to_numpy(float)
    folds = manifest.fold.to_numpy(int)
    groups = manifest.subject_id.astype(str).to_numpy()
    unique_groups = pd.unique(groups)
    paired_manifest_hash = sha256(FM2 / "paired_sample_manifest.csv")
    fold_manifest_hash = sha256(PREPARATION / "fm4_shared_fold_manifest.csv")
    approval_manifest_hash = sha256(RECORDS / "fm4_scope_approval_manifest.json")

    predictions: dict[str, np.ndarray] = {}
    selected: dict[str, np.ndarray] = {}
    fold_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        prediction, choices, diagnostics = nested_oof(
            arrays[encoder], truth, folds, groups, rank=None
        )
        predictions[encoder] = prediction
        selected[encoder] = choices
        for row in diagnostics:
            fold_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "encoder": encoder,
                    "configuration": "full_embedding_ridge",
                    **row,
                    "protocol_id": PROTOCOL_ID,
                }
            )
        print(f"FM4 {encoder} primary nested OOF complete", flush=True)

    oof_rows: list[dict[str, object]] = []
    subject_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        for index, row in enumerate(manifest.itertuples(index=False)):
            oof_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "target_role": "T2_descriptive_only_not_confirmatory",
                    "encoder": encoder,
                    "sample_id": row.sample_id,
                    "subject_id": row.subject_id,
                    "outer_fold": int(row.fold),
                    "embedding_row": index,
                    "truth": float(row.tumor_fraction),
                    "prediction": float(predictions[encoder][index]),
                    "prediction_status": "new_subject_grouped_nested_oof",
                    "selected_alpha": float(selected[encoder][index]),
                    "source_embedding_path": bundle[encoder]["array_path"],
                    "source_embedding_sha256": bundle[encoder]["array_sha256"],
                    "paired_manifest_sha256": paired_manifest_hash,
                    "fold_manifest_sha256": fold_manifest_hash,
                    "approval_manifest_sha256": approval_manifest_hash,
                    "protocol_id": PROTOCOL_ID,
                }
            )
        frame = analysis_frame(manifest, predictions[encoder], "subject_mean")
        fold_by_subject = manifest.groupby("subject_id").fold.first().astype(int)
        tile_counts = manifest.groupby("subject_id").size()
        for row in frame.itertuples(index=False):
            subject_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "encoder": encoder,
                    "subject_id": row.group_id,
                    "outer_fold": int(fold_by_subject.loc[row.group_id]),
                    "n_tiles": int(tile_counts.loc[row.group_id]),
                    "truth_subject_mean": float(row.truth),
                    "prediction_subject_mean": float(row.prediction),
                    "protocol_id": PROTOCOL_ID,
                }
            )

    units = ("tile_clustered_by_subject", "subject_mean")
    metrics = ("mae", "r2", "spearman")
    frames = {
        (encoder, unit): analysis_frame(manifest, predictions[encoder], unit)
        for encoder in ("CONCH", "Virchow")
        for unit in units
    }

    permutation_rows: list[dict[str, object]] = []
    null_values: dict[tuple[str, str], list[float]] = {}
    for encoder in ("CONCH", "Virchow"):
        subject_frame = frames[(encoder, "subject_mean")]
        tile_frame = frames[(encoder, "tile_clustered_by_subject")]
        subject_null: list[float] = []
        coordinate_null: list[float] = []
        tile_groups = tile_frame.group_id.to_numpy()
        group_indices = {
            group: np.flatnonzero(tile_groups == group)
            for group in pd.unique(tile_groups)
        }
        for replicate in range(PERMUTATION_REPLICATES):
            seed = SEED + replicate
            rng = np.random.default_rng(seed)
            estimate, reason = safe_metric(
                "spearman",
                rng.permutation(subject_frame.truth.to_numpy()),
                subject_frame.prediction.to_numpy(),
            )
            subject_null.append(estimate)
            permutation_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "encoder": encoder,
                    "null_type": "subject_mean_label_permutation",
                    "analysis_unit": "subject_mean",
                    "replicate_id": replicate,
                    "permutation_seed": seed,
                    "metric_name": "spearman",
                    "estimate": estimate,
                    "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                    "undefined_reason": reason,
                    "conditional_no_refit": True,
                    "protocol_id": PROTOCOL_ID,
                }
            )
            permuted_prediction = tile_frame.prediction.to_numpy().copy()
            for indices in group_indices.values():
                permuted_prediction[indices] = rng.permutation(permuted_prediction[indices])
            estimate, reason = safe_metric(
                "spearman", tile_frame.truth.to_numpy(), permuted_prediction
            )
            coordinate_null.append(estimate)
            permutation_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "encoder": encoder,
                    "null_type": "within_subject_coordinate_permutation",
                    "analysis_unit": "tile_clustered_by_subject",
                    "replicate_id": replicate,
                    "permutation_seed": seed,
                    "metric_name": "spearman",
                    "estimate": estimate,
                    "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                    "undefined_reason": reason,
                    "conditional_no_refit": True,
                    "protocol_id": PROTOCOL_ID,
                }
            )
        null_values[(encoder, "subject_mean_label_permutation")] = subject_null
        null_values[(encoder, "within_subject_coordinate_permutation")] = coordinate_null

    bootstrap_rows: list[dict[str, object]] = []
    bootstrap_values: dict[tuple[str, str, str], list[float]] = {
        (encoder, unit, metric): []
        for encoder in ("CONCH", "Virchow")
        for unit in units
        for metric in metrics
    }
    for replicate in range(BOOTSTRAP_REPLICATES):
        seed = SEED + 1 + replicate
        sampled = np.random.default_rng(seed).choice(
            unique_groups, size=len(unique_groups), replace=True
        )
        for encoder in ("CONCH", "Virchow"):
            for unit in units:
                frame = frames[(encoder, unit)]
                for metric in metrics:
                    estimate, reason = resampled_metric(frame, metric, sampled)
                    bootstrap_values[(encoder, unit, metric)].append(estimate)
                    bootstrap_rows.append(
                        {
                            "target_id": "tumor_fraction",
                            "encoder": encoder,
                            "analysis_unit": unit,
                            "replicate_id": replicate,
                            "bootstrap_seed": seed,
                            "metric_name": metric,
                            "estimate": estimate,
                            "replicate_status": "valid" if np.isfinite(estimate) else "undefined",
                            "undefined_reason": reason,
                            "protocol_id": PROTOCOL_ID,
                        }
                    )
    print("FM4 paired subject bootstraps and grouped permutations complete", flush=True)

    summary_rows: list[dict[str, object]] = []
    primary_indices: list[int] = []
    primary_p_values: list[float] = []
    for encoder in ("CONCH", "Virchow"):
        for unit in units:
            frame = frames[(encoder, unit)]
            for metric in metrics:
                estimate, reason = safe_metric(
                    metric, frame.truth.to_numpy(), frame.prediction.to_numpy()
                )
                if reason:
                    raise RuntimeError(f"observed {encoder}/{unit}/{metric} undefined: {reason}")
                distribution = np.asarray(
                    bootstrap_values[(encoder, unit, metric)], dtype=float
                )
                valid_bootstrap = distribution[np.isfinite(distribution)]
                null_type = ""
                p95 = empirical_p = np.nan
                gate: object = "not_primary_gate_metric"
                if metric == "spearman" and unit == "subject_mean":
                    null_type = "subject_mean_label_permutation"
                    null = np.asarray(null_values[(encoder, null_type)], dtype=float)
                    valid_null = null[np.isfinite(null)]
                    p95 = float(np.quantile(valid_null, 0.95))
                    empirical_p = float(
                        (1 + np.sum(valid_null >= estimate)) / (1 + len(valid_null))
                    )
                elif metric == "spearman" and unit == "tile_clustered_by_subject":
                    null_type = "within_subject_coordinate_permutation"
                    null = np.asarray(null_values[(encoder, null_type)], dtype=float)
                    valid_null = null[np.isfinite(null)]
                    p95 = float(np.quantile(valid_null, 0.95))
                    empirical_p = float(
                        (1 + np.sum(valid_null >= estimate)) / (1 + len(valid_null))
                    )
                summary_rows.append(
                    {
                        "family_id": (
                            "FM4-H1-TUMOR-SHARED"
                            if metric == "spearman" and unit == "subject_mean"
                            else "FM4-H1-TUMOR-SHARED-SECONDARY"
                        ),
                        "target_id": "tumor_fraction",
                        "target_role": "T2_descriptive_only_not_confirmatory",
                        "encoder": encoder,
                        "analysis_unit": unit,
                        "metric_name": metric,
                        "estimate": estimate,
                        "ci_low": float(np.quantile(valid_bootstrap, 0.025)),
                        "ci_high": float(np.quantile(valid_bootstrap, 0.975)),
                        "n_tiles": len(manifest),
                        "n_subjects": len(unique_groups),
                        "n_valid_bootstrap": len(valid_bootstrap),
                        "n_undefined_bootstrap": int((~np.isfinite(distribution)).sum()),
                        "permutation_null_type": null_type,
                        "permutation_p95": p95,
                        "empirical_p": empirical_p,
                        "empirical_q": np.nan,
                        "gate_exceedance": gate,
                        "claim_ceiling": CLAIM_CEILING,
                        "protocol_id": PROTOCOL_ID,
                    }
                )
                if metric == "spearman" and unit == "subject_mean":
                    primary_indices.append(len(summary_rows) - 1)
                    primary_p_values.append(empirical_p)
    for index, q_value in zip(primary_indices, bh_adjust(primary_p_values), strict=True):
        row = summary_rows[index]
        row["empirical_q"] = q_value
        row["gate_exceedance"] = bool(
            float(row["estimate"]) > float(row["permutation_p95"])
            and q_value < 0.05
        )

    delta_rows: list[dict[str, object]] = []
    for unit in units:
        for metric in metrics:
            conch, _ = safe_metric(
                metric,
                frames[("CONCH", unit)].truth,
                frames[("CONCH", unit)].prediction,
            )
            virchow, _ = safe_metric(
                metric,
                frames[("Virchow", unit)].truth,
                frames[("Virchow", unit)].prediction,
            )
            distribution = np.asarray(
                bootstrap_values[("CONCH", unit, metric)]
            ) - np.asarray(bootstrap_values[("Virchow", unit, metric)])
            valid = distribution[np.isfinite(distribution)]
            delta_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "analysis_unit": unit,
                    "metric_name": metric,
                    "conch_estimate": conch,
                    "virchow_estimate": virchow,
                    "paired_delta_conch_minus_virchow": conch - virchow,
                    "ci_low": float(np.quantile(valid, 0.025)),
                    "ci_high": float(np.quantile(valid, 0.975)),
                    "n_valid_bootstrap": len(valid),
                    "n_undefined_bootstrap": int((~np.isfinite(distribution)).sum()),
                    "interpretation": "descriptive_paired_delta_not_encoder_superiority",
                    "protocol_id": PROTOCOL_ID,
                }
            )

    capacity_oof_rows: list[dict[str, object]] = []
    capacity_rows: list[dict[str, object]] = []
    for encoder in ("CONCH", "Virchow"):
        capacity_prediction, capacity_alpha, _ = nested_oof(
            arrays[encoder], truth, folds, groups, rank=CAPACITY_RANK
        )
        for index, row in enumerate(manifest.itertuples(index=False)):
            capacity_oof_rows.append(
                {
                    "target_id": "tumor_fraction",
                    "encoder": encoder,
                    "configuration": f"fixed_rank_{CAPACITY_RANK}_pca_ridge",
                    "sample_id": row.sample_id,
                    "subject_id": row.subject_id,
                    "outer_fold": int(row.fold),
                    "truth": float(row.tumor_fraction),
                    "prediction": float(capacity_prediction[index]),
                    "selected_alpha": float(capacity_alpha[index]),
                    "pca_fit_scope": "within_each_training_split_only",
                    "outcome_role": "secondary_capacity_sensitivity_not_gate",
                    "protocol_id": PROTOCOL_ID,
                }
            )
        for unit in units:
            frame = analysis_frame(manifest, capacity_prediction, unit)
            for metric in metrics:
                estimate, reason = safe_metric(metric, frame.truth, frame.prediction)
                if reason:
                    raise RuntimeError(
                        f"capacity sensitivity {encoder}/{unit}/{metric} undefined: {reason}"
                    )
                primary = next(
                    row
                    for row in summary_rows
                    if row["encoder"] == encoder
                    and row["analysis_unit"] == unit
                    and row["metric_name"] == metric
                )
                capacity_rows.append(
                    {
                        "target_id": "tumor_fraction",
                        "encoder": encoder,
                        "analysis_unit": unit,
                        "metric_name": metric,
                        "primary_full_dimension": arrays[encoder].shape[1],
                        "sensitivity_rank": CAPACITY_RANK,
                        "primary_estimate": primary["estimate"],
                        "sensitivity_estimate": estimate,
                        "sensitivity_minus_primary": estimate - float(primary["estimate"]),
                        "direction_preserved": bool(
                            np.sign(estimate) == np.sign(float(primary["estimate"]))
                        ),
                        "outcome_role": "secondary_capacity_sensitivity_not_gate",
                        "protocol_id": PROTOCOL_ID,
                    }
                )
        print(f"FM4 {encoder} rank-{CAPACITY_RANK} capacity sensitivity complete", flush=True)

    passing = [
        row["encoder"]
        for row in summary_rows
        if row["analysis_unit"] == "subject_mean"
        and row["metric_name"] == "spearman"
        and row["gate_exceedance"] is True
    ]
    primary_by_encoder = {
        row["encoder"]: row
        for row in summary_rows
        if row["analysis_unit"] == "subject_mean"
        and row["metric_name"] == "spearman"
    }
    claim_rows = [
        {
            "claim_id": "FM4-C01",
            "claim": "tumor_fraction is internally recoverable from frozen representations",
            "status": "supported_descriptive" if passing else "not_supported",
            "evidence": "; ".join(
                f"{encoder}: rho={primary_by_encoder[encoder]['estimate']:.4f}, "
                f"95% CI [{primary_by_encoder[encoder]['ci_low']:.4f}, "
                f"{primary_by_encoder[encoder]['ci_high']:.4f}], "
                f"q={primary_by_encoder[encoder]['empirical_q']:.4g}"
                for encoder in ("CONCH", "Virchow")
            ),
            "allowed_wording": (
                "In this 25-subject internal exploratory analysis, tumor_fraction "
                "was recoverable above the grouped null for: " + ", ".join(passing)
            ),
            "prohibited_wording": (
                "confirmatory measurement validity; disease prediction/H2; clinical or PNI "
                "diagnosis; scanner/stain robustness; external transport; encoder superiority"
            ),
            "claim_ceiling": CLAIM_CEILING,
            "protocol_id": PROTOCOL_ID,
        }
    ]

    write_csv(output_dir / "fm4_oof_predictions.csv", oof_rows)
    write_csv(output_dir / "fm4_subject_predictions.csv", subject_rows)
    write_csv(output_dir / "fm4_summary.csv", summary_rows)
    write_csv(output_dir / "fm4_paired_deltas.csv", delta_rows)
    write_csv(output_dir / "fm4_permutation_null.csv", permutation_rows)
    write_csv(output_dir / "fm4_bootstrap_replicates.csv", bootstrap_rows)
    write_csv(output_dir / "fm4_fold_diagnostics.csv", fold_rows)
    write_csv(output_dir / "fm4_capacity_oof_predictions.csv", capacity_oof_rows)
    write_csv(output_dir / "fm4_capacity_sensitivity.csv", capacity_rows)
    write_csv(output_dir / "fm4_claim_evidence.csv", claim_rows)

    subject_delta = next(
        row
        for row in delta_rows
        if row["analysis_unit"] == "subject_mean" and row["metric_name"] == "spearman"
    )
    report = [
        "# FM4 concept benchmark report",
        "",
        "- Status: **PASS — approved exploratory/descriptive H1 benchmark complete**",
        f"- Protocol: `{PROTOCOL_ID}`",
        f"- Approval manifest: `{approval_manifest_hash}`",
        "- Scope: `tumor_fraction × CONCH/Virchow × shared 394.24 µm`",
        "- Cohort: 1,218 paired tiles / 25 subjects / five shared subject-grouped folds",
        "- Claim ceiling: internal descriptive recoverability only",
        "",
        "## Primary subject-level result",
        "",
        "| Encoder | OOF Spearman | 95% subject-bootstrap CI | Null p95 | p | BH q | Descriptive gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for encoder in ("CONCH", "Virchow"):
        row = primary_by_encoder[encoder]
        report.append(
            f"| {encoder} | {row['estimate']:.4f} | [{row['ci_low']:.4f}, "
            f"{row['ci_high']:.4f}] | {row['permutation_p95']:.4f} | "
            f"{row['empirical_p']:.4g} | {row['empirical_q']:.4g} | "
            f"{row['gate_exceedance']} |"
        )
    report.extend(
        [
            "",
            "## Paired cross-encoder description",
            "",
            f"Subject-mean Spearman Δ(CONCH−Virchow) was "
            f"{subject_delta['paired_delta_conch_minus_virchow']:.4f} "
            f"(95% paired subject-bootstrap CI {subject_delta['ci_low']:.4f} to "
            f"{subject_delta['ci_high']:.4f}). This is a descriptive paired contrast, "
            "not an encoder-superiority test.",
            "",
            "## Capacity sensitivity",
            "",
            f"A secondary fixed rank-{CAPACITY_RANK} PCA plus ridge analysis was fitted "
            "within training splits only. It does not alter the primary full-embedding gate.",
            "",
            "## Interpretation boundary",
            "",
            "The result can establish only that the descriptive tumor-fraction signal is "
            "decodable in this internal cohort. It does not establish measurement repeatability, "
            "disease prediction, functional utilization (H2), clinical or whole-slide PNI "
            "performance, scanner/stain robustness, external transport, or encoder superiority.",
        ]
    )
    (output_dir / "fm4-concept-benchmark-report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    config: dict[str, object] = {
        "schema_version": "fm4-benchmark-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started.isoformat(),
        "status": "complete_approved_exploratory_descriptive_h1",
        "execution_authorized": True,
        "protocol_id": PROTOCOL_ID,
        "approval": {
            "status": approval["status"],
            "approved_scope": approval["approved_scope"],
            "claim_ceiling": approval["claim_ceiling"],
            "manifest_sha256": approval_manifest_hash,
        },
        "seed": SEED,
        "counts": {
            "paired_tiles": len(manifest),
            "subjects": len(unique_groups),
            "outer_folds": 5,
            "encoders": 2,
            "targets": 1,
        },
        "methods": {
            "primary_probe": "StandardScaler plus Ridge(lsqr)",
            "alpha_grid": ALPHA_GRID.tolist(),
            "inner_tuning": "four preassigned training folds only; mean squared error",
            "primary_estimand": "subject_mean_oof_spearman",
            "permutation_replicates": PERMUTATION_REPLICATES,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "multiplicity": "BH-FDR across two primary encoder associations at 0.05",
            "capacity_sensitivity": f"training-fold-only PCA rank {CAPACITY_RANK} plus identical ridge grid",
        },
        "passing_encoders": passing,
        "source_hashes": {
            "paired_sample_manifest.csv": paired_manifest_hash,
            "embedding_bundle_manifest.csv": sha256(FM3 / "embedding_bundle_manifest.csv"),
            "embedding_row_manifest.csv": sha256(FM3 / "embedding_row_manifest.csv"),
            "fm4_shared_fold_manifest.csv": fold_manifest_hash,
            "fm4_scope_approval_manifest.json": approval_manifest_hash,
            "CONCH_embedding": bundle["CONCH"]["array_sha256"],
            "Virchow_embedding": bundle["Virchow"]["array_sha256"],
        },
        "output_hashes_excluding_run_config": {
            name: sha256(output_dir / name) for name in DETERMINISTIC_OUTPUTS
        },
        "clean_rerun": {"status": "not_requested"},
        "claim_ceiling": CLAIM_CEILING,
        "still_prohibited": approval["still_prohibited"],
    }
    (output_dir / "benchmark_run_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config


def run_with_clean_rerun(output_dir: Path) -> dict[str, object]:
    config = run_once(output_dir)
    with tempfile.TemporaryDirectory(prefix="fm4-clean-rerun-") as directory:
        rerun_dir = Path(directory)
        run_once(rerun_dir)
        comparison_rows: list[dict[str, object]] = []
        for name in DETERMINISTIC_OUTPUTS:
            first_hash = sha256(output_dir / name)
            rerun_hash = sha256(rerun_dir / name)
            comparison_rows.append(
                {
                    "output_file": name,
                    "reference_sha256": first_hash,
                    "clean_rerun_sha256": rerun_hash,
                    "exact_match": first_hash == rerun_hash,
                }
            )
        if not all(bool(row["exact_match"]) for row in comparison_rows):
            raise RuntimeError("FM4 clean rerun produced a deterministic output mismatch")
        write_csv(output_dir / "fm4_clean_rerun_comparison.csv", comparison_rows)
    config["clean_rerun"] = {
        "status": "pass",
        "deterministic_outputs_compared": len(DETERMINISTIC_OUTPUTS),
        "mismatch_count": 0,
    }
    hashes = dict(config["output_hashes_excluding_run_config"])
    hashes["fm4_clean_rerun_comparison.csv"] = sha256(
        output_dir / "fm4_clean_rerun_comparison.csv"
    )
    config["output_hashes_excluding_run_config"] = hashes
    (output_dir / "benchmark_run_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--clean-rerun", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = (
        run_with_clean_rerun(args.output_dir)
        if args.clean_rerun
        else run_once(args.output_dir)
    )
    print(
        json.dumps(
            {
                "status": config["status"],
                "passing_encoders": config["passing_encoders"],
                "clean_rerun": config["clean_rerun"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
