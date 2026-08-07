"""Grade-stratified, fully refit permutation tests for the nested confounder audit.

Unlike the legacy fixed-score tests, PTEN and AR image probes are retrained for every
permutation using the same nested outer/inner folds as pilot_confounder_audit_nested.py.
For marker 7 the image score remains fixed because it was trained externally on LEOPARD;
the clinical and combined Cox models are refit in every outer fold after permuting paired
(event, follow-up time) outcomes within rounded Gleason-grade strata.
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np
import pandas as pd

from pilot_confounder_audit import load_data
from pilot_confounder_audit_nested import (
    aggregate_patients,
    audit_marker7,
    nested_tabular_predictions,
    outer_cox_predictions,
    tabular_metric,
    cindex,
)
from pilot_marker7_confounder_audit import build_cohort, load_extra_covariates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 0


def permute_patient_target(y, grade, groups, rng):
    """Permute a patient-level target within rounded patient-mean grade strata."""
    patient = pd.DataFrame({"case_id": groups, "target": y, "grade": grade}).groupby(
        "case_id", as_index=False).agg(target=("target", "mean"), grade=("grade", "mean"))
    patient["stratum"] = np.rint(patient["grade"]).astype(int)
    permuted = patient["target"].to_numpy(copy=True)
    for stratum, indices in patient.groupby("stratum").indices.items():
        del stratum
        indices = np.asarray(indices)
        if len(indices) > 1:
            permuted[indices] = rng.permutation(permuted[indices])
    mapping = dict(zip(patient["case_id"], permuted))
    return np.asarray([mapping[group] for group in groups])


def tabular_delta(X, clinical, y, groups, outcome_type):
    clinical_pred, image_pred, combined_pred, fold = nested_tabular_predictions(
        X, clinical, y, groups, outcome_type)
    patient = aggregate_patients(
        groups, y, fold, clinical_pred, image_pred, combined_pred)
    clinical_metric = tabular_metric(
        patient["target"].to_numpy(), patient["clinical_pred"].to_numpy(), outcome_type)
    combined_metric = tabular_metric(
        patient["target"].to_numpy(), patient["combined_pred"].to_numpy(), outcome_type)
    return combined_metric - clinical_metric


def run_tabular(X, meta, label_col, marker, outcome_type, n_perm, seed):
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].to_numpy(dtype=float)
    grade = meta.loc[mask, "gleason_sum"].to_numpy(dtype=float)
    groups = meta.loc[mask, "case_id"].to_numpy()
    features = X[mask.to_numpy()]
    observed = tabular_delta(features, grade, y, groups, outcome_type)
    rng = np.random.default_rng(seed)
    null = np.full(n_perm, np.nan)
    started = time.perf_counter()
    for permutation in range(n_perm):
        permuted_y = permute_patient_target(y, grade, groups, rng)
        try:
            null[permutation] = tabular_delta(
                features, grade, permuted_y, groups, outcome_type)
        except (ValueError, FloatingPointError):
            pass
        if (permutation + 1) % max(1, min(25, n_perm)) == 0:
            elapsed = time.perf_counter() - started
            print(f"{marker}: {permutation + 1}/{n_perm} permutations, {elapsed:.1f}s", flush=True)
    return observed, null, time.perf_counter() - started


def permute_survival_outcomes(cohort, rng):
    """Shuffle event/time pairs together within rounded grade strata."""
    out = cohort.copy()
    strata = np.rint(out["gleason_sum"]).astype(int).to_numpy()
    event = out["event"].to_numpy(copy=True)
    follow_up = out["follow_up_y"].to_numpy(copy=True)
    for stratum in np.unique(strata):
        indices = np.flatnonzero(strata == stratum)
        if len(indices) > 1:
            source = rng.permutation(indices)
            event[indices] = out["event"].to_numpy()[source]
            follow_up[indices] = out["follow_up_y"].to_numpy()[source]
    out["event"] = event
    out["follow_up_y"] = follow_up
    return out


def survival_delta(cohort, clinical_cols):
    clinical_pred, image_pred, combined_pred, fold = outer_cox_predictions(cohort, clinical_cols)
    frame = cohort.copy()
    frame["clinical_pred"] = clinical_pred
    frame["image_pred"] = image_pred
    frame["combined_pred"] = combined_pred
    frame["fold"] = fold
    return cindex(frame, "combined_pred") - cindex(frame, "clinical_pred")


def run_survival(cohort, analysis, clinical_cols, n_perm, seed):
    required = ["case_id", "event", "follow_up_y", "marker7_risk"] + clinical_cols
    cohort = cohort.dropna(subset=required).reset_index(drop=True)
    observed = survival_delta(cohort, clinical_cols)
    rng = np.random.default_rng(seed)
    null = np.full(n_perm, np.nan)
    started = time.perf_counter()
    for permutation in range(n_perm):
        permuted = permute_survival_outcomes(cohort, rng)
        try:
            null[permutation] = survival_delta(permuted, clinical_cols)
        except Exception as exc:  # Cox failures are retained as missing, never as zero evidence.
            print(f"marker7/{analysis}: permutation {permutation} failed: {exc}", flush=True)
        if (permutation + 1) % max(1, min(25, n_perm)) == 0:
            elapsed = time.perf_counter() - started
            print(f"marker7/{analysis}: {permutation + 1}/{n_perm} permutations, {elapsed:.1f}s",
                  flush=True)
    return observed, null, time.perf_counter() - started


def summarize(marker, analysis, metric, observed, null, elapsed):
    finite = null[np.isfinite(null)]
    p = (1 + np.sum(finite >= observed)) / (1 + len(finite))
    return {
        "marker": marker, "analysis": analysis, "metric": metric,
        "observed_delta": observed, "n_requested": len(null), "n_valid": len(finite),
        "null_mean": finite.mean(), "null_sd": finite.std(),
        "null_q025": np.percentile(finite, 2.5), "null_q975": np.percentile(finite, 97.5),
        "permutation_p_one_sided": p, "elapsed_seconds": elapsed,
        "seconds_per_permutation": elapsed / len(null),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-perm", type=int, default=200)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--suffix", default="pilot200")
    parser.add_argument(
        "--markers", nargs="+",
        choices=["pten", "ar", "marker7-grade", "marker7-full"],
        default=["pten", "ar", "marker7-grade", "marker7-full"],
    )
    return parser.parse_args()


def main():
    args = parse_args()
    X, meta = load_data()
    summaries, null_frames = [], []
    if "pten" in args.markers:
        result = run_tabular(X, meta, "pten_loss", "marker4_pten", "binary",
                             args.n_perm, args.seed)
        summaries.append(summarize("marker4_pten", "grade_only", "delta_AUROC", *result))
        null_frames.append(pd.DataFrame({"marker": "marker4_pten", "analysis": "grade_only",
                                         "permutation": np.arange(args.n_perm), "delta": result[1]}))
    if "ar" in args.markers:
        result = run_tabular(X, meta, "ar_score", "marker6_ar", "continuous",
                             args.n_perm, args.seed)
        summaries.append(summarize("marker6_ar", "grade_only", "delta_R2", *result))
        null_frames.append(pd.DataFrame({"marker": "marker6_ar", "analysis": "grade_only",
                                         "permutation": np.arange(args.n_perm), "delta": result[1]}))

    if "marker7-grade" in args.markers or "marker7-full" in args.markers:
        marker7 = build_cohort()
        survival_specs = []
        if "marker7-grade" in args.markers:
            survival_specs.append(("grade_only", marker7, ["gleason_sum"]))
        if "marker7-full" in args.markers:
            full = marker7.merge(load_extra_covariates(), on="case_id", how="left")
            survival_specs.append(("fully_adjusted", full,
                                   ["gleason_sum", "age", "t_stage", "psa", "margin_positive"]))
        for analysis, cohort, cols in survival_specs:
            result = run_survival(cohort, analysis, cols, args.n_perm, args.seed)
            summaries.append(summarize(
                "marker7_recurrence", analysis, "delta_C-index", *result))
            null_frames.append(pd.DataFrame({
                "marker": "marker7_recurrence", "analysis": analysis,
                "permutation": np.arange(args.n_perm), "delta": result[1]}))

    summary = pd.DataFrame(summaries)
    summary_path = os.path.join(ROOT, "models", f"confounder_refit_permutation_{args.suffix}_summary.csv")
    null_path = os.path.join(ROOT, "models", f"confounder_refit_permutation_{args.suffix}_null.csv")
    summary.to_csv(summary_path, index=False)
    pd.concat(null_frames, ignore_index=True).to_csv(null_path, index=False)
    print(summary.to_string(index=False))
    print(f"saved {summary_path}\nsaved {null_path}")


if __name__ == "__main__":
    main()
