#!/usr/bin/env python3
"""Reproduce the frozen PRECISE PNI candidate-score audit.

This module treats the clinician review as immutable source data and fails closed on
candidate-universe or frozen-score reconciliation errors.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import beta
from sklearn.metrics import average_precision_score, roc_auc_score


LABEL_COLUMNS = ["nerve_present", "pni_present", "tumor_nerve_relation", "confidence"]
IDENTITY_COLUMNS = [
    "candidate_id",
    "review_order",
    "image_id",
    "x0",
    "y0",
    "window_px",
    "window_um",
]
SCORE_COLUMNS = [
    "prototype_score",
    "text_pni_score",
    "nerve_score",
    "prototype_score_pct",
    "text_pni_score_pct",
    "nerve_score_pct",
    "combined_score",
    "within_slide_pct",
]


class AuditIntegrityError(RuntimeError):
    """Raised when fixed audit inputs do not reconcile."""


def _event(
    check: str,
    status: str,
    severity: str,
    n_affected: int,
    details: str,
) -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "severity": severity,
        "n_affected": int(n_affected),
        "details": details,
    }


def normalize_review(review: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Return an analytic copy while retaining verbatim clinician-entered labels."""
    missing_columns = set(IDENTITY_COLUMNS + ["reviewer_id", *LABEL_COLUMNS, "notes"]) - set(
        review.columns
    )
    if missing_columns:
        raise AuditIntegrityError(f"Review is missing columns: {sorted(missing_columns)}")
    if review["candidate_id"].duplicated().any():
        raise AuditIntegrityError("Review candidate_id values are not unique")
    if review["review_order"].duplicated().any():
        raise AuditIntegrityError("Review order values are not unique")

    out = review.copy(deep=True)
    events: list[dict[str, Any]] = []
    out["reviewer_id"] = out["reviewer_id"].astype("string")
    reviewer_blank = out["reviewer_id"].isna() | out["reviewer_id"].str.strip().eq("")
    out.loc[reviewer_blank, "reviewer_id"] = "Song"
    events.append(
        _event(
            "derived_reviewer_id",
            "pass",
            "info",
            int(reviewer_blank.sum()),
            "Blank source reviewer_id populated as Song in normalized_review.csv only.",
        )
    )

    missing_total = 0
    missing_details = []
    for column in LABEL_COLUMNS:
        source_column = f"{column}_source"
        out[source_column] = out[column]
        text = out[column].astype("string")
        blank = text.isna() | text.str.strip().eq("")
        out[column] = text.str.strip().str.lower().mask(blank, pd.NA)
        count = int(blank.sum())
        missing_total += count
        if count:
            missing_details.append(f"{column}={count}")
    events.append(
        _event(
            "missing_outcome_fields",
            "warning" if missing_total else "pass",
            "warning" if missing_total else "info",
            missing_total,
            ", ".join(missing_details) if missing_details else "No missing outcome fields.",
        )
    )
    notes_text = out["notes"].astype("string")
    notes_blank = notes_text.isna() | notes_text.str.strip().eq("")
    events.append(
        _event(
            "missing_optional_notes",
            "noted",
            "info",
            int(notes_blank.sum()),
            "Optional notes blanks retained as missing; no negative label was inferred.",
        )
    )
    return out, events


