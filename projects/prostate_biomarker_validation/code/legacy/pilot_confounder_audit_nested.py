"""Nested cross-fitted incremental-value audit for markers 4, 6, and 7.

For PTEN and AR, every outer fold constructs the second-stage training feature from
inner-fold OOF image predictions and constructs the outer-test image feature from a probe
fit on the complete outer-training fold. Thus neither the image probe nor the clinical /
combined model sees an outer-test patient. Marker 7 is a LEOPARD-trained zero-shot score;
only its clinical and Cox combination coefficients are fit inside each outer fold.

Outputs (under resources/projects/prostate_biomarker_validation/model_workspace/):
  confounder_nested_summary.csv, confounder_nested_folds.csv,
  confounder_nested_bootstrap.csv, confounder_nested_predictions.csv
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_confounder_audit import load_data  # noqa: E402
from pilot_marker7_confounder_audit import build_cohort, load_extra_covariates  # noqa: E402

N_SPLITS = 5
N_BOOT = 2000
SEED = 0
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace")


def binary_model():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"),
    )


def continuous_model():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))


def nested_tabular_predictions(X, clinical, y, groups, outcome_type):
    """Return honest outer-OOF clinical, image, and combined predictions."""
    clinical = np.asarray(clinical, dtype=float)
    if clinical.ndim == 1:
        clinical = clinical[:, None]
    factory = binary_model if outcome_type == "binary" else continuous_model
    outer = GroupKFold(n_splits=N_SPLITS)
    pred_clin = np.full(len(y), np.nan)
    pred_img = np.full(len(y), np.nan)
    pred_comb = np.full(len(y), np.nan)
    fold_id = np.full(len(y), -1, dtype=int)

    for fold, (tr, te) in enumerate(outer.split(X, y, groups)):
        inner_score = np.full(len(tr), np.nan)
        inner = GroupKFold(n_splits=N_SPLITS)
        for inner_tr, inner_va in inner.split(X[tr], y[tr], groups[tr]):
            probe = factory()
            probe.fit(X[tr][inner_tr], y[tr][inner_tr])
            if outcome_type == "binary":
                inner_score[inner_va] = probe.predict_proba(X[tr][inner_va])[:, 1]
            else:
                inner_score[inner_va] = probe.predict(X[tr][inner_va])

        outer_probe = factory()
        outer_probe.fit(X[tr], y[tr])
        if outcome_type == "binary":
            test_score = outer_probe.predict_proba(X[te])[:, 1]
        else:
            test_score = outer_probe.predict(X[te])

        clinical_model = factory()
        clinical_model.fit(clinical[tr], y[tr])
        combined_model = factory()
        combined_model.fit(np.column_stack([clinical[tr], inner_score]), y[tr])

        if outcome_type == "binary":
            pred_clin[te] = clinical_model.predict_proba(clinical[te])[:, 1]
            pred_comb[te] = combined_model.predict_proba(
                np.column_stack([clinical[te], test_score]))[:, 1]
        else:
            pred_clin[te] = clinical_model.predict(clinical[te])
            pred_comb[te] = combined_model.predict(
                np.column_stack([clinical[te], test_score]))
        pred_img[te] = test_score
        fold_id[te] = fold

    return pred_clin, pred_img, pred_comb, fold_id


def aggregate_patients(groups, y, fold, clinical_pred, image_pred, combined_pred):
    frame = pd.DataFrame({
        "case_id": groups,
        "target": y,
        "fold": fold,
        "clinical_pred": clinical_pred,
        "image_pred": image_pred,
        "combined_pred": combined_pred,
    })
    return frame.groupby("case_id", as_index=False).agg(
        target=("target", "mean"), fold=("fold", "first"),
        clinical_pred=("clinical_pred", "mean"), image_pred=("image_pred", "mean"),
        combined_pred=("combined_pred", "mean"),
    )


def tabular_metric(y, pred, outcome_type):
    if outcome_type == "binary":
        return roc_auc_score(y.astype(int), pred)
    return r2_score(y, pred)


def bootstrap_tabular(patient, outcome_type, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    values = []
    n = len(patient)
    for _ in range(n_boot):
        sample = patient.iloc[rng.integers(0, n, n)]
        if outcome_type == "binary" and sample["target"].nunique() < 2:
            continue
        clinical = tabular_metric(sample["target"].values,
                                  sample["clinical_pred"].values, outcome_type)
        combined = tabular_metric(sample["target"].values,
                                  sample["combined_pred"].values, outcome_type)
        values.append(combined - clinical)
    return np.asarray(values)


def audit_tabular(X, meta, label_col, marker, outcome_type):
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].to_numpy(dtype=float)
    groups = meta.loc[mask, "case_id"].to_numpy()
    clinical = meta.loc[mask, "gleason_sum"].to_numpy(dtype=float)
    preds = nested_tabular_predictions(X[mask.to_numpy()], clinical, y, groups, outcome_type)
    clinical_pred, image_pred, combined_pred, fold = preds
    slide = pd.DataFrame({
        "case_id": groups, "target": y, "fold": fold,
        "clinical_pred": clinical_pred, "image_pred": image_pred,
        "combined_pred": combined_pred,
    })
    patient = aggregate_patients(groups, y, fold, clinical_pred, image_pred, combined_pred)
    patient["marker"] = marker
    patient["analysis"] = "grade_only"
    patient["scope"] = "patient"

    summaries, folds = [], []
    for scope, frame in (("slide", slide), ("patient", patient)):
        clin = tabular_metric(frame["target"].values, frame["clinical_pred"].values, outcome_type)
        img = tabular_metric(frame["target"].values, frame["image_pred"].values, outcome_type)
        comb = tabular_metric(frame["target"].values, frame["combined_pred"].values, outcome_type)
        summaries.append({"marker": marker, "analysis": "grade_only", "scope": scope,
                          "n": len(frame), "n_events": np.nan, "metric": "AUROC" if outcome_type == "binary" else "R2",
                          "clinical": clin, "image": img, "combined": comb,
                          "delta": comb - clin})
        for f, part in frame.groupby("fold"):
            if outcome_type == "binary" and part["target"].nunique() < 2:
                continue
            fclin = tabular_metric(part["target"].values, part["clinical_pred"].values, outcome_type)
            fcomb = tabular_metric(part["target"].values, part["combined_pred"].values, outcome_type)
            folds.append({"marker": marker, "analysis": "grade_only", "scope": scope,
                          "fold": f, "n": len(part), "clinical": fclin,
                          "combined": fcomb, "delta": fcomb - fclin})

    boot = bootstrap_tabular(patient, outcome_type)
    boot_frame = pd.DataFrame({"marker": marker, "analysis": "grade_only",
                               "bootstrap": np.arange(len(boot)), "delta": boot})
    patient_summary = next(r for r in summaries if r["scope"] == "patient")
    patient_summary["ci_low"], patient_summary["ci_high"] = np.percentile(boot, [2.5, 97.5])
    return summaries, folds, boot_frame, patient


def fit_cox_predict(train, test, covariates):
    scaler = StandardScaler().fit(train[covariates])
    tr = pd.DataFrame(scaler.transform(train[covariates]), columns=covariates, index=train.index)
    te = pd.DataFrame(scaler.transform(test[covariates]), columns=covariates, index=test.index)
    tr["time"] = train["follow_up_y"].values
    tr["event"] = train["event"].values
    model = CoxPHFitter().fit(tr, "time", "event", show_progress=False)
    return model.predict_log_partial_hazard(te).to_numpy()


def outer_cox_predictions(cohort, clinical_cols):
    cohort = cohort.reset_index(drop=True).copy()
    outer = GroupKFold(n_splits=N_SPLITS)
    groups = cohort["case_id"].to_numpy()
    dummy = cohort["event"].to_numpy()
    clinical_pred = np.full(len(cohort), np.nan)
    image_pred = np.full(len(cohort), np.nan)
    combined_pred = np.full(len(cohort), np.nan)
    fold_id = np.full(len(cohort), -1, dtype=int)
    for fold, (tr, te) in enumerate(outer.split(cohort, dummy, groups)):
        train, test = cohort.iloc[tr], cohort.iloc[te]
        clinical_pred[te] = fit_cox_predict(train, test, clinical_cols)
        image_pred[te] = fit_cox_predict(train, test, ["marker7_risk"])
        combined_pred[te] = fit_cox_predict(train, test, clinical_cols + ["marker7_risk"])
        fold_id[te] = fold
    return clinical_pred, image_pred, combined_pred, fold_id


def cindex(frame, pred_col):
    return concordance_index(frame["follow_up_y"], -frame[pred_col], frame["event"])


def bootstrap_survival(frame, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    values = []
    n = len(frame)
    for _ in range(n_boot):
        sample = frame.iloc[rng.integers(0, n, n)]
        try:
            values.append(cindex(sample, "combined_pred") - cindex(sample, "clinical_pred"))
        except ZeroDivisionError:
            continue
    return np.asarray(values)


def audit_marker7(cohort, analysis, clinical_cols):
    cols = ["case_id", "event", "follow_up_y", "marker7_risk"] + clinical_cols
    frame = cohort.dropna(subset=cols).reset_index(drop=True).copy()
    clinical_pred, image_pred, combined_pred, fold = outer_cox_predictions(frame, clinical_cols)
    frame["clinical_pred"] = clinical_pred
    frame["image_pred"] = image_pred
    frame["combined_pred"] = combined_pred
    frame["fold"] = fold
    frame["marker"] = "marker7_recurrence"
    frame["analysis"] = analysis
    frame["scope"] = "patient"
    clin, img, comb = cindex(frame, "clinical_pred"), cindex(frame, "image_pred"), cindex(frame, "combined_pred")
    summary = {"marker": "marker7_recurrence", "analysis": analysis, "scope": "patient",
               "n": len(frame), "n_events": int(frame["event"].sum()), "metric": "C-index",
               "clinical": clin, "image": img, "combined": comb, "delta": comb - clin}
    folds = []
    for f, part in frame.groupby("fold"):
        try:
            fclin, fcomb = cindex(part, "clinical_pred"), cindex(part, "combined_pred")
        except ZeroDivisionError:
            continue
        folds.append({"marker": "marker7_recurrence", "analysis": analysis, "scope": "patient",
                      "fold": f, "n": len(part), "clinical": fclin,
                      "combined": fcomb, "delta": fcomb - fclin})
    boot = bootstrap_survival(frame)
    summary["ci_low"], summary["ci_high"] = np.percentile(boot, [2.5, 97.5])
    boot_frame = pd.DataFrame({"marker": "marker7_recurrence", "analysis": analysis,
                               "bootstrap": np.arange(len(boot)), "delta": boot})
    return [summary], folds, boot_frame, frame


def main():
    X, meta = load_data()
    all_summary, all_folds, all_boot, all_predictions = [], [], [], []
    for args in ((X, meta, "pten_loss", "marker4_pten", "binary"),
                 (X, meta, "ar_score", "marker6_ar", "continuous")):
        summary, folds, boot, predictions = audit_tabular(*args)
        all_summary.extend(summary)
        all_folds.extend(folds)
        all_boot.append(boot)
        all_predictions.append(predictions)

    marker7 = build_cohort()
    analyses = [("grade_only", marker7, ["gleason_sum"])]
    full = marker7.merge(load_extra_covariates(), on="case_id", how="left")
    analyses.append(("fully_adjusted", full,
                     ["gleason_sum", "age", "t_stage", "psa", "margin_positive"]))
    for analysis, cohort, cols in analyses:
        summary, folds, boot, predictions = audit_marker7(cohort, analysis, cols)
        all_summary.extend(summary)
        all_folds.extend(folds)
        all_boot.append(boot)
        all_predictions.append(predictions)

    summary_df = pd.DataFrame(all_summary)
    for col in ("ci_low", "ci_high"):
        if col not in summary_df:
            summary_df[col] = np.nan
    summary_df.to_csv(os.path.join(OUT_DIR, "confounder_nested_summary.csv"), index=False)
    pd.DataFrame(all_folds).to_csv(os.path.join(OUT_DIR, "confounder_nested_folds.csv"), index=False)
    pd.concat(all_boot, ignore_index=True).to_csv(
        os.path.join(OUT_DIR, "confounder_nested_bootstrap.csv"), index=False)
    pd.concat(all_predictions, ignore_index=True, sort=False).to_csv(
        os.path.join(OUT_DIR, "confounder_nested_predictions.csv"), index=False)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
