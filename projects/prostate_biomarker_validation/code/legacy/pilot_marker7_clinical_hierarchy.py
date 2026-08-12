"""Nested out-of-sample M0--M5 clinical hierarchy for marker 7.

M0 grade; M1 grade+age; M2 grade+PSA+pT stage; M3 M2+margin; M4 M3+site;
M5 M4+the externally trained marker-7 image score. Each row reports its own complete-case
cohort, missingness, 5-fold patient-disjoint C-index, and patient-bootstrap CI. M4 and M5 use
the same patients, so their paired delta is also bootstrapped.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from lifelines.utils import concordance_index
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_marker7_confounder_audit import build_cohort, load_extra_covariates, to_struct  # noqa: E402

N_SPLITS = 5
N_BOOT = 2000
SEED = 0
MODEL_SPECS = {
    "M0": ["gleason_sum"],
    "M1": ["gleason_sum", "age"],
    "M2": ["gleason_sum", "psa", "t_stage"],
    "M3": ["gleason_sum", "psa", "t_stage", "margin_positive"],
    "M4": ["gleason_sum", "psa", "t_stage", "margin_positive", "site"],
    "M5": ["gleason_sum", "psa", "t_stage", "margin_positive", "site", "marker7_risk"],
}


def make_cox_pipeline(columns):
    categorical = [column for column in columns if column == "site"]
    numeric = [column for column in columns if column != "site"]
    transformers = [("numeric", StandardScaler(), numeric)]
    if categorical:
        transformers.append(("site", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                             categorical))
    preprocess = ColumnTransformer(transformers)
    return make_pipeline(preprocess, CoxPHSurvivalAnalysis(alpha=1.0))


def outer_predictions(frame, columns):
    groups = frame["case_id"].to_numpy()
    y = to_struct(frame["event"].to_numpy(), frame["follow_up_y"].to_numpy())
    predictions = np.full(len(frame), np.nan)
    folds = np.full(len(frame), -1, dtype=int)
    splitter = GroupKFold(n_splits=N_SPLITS)
    for fold, (train, test) in enumerate(splitter.split(frame, frame["event"], groups)):
        model = make_cox_pipeline(columns)
        model.fit(frame.iloc[train][columns], y[train])
        predictions[test] = model.predict(frame.iloc[test][columns])
        folds[test] = fold
    return predictions, folds


def cindex(frame, predictions):
    return concordance_index(frame["follow_up_y"], -predictions, frame["event"])


def bootstrap_metric(frame, prediction_columns, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    values = {column: [] for column in prediction_columns}
    for _ in range(n_boot):
        sample = frame.iloc[rng.integers(0, len(frame), len(frame))]
        for column in prediction_columns:
            try:
                values[column].append(cindex(sample, sample[column]))
            except ZeroDivisionError:
                pass
    return {column: np.asarray(metric) for column, metric in values.items()}


def main():
    cohort = build_cohort().merge(load_extra_covariates(), on="case_id", how="left")
    cohort["site"] = cohort["case_id"].str.split("-").str[1]
    summary_rows, prediction_frames, missingness_rows = [], [], []

    for model_name, columns in MODEL_SPECS.items():
        for column in columns:
            missingness_rows.append({
                "model": model_name, "covariate": column,
                "n_total": len(cohort), "n_missing": int(cohort[column].isna().sum()),
                "missing_fraction": float(cohort[column].isna().mean()),
            })
        required = ["case_id", "event", "follow_up_y"] + columns
        frame = cohort.dropna(subset=required).reset_index(drop=True).copy()
        predictions, folds = outer_predictions(frame, columns)
        frame["prediction"] = predictions
        frame["fold"] = folds
        frame["model"] = model_name
        boot = bootstrap_metric(frame, ["prediction"])["prediction"]
        estimate = cindex(frame, predictions)
        summary_rows.append({
            "model": model_name, "covariates": "+".join(columns), "n": len(frame),
            "events": int(frame["event"].sum()), "c_index": estimate,
            "ci_low": np.percentile(boot, 2.5), "ci_high": np.percentile(boot, 97.5),
            "regularization": "CoxPH alpha=1.0",
        })
        prediction_frames.append(frame[["case_id", "event", "follow_up_y", "model",
                                        "fold", "prediction"]])

    # Paired M4/M5 comparison on their identical complete-case cohort.
    predictions = pd.concat(prediction_frames, ignore_index=True)
    paired = predictions[predictions["model"].isin(["M4", "M5"])].pivot(
        index=["case_id", "event", "follow_up_y"], columns="model", values="prediction").reset_index()
    paired = paired.rename(columns={"M4": "m4_prediction", "M5": "m5_prediction"})
    boot = bootstrap_metric(paired, ["m4_prediction", "m5_prediction"])
    # Use identical bootstrap indices for a paired delta, rather than subtracting independent draws.
    rng = np.random.default_rng(SEED)
    deltas = []
    for _ in range(N_BOOT):
        sample = paired.iloc[rng.integers(0, len(paired), len(paired))]
        try:
            deltas.append(cindex(sample, sample["m5_prediction"]) -
                          cindex(sample, sample["m4_prediction"]))
        except ZeroDivisionError:
            pass
    deltas = np.asarray(deltas)
    delta_row = pd.DataFrame([{
        "comparison": "M5-M4", "n": len(paired), "events": int(paired["event"].sum()),
        "delta_c_index": cindex(paired, paired["m5_prediction"]) -
                         cindex(paired, paired["m4_prediction"]),
        "ci_low": np.percentile(deltas, 2.5), "ci_high": np.percentile(deltas, 97.5),
    }])

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_summary.csv"), index=False)
    pd.DataFrame(missingness_rows).to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_missingness.csv"), index=False)
    predictions.to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_predictions.csv"), index=False)
    delta_row.to_csv(
        os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/marker7_clinical_hierarchy_delta.csv"), index=False)
    print(summary.to_string(index=False))
    print(delta_row.to_string(index=False))


if __name__ == "__main__":
    main()