def normalize_full_score_header(
    scores: pd.DataFrame, expected_image_ids: set[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Repair the known path-prefixed image_id header only after value reconciliation."""
    out = scores.copy(deep=True)
    if "image_id" in out.columns:
        return out, _event("full_score_image_id_header", "pass", "info", 0, "Header is image_id.")
    first = str(out.columns[0])
    if not first.endswith("image_id"):
        raise AuditIntegrityError(f"Full-score table has no image_id column; first header is {first!r}")
    observed = set(out.iloc[:, 0].dropna().astype(str))
    if not expected_image_ids.issubset(observed):
        missing = sorted(expected_image_ids - observed)
        raise AuditIntegrityError(
            f"Cannot repair malformed image_id header: manifest images absent from values: {missing}"
        )
    out = out.rename(columns={out.columns[0]: "image_id"})
    return out, _event(
        "full_score_image_id_header",
        "warning",
        "warning",
        1,
        f"Renamed path-prefixed first header {first!r} to image_id after value reconciliation.",
    )


def spatial_nms(scores: pd.DataFrame, distance_fraction: float = 0.75) -> pd.DataFrame:
    """Exactly reproduce the original greedy per-slide spatial NMS."""
    kept_parts: list[pd.DataFrame] = []
    for _, group in scores.groupby("image_id", sort=True):
        centers: list[tuple[float, float]] = []
        indices: list[int] = []
        for idx, row in group.sort_values("combined_score", ascending=False).iterrows():
            cx = float(row.x0 + row.window_px / 2)
            cy = float(row.y0 + row.window_px / 2)
            minimum = distance_fraction * float(row.window_px)
            if any(
                (cx - kept_x) ** 2 + (cy - kept_y) ** 2 < minimum**2
                for kept_x, kept_y in centers
            ):
                continue
            centers.append((cx, cy))
            indices.append(idx)
        kept_parts.append(scores.loc[indices])
    if not kept_parts:
        raise AuditIntegrityError("Full-score table contains no candidate groups")
    out = pd.concat(kept_parts, ignore_index=True)
    out["within_slide_pct"] = out.groupby("image_id")["combined_score"].rank(pct=True)
    out["nms_rank"] = out.groupby("image_id")["combined_score"].rank(
        ascending=False, method="first"
    ).astype(int)
    return out.sort_values(["image_id", "nms_rank"], kind="stable").reset_index(drop=True)


def validate_and_merge(
    review: pd.DataFrame, manifest: pd.DataFrame, nms: pd.DataFrame
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Reconcile review, manifest, and reconstructed NMS candidates or fail closed."""
    if manifest["candidate_id"].duplicated().any() or manifest["review_order"].duplicated().any():
        raise AuditIntegrityError("Manifest candidate_id/review_order values are not unique")
    if len(review) != len(manifest):
        raise AuditIntegrityError(f"Review/manifest row count differs: {len(review)} vs {len(manifest)}")

    review_manifest = review.merge(
        manifest,
        on="candidate_id",
        how="outer",
        suffixes=("_review", "_manifest"),
        validate="one_to_one",
        indicator=True,
    )
    if not review_manifest["_merge"].eq("both").all():
        raise AuditIntegrityError("Review and manifest candidate IDs do not match exactly")
    for column in IDENTITY_COLUMNS[1:]:
        left = review_manifest[f"{column}_review"]
        right = review_manifest[f"{column}_manifest"]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            equal = np.isclose(left.astype(float), right.astype(float), rtol=0.0, atol=1e-12)
        else:
            equal = left.astype("string").eq(right.astype("string")).fillna(False)
        if not bool(np.all(equal)):
            raise AuditIntegrityError(f"Review/manifest mismatch in {column}")

    keys = ["image_id", "x0", "y0", "window_px"]
    merged = manifest.merge(
        nms,
        on=keys,
        how="left",
        suffixes=("_manifest", "_nms"),
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise AuditIntegrityError("One or more reviewed manifest candidates are absent after NMS")
    for column in SCORE_COLUMNS:
        left = merged[f"{column}_manifest"]
        right = merged[f"{column}_nms"]
        if not np.allclose(left.astype(float), right.astype(float), rtol=0.0, atol=1e-12):
            raise AuditIntegrityError(f"Manifest/NMS mismatch in frozen column {column}")
    if "image_rank_manifest" in merged and "image_rank_nms" in merged:
        if not merged["image_rank_manifest"].astype(int).eq(merged["image_rank_nms"].astype(int)).all():
            raise AuditIntegrityError("Manifest/NMS mismatch in raw image_rank")

    expected_stratum = np.select(
        [
            merged["within_slide_pct_nms"] >= 0.70,
            (merged["within_slide_pct_nms"] >= 0.35)
            & (merged["within_slide_pct_nms"] <= 0.65),
            merged["within_slide_pct_nms"] <= 0.30,
        ],
        ["high", "mid", "low_random"],
        default="excluded",
    )
    if not np.all(expected_stratum == merged["selection_stratum"].astype(str).to_numpy()):
        raise AuditIntegrityError("Manifest selection_stratum does not match reconstructed NMS")

    audit = review.merge(manifest, on=IDENTITY_COLUMNS, how="inner", validate="one_to_one")
    audit = audit.merge(nms[keys + ["nms_rank"]], on=keys, how="left", validate="one_to_one")
    audit["subject_id"] = audit["image_id"].astype(str).str.rsplit("_", n=1).str[0]
    audit = audit.sort_values("review_order", kind="stable").reset_index(drop=True)
    events = [
        _event(
            "review_manifest_identity_geometry",
            "pass",
            "info",
            len(audit),
            "All reviewed candidate IDs, orders, slide IDs, coordinates, and windows match.",
        ),
        _event(
            "frozen_score_nms_reconstruction",
            "pass",
            "info",
            len(audit),
            "All reviewed candidates, frozen scores, raw ranks, strata, and NMS membership match.",
        ),
    ]
    return audit, events


def exact_binomial_ci(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval, undefined when there are no trials."""
    if trials == 0:
        return np.nan, np.nan
    low = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    high = (
        1.0
        if successes == trials
        else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    )
    return low, high


def _endpoint_masks(audit: pd.DataFrame, endpoint: str) -> tuple[pd.Series, pd.Series]:
    if endpoint == "nerve":
        evaluable = audit["nerve_present"].isin(["yes", "no"])
        positive = audit["nerve_present"].eq("yes")
    else:
        evaluable = audit["pni_present"].isin(["yes", "no"])
        if endpoint == "pni":
            positive = audit["pni_present"].eq("yes")
        elif endpoint == "pni_touching":
            positive = audit["pni_present"].eq("yes") & audit["tumor_nerve_relation"].eq(
                "touching"
            )
        elif endpoint == "pni_surrounding":
            positive = audit["pni_present"].eq("yes") & audit["tumor_nerve_relation"].eq(
                "surrounding"
            )
        else:
            raise ValueError(f"Unknown endpoint: {endpoint}")
    return evaluable, positive


def compute_budget_capture(
    audit: pd.DataFrame, nms: pd.DataFrame, max_k: int = 10
) -> pd.DataFrame:
    """Calculate known-positive capture and endpoint-specific review coverage."""
    keys = ["image_id", "x0", "y0", "window_px"]
    review_labels = audit[
        keys + ["nms_rank", "pni_present", "nerve_present", "tumor_nerve_relation"]
    ].copy()
    universe = nms.merge(
        review_labels.drop(columns="nms_rank"), on=keys, how="left", validate="one_to_one"
    )
    rows: list[dict[str, Any]] = []
    for endpoint in ["pni", "nerve", "pni_touching", "pni_surrounding"]:
        audit_evaluable, audit_positive = _endpoint_masks(audit, endpoint)
        total_positive = int((audit_evaluable & audit_positive).sum())
        universe_evaluable, universe_positive = _endpoint_masks(universe, endpoint)
        for k in range(1, max_k + 1):
            budget = universe["nms_rank"].le(k)
            captured = int((universe_evaluable & universe_positive & budget).sum())
            budget_count = int(budget.sum())
            evaluable_count = int((universe_evaluable & budget).sum())
            capture = captured / total_positive if total_positive else np.nan
            coverage = evaluable_count / budget_count if budget_count else np.nan
            precision = captured / budget_count if budget_count and evaluable_count == budget_count else np.nan
            ci_low, ci_high = exact_binomial_ci(captured, total_positive)
            rows.append(
                {
                    "endpoint": endpoint,
                    "k": k,
                    "captured_positive": captured,
                    "total_positive": total_positive,
                    "capture_fraction": capture,
                    "exact_ci_low": ci_low,
                    "exact_ci_high": ci_high,
                    "budget_candidate_count": budget_count,
                    "reviewed_candidate_count": int((budget & universe["pni_present"].notna()).sum()),
                    "evaluable_review_count": evaluable_count,
                    "review_coverage": coverage,
                    "top_k_precision": precision,
                }
            )
    return pd.DataFrame(rows)


SCORE_MAP = {
    "prototype": "prototype_score",
    "text_pni": "text_pni_score",
    "nerve": "nerve_score",
    "combined": "combined_score",
}

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REVIEW = ROOT / "resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv"
DEFAULT_MANIFEST = ROOT / "resources/data/shared/opendataset/PRECISE/pni_review_120_selection_manifest.csv"
DEFAULT_SCORES = ROOT / "resources/data/shared/opendataset/PRECISE/pni_candidate_full/all_candidate_scores.csv"
DEFAULT_CANDIDATE_CONFIG = ROOT / "resources/data/shared/opendataset/PRECISE/pni_candidate_full/run_config.json"
DEFAULT_BUILD_SUMMARY = ROOT / "resources/data/shared/opendataset/PRECISE/pni_review_120_build_summary.json"
DEFAULT_OUTPUT = ROOT / "resources/data/shared/opendataset/PRECISE/pni_frozen_score_audit"
DEFAULT_SEED = 20260805
DEFAULT_BOOTSTRAP = 10_000


def compute_score_metrics(audit: pd.DataFrame) -> pd.DataFrame:
    """Compute candidate-level discrimination within evaluable reviewed candidates only."""
    evaluable = audit["pni_present"].isin(["yes", "no"])
    data = audit.loc[evaluable]
    y = data["pni_present"].eq("yes").astype(int)
    rows = []
    for score_name, column in SCORE_MAP.items():
        for metric in ["roc_auc", "average_precision"]:
            if y.nunique() < 2:
                estimate = np.nan
                valid = False
                reason = "single_outcome_class"
            else:
                estimate = float(
                    roc_auc_score(y, data[column])
                    if metric == "roc_auc"
                    else average_precision_score(y, data[column])
                )
                valid = True
                reason = ""
            rows.append(
                {
                    "outcome": "pni_present",
                    "score": score_name,
                    "score_column": column,
                    "metric": metric,
                    "point_estimate": estimate,
                    "n_evaluable": len(data),
                    "n_positive": int(y.sum()),
                    "n_negative": int((1 - y).sum()),
                    "valid": valid,
                    "failure_reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _count_summary(group: pd.DataFrame, summary_type: str, name: str) -> dict[str, Any]:
    return {
        "summary_type": summary_type,
        "group": name,
        "reviewed_count": len(group),
        "evaluable_pni_count": int(group["pni_present"].isin(["yes", "no"]).sum()),
        "pni_positive_count": int(group["pni_present"].eq("yes").sum()),
        "evaluable_nerve_count": int(group["nerve_present"].isin(["yes", "no"]).sum()),
        "nerve_positive_count": int(group["nerve_present"].eq("yes").sum()),
        "touching_pni_count": int(
            (group["pni_present"].eq("yes") & group["tumor_nerve_relation"].eq("touching")).sum()
        ),
        "surrounding_pni_count": int(
            (
                group["pni_present"].eq("yes")
                & group["tumor_nerve_relation"].eq("surrounding")
            ).sum()
        ),
    }


def compute_subtype_and_stratum(audit: pd.DataFrame) -> pd.DataFrame:
    """Return deterministic stratum, subtype, slide, and subject count summaries."""
    rows: list[dict[str, Any]] = []
    for stratum in ["high", "mid", "low_random"]:
        rows.append(_count_summary(audit[audit["selection_stratum"].eq(stratum)], "stratum", stratum))
    for subtype in ["touching", "surrounding"]:
        subset = audit[audit["pni_present"].eq("yes") & audit["tumor_nerve_relation"].eq(subtype)]
        rows.append(_count_summary(subset, "pni_subtype", subtype))
    for image_id, group in audit.groupby("image_id", sort=True):
        rows.append(_count_summary(group, "slide", str(image_id)))
    for subject_id, group in audit.groupby("subject_id", sort=True):
        rows.append(_count_summary(group, "subject", str(subject_id)))
    return pd.DataFrame(rows)


def build_error_review(audit: pd.DataFrame) -> pd.DataFrame:
    """Select deterministic error-review cases without inferring histologic diagnoses."""
    records = []
    for _, row in audit.sort_values(["image_id", "nms_rank", "candidate_id"], kind="stable").iterrows():
        reasons = []
        if row["selection_stratum"] == "high" and row["pni_present"] == "no":
            reasons.append("high_ranked_pni_negative")
        if row["nerve_present"] == "yes" and row["pni_present"] == "no":
            reasons.append("nerve_positive_pni_negative")
        if row["pni_present"] == "yes" and int(row["nms_rank"]) > 1:
            reasons.append("confirmed_pni_below_top1_budget")
        if reasons:
            item = row.to_dict()
            item["error_review_reason"] = "|".join(reasons)
            records.append(item)
    preferred = [
        "candidate_id",
        "review_order",
        "subject_id",
        "image_id",
        "x0",
        "y0",
        "window_px",
        "window_um",
        "image_rank",
        "nms_rank",
        "selection_stratum",
        "nerve_present",
        "pni_present",
        "tumor_nerve_relation",
        "confidence",
        "notes",
        "prototype_score",
        "text_pni_score",
        "nerve_score",
        "combined_score",
        "tumor_fraction",
        "stroma_fraction",
        "labeled_fraction",
        "rgb_tissue_fraction",
        "error_review_reason",
    ]
    if not records:
        return pd.DataFrame(columns=[column for column in preferred if column in audit or column == "error_review_reason"])
    out = pd.DataFrame(records)
    return out[[column for column in preferred if column in out.columns]]


def cluster_bootstrap(
    audit: pd.DataFrame,
    seed: int,
    n_replicates: int,
    max_k: int = 10,
) -> pd.DataFrame:
    """Resample subjects and retain every capture/score replicate, including failures."""
    subjects = np.array(sorted(audit["subject_id"].astype(str).unique()))
    if len(subjects) == 0:
        raise AuditIntegrityError("No subjects available for cluster bootstrap")
    subject_index = {subject: index for index, subject in enumerate(subjects)}
    row_subject = audit["subject_id"].astype(str).map(subject_index).to_numpy()
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    endpoint_arrays = {}
    for endpoint in ["pni", "nerve", "pni_touching", "pni_surrounding"]:
        evaluable, positive = _endpoint_masks(audit, endpoint)
        endpoint_arrays[endpoint] = (evaluable.to_numpy(bool), positive.to_numpy(bool))
    pni_evaluable = audit["pni_present"].isin(["yes", "no"]).to_numpy(bool)
    y = audit["pni_present"].eq("yes").to_numpy(int)
    ranks = audit["nms_rank"].to_numpy(int)
    score_arrays = {name: audit[column].to_numpy(float) for name, column in SCORE_MAP.items()}

    for replicate_id in range(1, n_replicates + 1):
        draws = rng.integers(0, len(subjects), size=len(subjects))
        subject_weights = np.bincount(draws, minlength=len(subjects))
        weights = subject_weights[row_subject].astype(float)
        for endpoint, (evaluable, positive) in endpoint_arrays.items():
            denominator = int(np.sum(weights[evaluable & positive]))
            for k in range(1, max_k + 1):
                numerator = int(np.sum(weights[evaluable & positive & (ranks <= k)]))
                valid = denominator > 0
                rows.append(
                    {
                        "replicate_id": replicate_id,
                        "analysis_family": "capture",
                        "endpoint": endpoint,
                        "k": k,
                        "score": "",
                        "metric": "capture_fraction",
                        "estimate": numerator / denominator if valid else np.nan,
                        "numerator": numerator,
                        "denominator": denominator,
                        "valid": valid,
                        "failure_reason": "" if valid else "no_positive_outcomes",
                    }
                )

        metric_rows = pni_evaluable & (weights > 0)
        metric_y = y[metric_rows]
        metric_weights = weights[metric_rows]
        has_two_classes = len(np.unique(metric_y)) == 2
        for score_name, values in score_arrays.items():
            for metric in ["roc_auc", "average_precision"]:
                if has_two_classes:
                    estimate = float(
                        roc_auc_score(
                            metric_y, values[metric_rows], sample_weight=metric_weights
                        )
                        if metric == "roc_auc"
                        else average_precision_score(
                            metric_y, values[metric_rows], sample_weight=metric_weights
                        )
                    )
                    valid = True
                    reason = ""
                else:
                    estimate = np.nan
                    valid = False
                    reason = "single_outcome_class"
                rows.append(
                    {
                        "replicate_id": replicate_id,
                        "analysis_family": "score",
                        "endpoint": "pni_present",
                        "k": pd.NA,
                        "score": score_name,
                        "metric": metric,
                        "estimate": estimate,
                        "numerator": pd.NA,
                        "denominator": int(np.sum(metric_weights)),
                        "valid": valid,
                        "failure_reason": reason,
                    }
                )
    return pd.DataFrame(rows)


def _bootstrap_fields(group: pd.DataFrame, requested: int) -> dict[str, Any]:
    valid = group["valid"].astype(bool) & group["estimate"].notna()
    values = group.loc[valid, "estimate"].astype(float)
    n_valid = int(valid.sum())
    n_undefined = int(requested - n_valid)
    return {
        "bootstrap_ci_low": float(values.quantile(0.025)) if n_valid else np.nan,
        "bootstrap_ci_high": float(values.quantile(0.975)) if n_valid else np.nan,
        "n_bootstrap_requested": int(requested),
        "n_bootstrap_valid": n_valid,
        "n_bootstrap_undefined": n_undefined,
        "bootstrap_undefined_fraction": n_undefined / requested if requested else np.nan,
    }


def attach_bootstrap_summary(
    budget: pd.DataFrame,
    scores: pd.DataFrame,
    replicates: pd.DataFrame,
    n_requested: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach percentile intervals and explicit valid/undefined replicate accounting."""
    budget_out = budget.copy()
    budget_fields = []
    capture_reps = replicates[replicates["analysis_family"].eq("capture")]
    for row in budget_out.itertuples(index=False):
        group = capture_reps[
            capture_reps["endpoint"].eq(row.endpoint)
            & capture_reps["k"].astype("Int64").eq(int(row.k))
        ]
        budget_fields.append(_bootstrap_fields(group, n_requested))
    budget_out = pd.concat([budget_out.reset_index(drop=True), pd.DataFrame(budget_fields)], axis=1)

    scores_out = scores.copy()
    score_fields = []
    score_reps = replicates[replicates["analysis_family"].eq("score")]
    for row in scores_out.itertuples(index=False):
        group = score_reps[
            score_reps["score"].eq(row.score) & score_reps["metric"].eq(row.metric)
        ]
        score_fields.append(_bootstrap_fields(group, n_requested))
    scores_out = pd.concat([scores_out.reset_index(drop=True), pd.DataFrame(score_fields)], axis=1)
    return budget_out, scores_out


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.15g", na_rep="")


def _validate_frozen_config(
    scores: pd.DataFrame, candidate_config: dict[str, Any]
) -> list[dict[str, Any]]:
    expected_weights = {"prototype": 0.5, "text_pni": 0.35, "nerve": 0.15}
    observed_weights = candidate_config.get("score_weights", {})
    if observed_weights != expected_weights:
        raise AuditIntegrityError(
            f"Frozen score weights differ: expected {expected_weights}, observed {observed_weights}"
        )
    if float(candidate_config.get("window_um", np.nan)) != 300.0:
        raise AuditIntegrityError("Frozen candidate configuration window_um is not 300.0")
    recomputed = (
        0.50 * scores["prototype_score_pct"]
        + 0.35 * scores["text_pni_score_pct"]
        + 0.15 * scores["nerve_score_pct"]
    )
    if not np.allclose(recomputed, scores["combined_score"], rtol=0.0, atol=1e-12):
        raise AuditIntegrityError("Full-score combined_score does not match frozen weights")
    return [
        _event(
            "frozen_configuration",
            "pass",
            "info",
            len(scores),
            "300 um window and 0.50/0.35/0.15 frozen combined-score formula verified.",
        )
    ]


def _plot_budget_from_csv(csv_path: Path, png_path: Path, pdf_path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/vlm-pathology-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = pd.read_csv(csv_path)
    labels = {
        "pni": "PNI",
        "nerve": "Nerve",
        "pni_touching": "PNI: touching",
        "pni_surrounding": "PNI: surrounding",
    }
    colors = {
        "pni": "#9b2226",
        "nerve": "#005f73",
        "pni_touching": "#ca6702",
        "pni_surrounding": "#6a4c93",
    }
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), constrained_layout=True)
    for endpoint in labels:
        group = data[data["endpoint"].eq(endpoint)].sort_values("k")
        axes[0].plot(
            group["k"], group["capture_fraction"], marker="o", linewidth=2,
            label=labels[endpoint], color=colors[endpoint],
        )
        axes[0].fill_between(
            group["k"].to_numpy(float),
            group["bootstrap_ci_low"].to_numpy(float),
            group["bootstrap_ci_high"].to_numpy(float),
            color=colors[endpoint], alpha=0.12,
        )
    pni = data[data["endpoint"].eq("pni")].sort_values("k")
    axes[1].plot(pni["k"], pni["review_coverage"], marker="o", color="#33415c", linewidth=2)
    axes[0].set(title="Observed focus capture after spatial NMS", xlabel="Candidates reviewed per slide (k)", ylabel="Captured fraction")
    axes[1].set(title="Evaluable PNI-label coverage of top-k universe", xlabel="Candidates per slide (k)", ylabel="Coverage")
    for axis in axes:
        axis.set_xticks(sorted(data["k"].unique()))
        axis.set_ylim(-0.03, 1.03)
        axis.grid(alpha=0.25)
    axes[0].legend(frameon=False, loc="lower right")
    fig.suptitle("PRECISE frozen candidate-ranker audit (reviewed positives only)")
    fig.savefig(png_path, dpi=220, metadata={"Software": "PRECISE frozen-score audit"})
    fig.savefig(
        pdf_path,
        metadata={"Creator": "PRECISE frozen-score audit", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def _plot_scores_from_csv(csv_path: Path, png_path: Path, pdf_path: Path) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/vlm-pathology-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = pd.read_csv(csv_path)
    data = data[data["pni_present"].isin(["yes", "no"])]
    score_items = [
        ("prototype_score", "Prototype"),
        ("text_pni_score", "Text-PNI"),
        ("nerve_score", "Nerve"),
        ("combined_score", "Frozen combined"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 7.2), constrained_layout=True)
    for axis, (column, title) in zip(axes.flat, score_items):
        negative = data.loc[data["pni_present"].eq("no"), column].dropna().to_numpy(float)
        positive = data.loc[data["pni_present"].eq("yes"), column].dropna().to_numpy(float)
        box = axis.boxplot(
            [negative, positive], tick_labels=[f"PNI no\n(n={len(negative)})", f"PNI yes\n(n={len(positive)})"],
            patch_artist=True, widths=0.55, showfliers=False,
        )
        for patch, color in zip(box["boxes"], ["#94a3b8", "#dc6b5f"]):
            patch.set_facecolor(color)
            patch.set_alpha(0.55)
        for position, values, color in [(1, negative, "#475569"), (2, positive, "#9b2226")]:
            offsets = np.linspace(-0.10, 0.10, len(values)) if len(values) > 1 else np.array([0.0])
            axis.scatter(position + offsets, values, s=14, alpha=0.65, color=color, zorder=3)
        axis.set_title(title)
        axis.set_ylabel(column)
        axis.grid(axis="y", alpha=0.22)
    fig.suptitle("Frozen scores in the stratified 120-candidate reviewed sample")
    fig.savefig(png_path, dpi=220, metadata={"Software": "PRECISE frozen-score audit"})
    fig.savefig(
        pdf_path,
        metadata={"Creator": "PRECISE frozen-score audit", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def _minimum_full_capture(budget: pd.DataFrame, endpoint: str) -> int | None:
    rows = budget[
        budget["endpoint"].eq(endpoint)
        & budget["total_positive"].gt(0)
        & budget["captured_positive"].eq(budget["total_positive"])
    ]
    return int(rows["k"].min()) if len(rows) else None


def _format_metric_table(scores: pd.DataFrame) -> str:
    lines = ["| Score | ROC-AUC (95% cluster bootstrap CI) | Average precision (95% CI) |", "|---|---:|---:|"]
    display = {"prototype": "Prototype", "text_pni": "Text-PNI", "nerve": "Nerve", "combined": "Frozen combined"}
    for score in ["prototype", "text_pni", "nerve", "combined"]:
        values = {}
        for metric in ["roc_auc", "average_precision"]:
            row = scores[(scores["score"].eq(score)) & (scores["metric"].eq(metric))].iloc[0]
            values[metric] = f"{row.point_estimate:.3f} ({row.bootstrap_ci_low:.3f}–{row.bootstrap_ci_high:.3f})"
        lines.append(f"| {display[score]} | {values['roc_auc']} | {values['average_precision']} |")
    return "\n".join(lines)


def _write_report(
    path: Path,
    audit: pd.DataFrame,
    nms: pd.DataFrame,
    budget: pd.DataFrame,
    scores: pd.DataFrame,
    strata: pd.DataFrame,
) -> None:
    pni = audit[audit["pni_present"].eq("yes")]
    nerve = audit[audit["nerve_present"].eq("yes")]
    pni_k = _minimum_full_capture(budget, "pni")
    nerve_k = _minimum_full_capture(budget, "nerve")
    pni_full = budget[(budget["endpoint"].eq("pni")) & (budget["k"].eq(pni_k))].iloc[0]
    pni_rows = budget[budget["endpoint"].eq("pni")].sort_values("k")
    coverage_lines = ["| k | Captured PNI | Evaluable-label coverage | Top-k precision |", "|---:|---:|---:|---:|"]
    for row in pni_rows.itertuples(index=False):
        precision = "not calculated" if pd.isna(row.top_k_precision) else f"{row.top_k_precision:.3f}"
        coverage_lines.append(
            f"| {int(row.k)} | {int(row.captured_positive)}/{int(row.total_positive)} | {row.review_coverage:.3f} ({int(row.evaluable_review_count)}/{int(row.budget_candidate_count)}) | {precision} |"
        )
    score_undefined = scores[["score", "metric", "n_bootstrap_undefined", "n_bootstrap_requested"]]
    failure_lines = ["| Score | Metric | Undefined replicates |", "|---|---|---:|"]
    for row in score_undefined.itertuples(index=False):
        failure_lines.append(
            f"| {row.score} | {row.metric} | {int(row.n_bootstrap_undefined)}/{int(row.n_bootstrap_requested)} ({row.n_bootstrap_undefined/row.n_bootstrap_requested:.2%}) |"
        )
    capture_failure_lines = ["| Capture endpoint | Undefined replicates |", "|---|---:|"]
    for endpoint in ["pni", "nerve", "pni_touching", "pni_surrounding"]:
        row = budget[(budget["endpoint"].eq(endpoint)) & (budget["k"].eq(1))].iloc[0]
        capture_failure_lines.append(
            f"| {endpoint} | {int(row.n_bootstrap_undefined)}/{int(row.n_bootstrap_requested)} ({row.bootstrap_undefined_fraction:.2%}) |"
        )
    stratum_rows = strata[strata["summary_type"].eq("stratum")]
    stratum_lines = ["| Stratum | Reviewed | PNI | Nerve |", "|---|---:|---:|---:|"]
    for name in ["high", "mid", "low_random"]:
        row = stratum_rows[stratum_rows["group"].eq(name)].iloc[0]
        stratum_lines.append(
            f"| {name} | {int(row.reviewed_count)} | {int(row.pni_positive_count)} | {int(row.nerve_positive_count)} |"
        )
    report = f"""# PRECISE PNI Frozen-Score Audit Results

## Scope and integrity

This is a retrospective technical audit of candidate triage, not a whole-slide PNI diagnostic-performance or prognostic study. The fixed audit contained {len(audit)} blinded, stratified reviewed candidates from {audit.image_id.nunique()} slides and {audit.subject_id.nunique()} subjects. Exact reconstruction retained {len(nms)} spatially non-overlapping candidates from the full frozen candidate universe.

All candidate identities, slide identifiers, coordinates, 300 µm windows, frozen score components, raw slide ranks, selection strata, and NMS membership reconciled. The clinician source file remained byte-identical. Missing outcome labels were kept missing rather than changed to negative; counts are in `data_integrity_report.csv`.

## Observed focus capture

There were {len(pni)} pathologist-confirmed PNI candidates and {len(nerve)} nerve-positive candidates. The PNI subtypes were {(pni.tumor_nerve_relation == 'touching').sum()} touching and {(pni.tumor_nerve_relation == 'surrounding').sum()} surrounding.

After reproducing spatial NMS and re-ranking retained candidates, all {len(pni)} observed PNI foci were included by k={pni_k} candidates per slide ({int(pni_full.captured_positive)}/{int(pni_full.total_positive)}; exact binomial 95% CI {pni_full.exact_ci_low:.3f}–{pni_full.exact_ci_high:.3f}). All observed nerve-positive foci were included by k={nerve_k}. These are capture fractions among confirmed positives in the selected review sample, not whole-slide sensitivity.

The confirmed PNI raw pre-NMS `image_rank` values were {sorted(pni.image_rank.astype(int).tolist())}; the post-NMS `nms_rank` values were {sorted(pni.nms_rank.astype(int).tolist())}. Thus the retrospectively noticed raw top-4 pattern and the post-NMS k={pni_k} capture result are distinct descriptive observations based on seven foci; neither is a prespecified clinical threshold, and both require independent validation.

### Review coverage and precision guard

{chr(10).join(coverage_lines)}

Unreviewed top-k candidates were never treated as negative. Top-k precision is not calculated unless every candidate in that budget has an evaluable PNI label.

## Strata and subtypes

{chr(10).join(stratum_lines)}

Touching and surrounding capture curves are reported separately in `review_budget_capture.csv` and the capture figure. Slide- and subject-level reviewed/PNI/nerve counts are in `subtype_and_stratum_summary.csv`.

## Frozen score discrimination in the reviewed sample

{_format_metric_table(scores)}

These ROC-AUC and average-precision estimates apply only to the stratified 120-candidate audit sample. They do not estimate population-wide or whole-slide diagnostic performance.

## Bootstrap failure accounting

{chr(10).join(failure_lines)}

{chr(10).join(capture_failure_lines)}

Every subject-cluster bootstrap replicate is retained in `cluster_bootstrap_replicates.csv`. Undefined estimates arise when a resample contains a single outcome class (or, for subtype capture, no positive outcome); they were not silently dropped from failure accounting.

## Error review

`error_review_table.csv` lists high-stratum PNI-negative candidates, nerve-positive/PNI-negative candidates, and confirmed PNI below the top-1 post-NMS budget. Categories use only review labels and notes; no new histologic diagnosis was invented.

## Interpretation and limitations

In the stratified, blinded 120-candidate PRECISE review sample, all seven pathologist-confirmed PNI foci occurred in the high-ranked stratum, and the frozen candidate ranker concentrated the observed foci within a small per-slide review budget.

This audit cannot establish that the model has 100% PNI sensitivity, that any fixed number of candidates is sufficient for clinical diagnosis, that unreviewed regions contain no PNI, that PRECISE PNI prevalence is known, or that the observed budget generalizes externally. Selection into high/mid/low-random strata changes the candidate distribution, only seven positives were observed, and cluster bootstrap addresses sampling variability within this selected audit rather than selection bias.

## Reproducible artifacts

Every numeric result above is traceable to the saved CSV files. `run_config.json` records fixed seeds, input/output SHA256 hashes, execution time, environment, and software versions. Both figures are regenerated by the single entry point from the already-saved CSVs.
"""
    path.write_text(report, encoding="utf-8", newline="\n")


def run_audit(
    output_dir: Path = DEFAULT_OUTPUT,
    review: Path = DEFAULT_REVIEW,
    manifest: Path = DEFAULT_MANIFEST,
    scores: Path = DEFAULT_SCORES,
    candidate_config: Path = DEFAULT_CANDIDATE_CONFIG,
    build_summary: Path = DEFAULT_BUILD_SUMMARY,
    seed: int = DEFAULT_SEED,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    max_k: int = 10,
) -> dict[str, Any]:
    """Validate fixed inputs and regenerate every audit artifact."""
    output_dir = Path(output_dir)
    input_paths = {
        "clinician_review": Path(review),
        "selection_manifest": Path(manifest),
        "all_candidate_scores": Path(scores),
        "candidate_run_config": Path(candidate_config),
        "review_build_summary": Path(build_summary),
    }
    input_hashes = {name: sha256_file(path) for name, path in input_paths.items()}
    source_hash_before = input_hashes["clinician_review"]

    raw_review = pd.read_csv(input_paths["clinician_review"], keep_default_na=True)
    manifest_frame = pd.read_csv(input_paths["selection_manifest"])
    raw_scores = pd.read_csv(input_paths["all_candidate_scores"])
    candidate_configuration = json.loads(input_paths["candidate_run_config"].read_text())
    review_build = json.loads(input_paths["review_build_summary"].read_text())

    normalized, integrity = normalize_review(raw_review)
    score_frame, header_event = normalize_full_score_header(
        raw_scores, set(manifest_frame["image_id"].astype(str))
    )
    integrity.append(header_event)
    integrity.extend(_validate_frozen_config(score_frame, candidate_configuration))
    if int(review_build.get("n_total", -1)) != len(manifest_frame):
        raise AuditIntegrityError("Review build-summary n_total does not match manifest")
    integrity.append(
        _event(
            "review_build_summary",
            "pass",
            "info",
            len(manifest_frame),
            f"Manifest count matches build summary; selection seed={review_build.get('seed')}.",
        )
    )
    nms = spatial_nms(score_frame)
    audit, reconciliation_events = validate_and_merge(normalized, manifest_frame, nms)
    integrity.extend(reconciliation_events)
    integrity.append(
        _event(
            "candidate_universe_counts",
            "pass",
            "info",
            len(score_frame),
            f"Full candidates={len(score_frame)}, NMS retained={len(nms)}, slides={nms.image_id.nunique()}.",
        )
    )
    source_hash_after = sha256_file(input_paths["clinician_review"])
    if source_hash_after != source_hash_before:
        raise AuditIntegrityError("Clinician source SHA256 changed during execution")
    integrity.append(
        _event(
            "clinician_source_sha256_unchanged",
            "pass",
            "info",
            1,
            f"SHA256 before=after={source_hash_after}.",
        )
    )

    budget = compute_budget_capture(audit, nms, max_k=max_k)
    score_summary = compute_score_metrics(audit)
    replicates = cluster_bootstrap(
        audit, seed=seed, n_replicates=n_bootstrap, max_k=max_k
    )
    budget, score_summary = attach_bootstrap_summary(
        budget, score_summary, replicates, n_bootstrap
    )
    subtype_stratum = compute_subtype_and_stratum(audit)
    error_review = build_error_review(audit)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_outputs = {
        "normalized_review.csv": normalized,
        "data_integrity_report.csv": pd.DataFrame(integrity),
        "candidate_audit_table.csv": audit,
        "review_budget_capture.csv": budget,
        "score_metric_summary.csv": score_summary,
        "cluster_bootstrap_replicates.csv": replicates,
        "subtype_and_stratum_summary.csv": subtype_stratum,
        "error_review_table.csv": error_review,
    }
    for filename, frame in csv_outputs.items():
        _write_csv(frame, output_dir / filename)

    _plot_budget_from_csv(
        output_dir / "review_budget_capture.csv",
        output_dir / "fig_review_budget_capture.png",
        output_dir / "fig_review_budget_capture.pdf",
    )
    _plot_scores_from_csv(
        output_dir / "candidate_audit_table.csv",
        output_dir / "fig_score_distributions.png",
        output_dir / "fig_score_distributions.pdf",
    )
    _write_report(
        output_dir / "RESULTS_REPORT.md", audit, nms, budget, score_summary, subtype_stratum
    )

    output_hashes = {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "run_config.json"
    }
    versions = {}
    for package in ["pandas", "numpy", "scipy", "scikit-learn", "matplotlib"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    run_configuration = {
        "audit_scope": "retrospective candidate-triage audit; not whole-slide diagnostic performance",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": int(seed),
        "cluster_bootstrap_replicates": int(n_bootstrap),
        "max_per_slide_budget": int(max_k),
        "nms_distance_fraction": 0.75,
        "subject_id_derivation": "image_id.rsplit('_', 1)[0]",
        "input_paths": {name: str(path.resolve()) for name, path in input_paths.items()},
        "input_sha256": input_hashes,
        "clinician_source_sha256_before": source_hash_before,
        "clinician_source_sha256_after": source_hash_after,
        "source_unchanged": source_hash_before == source_hash_after,
        "frozen_candidate_configuration": candidate_configuration,
        "review_build_summary": review_build,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "software_versions": versions,
            "git_repository": False,
            "git_note": "Workspace is not a valid Git repository; git init was not run.",
        },
        "output_sha256": output_hashes,
        "output_hash_note": "run_config.json excluded to avoid a self-referential hash.",
    }
    (output_dir / "run_config.json").write_text(
        json.dumps(run_configuration, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_configuration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--max-k", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = run_audit(
        output_dir=args.output_dir,
        seed=args.seed,
        n_bootstrap=args.bootstrap_replicates,
        max_k=args.max_k,
    )
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "bootstrap_replicates": config["cluster_bootstrap_replicates"],
                "source_unchanged": config["source_unchanged"],
                "outputs_hashed": len(config["output_sha256"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
