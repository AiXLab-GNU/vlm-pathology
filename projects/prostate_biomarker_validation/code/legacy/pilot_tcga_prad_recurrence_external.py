"""Marker 7 external validation (2026-07-31): does the LEOPARD-fitted in-cohort recurrence
model (docs/03_experimental_results.md §6d, C-index 0.60-0.66 on LEOPARD, cross-encoder
reproducible with Virchow) transfer zero-shot to a genuinely independent cohort -- TCGA-PRAD,
different institution mix, different specimen type (resection vs LEOPARD's prostatectomy too,
but different country/scanner/population), different (coarser) outcome definition?

Labels: `resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv`, rebuilt from the GDC clinical API
(`build_bcr_labels.py`) after the original file in that directory turned out to have no
traceable provenance and failed a spot check. IMPORTANT CAVEAT, carried through to any
reporting: TCGA-PRAD's GDC-harmonized data has no populated days_to_recurrence /
progression_or_recurrence fields for this cohort -- the event definition used here is
derived from `follow_ups.disease_response == "wt-with tumor"` (clinical assessment of
persistent/recurrent tumor at a follow-up visit), which is coarser than LEOPARD's explicit
PSA-based biochemical recurrence definition. Not the same outcome construct -- transfer
success/failure here speaks to "recurrence/persistence-related signal" transfer in a broad
sense, not a strict biochemical-recurrence replication.

Two tests, patient-level (270 overlapping patients, slide embeddings mean-pooled per patient
where multiple slides exist):
  (a) Zero-shot: LEOPARD-fitted PCA(8)+Cox coefficients (fixed, no TCGA-PRAD data used to fit)
      applied directly to TCGA-PRAD embeddings.
  (b) TCGA-PRAD-native in-cohort fit (same PCA-dim sweep + 5-fold CV recipe as
      pilot_leopard_direct_recurrence.py), to check whether TCGA-PRAD's own embeddings carry
      independently-learnable recurrence-related signal (same domain-shift-diagnostic logic).

2026-08-03 EXTENSION (external review, Tier-1 item 1.7): the zero-shot test above reported only
C-index and td-AUROC. Added here: integrated Brier score (IBS) and calibration slope, following
the same sksurv.metrics.integrated_brier_score / calibration-Cox-regression pattern used in
pilot_leopard_survival_3pool.py, plus the marker7_risk coefficient reported as a hazard ratio
(exp(coef)) with 95% CI, since Cox coefficients alone are less interpretable to clinical readers.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_recurrence_external.py
"""
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc, integrated_brier_score

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_leopard_direct_recurrence import cv_c_index, N_COMPONENTS_GRID  # noqa: E402

LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
BCR_CSV = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv")


def to_struct(e, t):
    return np.array(list(zip(e.astype(bool), t)), dtype=[("event", bool), ("time", float)])


def load_tcga_patient_level():
    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))
    bcr = pd.read_csv(BCR_CSV)

    df = pd.DataFrame(X)
    df["case_id"] = meta["case_id"].values
    patient_X = df.groupby("case_id").mean().values
    patient_ids = df.groupby("case_id").mean().index.values

    patient_df = pd.DataFrame({"case_id": patient_ids})
    patient_df = patient_df.merge(bcr, on="case_id", how="inner")
    keep_mask = patient_df["case_id"].isin(patient_ids)
    id_to_idx = {cid: i for i, cid in enumerate(patient_ids)}
    idx = [id_to_idx[cid] for cid in patient_df["case_id"]]
    return patient_X[idx], patient_df["event"].values, patient_df["follow_up_y"].values, patient_df["case_id"].values


def main():
    Xt, event_t, time_t, ids_t = load_tcga_patient_level()
    print(f"TCGA-PRAD patient-level cohort: n={len(Xt)}, events={event_t.sum()}")

    # (a) zero-shot: LEOPARD-fitted PCA(8)+Cox, fixed, no TCGA-PRAD data in the fit
    Xl = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    metal = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    event_l, time_l = metal["event"].values, metal["follow_up_years"].values

    sc = StandardScaler().fit(Xl)
    pca = PCA(n_components=8, random_state=0).fit(sc.transform(Xl))
    y_l = to_struct(event_l, time_l)
    cox = CoxPHSurvivalAnalysis(alpha=1.0).fit(pca.transform(sc.transform(Xl)), y_l)

    risk_t = cox.predict(pca.transform(sc.transform(Xt)))
    c_zeroshot = concordance_index_censored(event_t.astype(bool), time_t, risk_t)[0]
    y_t = to_struct(event_t, time_t)
    surv_fns = cox.predict_survival_function(pca.transform(sc.transform(Xt)))
    risk_at_5y = np.array([1 - fn(5.0) for fn in surv_fns])
    try:
        auc_t, _ = cumulative_dynamic_auc(y_l, y_t, risk_at_5y, [5.0])
        td_auc = auc_t[0]
    except ValueError as e:
        td_auc = float("nan")
        print(f"  [td-AUROC failed: {e}]")

    print(f"\n(a) Zero-shot LEOPARD->TCGA-PRAD: C-index={c_zeroshot:.3f}  td-AUROC@5y={td_auc:.3f}")

    # IBS: reuse surv_fns already computed above for risk_at_5y
    ibs_times = np.linspace(0.5, min(10.0, time_t.max() * 0.99), 50)
    surv_probs = np.array([[fn(t) for t in ibs_times] for fn in surv_fns])
    try:
        ibs = integrated_brier_score(y_l, y_t, surv_probs, ibs_times)
    except ValueError as e:
        ibs = float("nan")
        print(f"  [IBS failed: {e}]")

    # Calibration slope: Cox regression of event~time on the single zero-shot linear predictor
    calib_df = pd.DataFrame({"lp": risk_t, "time": time_t, "event": event_t})
    cph_calib = CoxPHFitter()
    cph_calib.fit(calib_df, duration_col="time", event_col="event")
    calib_slope = cph_calib.params_["lp"]

    # Hazard ratio for marker7_risk in a simple univariate Cox model (image-only), with 95% CI
    cph_hr = CoxPHFitter()
    cph_hr.fit(calib_df[["lp", "time", "event"]], duration_col="time", event_col="event")
    hr = np.exp(cph_hr.params_["lp"])
    hr_ci = np.exp(cph_hr.confidence_intervals_.loc["lp"].values)

    print(f"  IBS (0.5-{ibs_times[-1]:.1f}y)={ibs:.4f}  calibration slope={calib_slope:+.3f} "
          f"(1.0=perfect)  HR={hr:.3f} [{hr_ci[0]:.3f}, {hr_ci[1]:.3f}]")

    # (b) TCGA-PRAD-native in-cohort fit (domain-shift-diagnostic style, same recipe as LEOPARD)
    print(f"\n(b) TCGA-PRAD-native in-cohort CV (same recipe as LEOPARD domain-shift diagnostic):")
    print(f"{'n_components':>13s} {'C-index(OOF)':>13s} {'td-AUROC@5y':>13s}")
    for k in N_COMPONENTS_GRID:
        oof_risk, oof_surv = cv_c_index(Xt, event_t, time_t, k, seed=0)
        c = concordance_index_censored(event_t.astype(bool), time_t, oof_risk)[0]
        risk_h = np.array([1 - fn(5.0) for fn in oof_surv])
        try:
            auc_h, _ = cumulative_dynamic_auc(y_t, y_t, risk_h, [5.0])
            td = auc_h[0]
        except ValueError:
            td = float("nan")
        print(f"{k:13d} {c:13.3f} {td:13.3f}")


if __name__ == "__main__":
    main()
