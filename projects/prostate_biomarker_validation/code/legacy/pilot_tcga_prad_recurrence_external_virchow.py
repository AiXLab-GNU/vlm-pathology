"""Virchow cross-encoder check for the marker-7 external validation (2026-07-31): CONCH's
LEOPARD-fitted recurrence model transferred zero-shot to TCGA-PRAD with C-index=0.673
(pilot_tcga_prad_recurrence_external.py). Before trusting that as a general finding rather
than a CONCH-specific fluke, repeat with Virchow -- same discipline as the LEOPARD in-cohort
signal's own CONCH-vs-Virchow cross-check (docs/03_experimental_results.md §6d).

Reuses existing Virchow embeddings for both cohorts (no new GPU work):
  - LEOPARD: resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache/X.npy (508 slides, 2560-dim)
  - TCGA-PRAD: resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/X_spop.npy (300 slides, 2560-dim) -- same
    underlying tile embeddings as the SPOP experiment, label-agnostic, safe to reuse for any
    TCGA-PRAD analysis on this slide set.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_recurrence_external_virchow.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc
from scipy import stats

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
LEOPARD_V_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache")
TCGA_V_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache")
BCR_CSV = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr.csv")


def to_struct(e, t):
    return np.array(list(zip(e.astype(bool), t)), dtype=[("event", bool), ("time", float)])


def load_tcga_patient_level_virchow():
    X = np.load(os.path.join(TCGA_V_CACHE, "X_spop.npy"))
    meta = pd.read_csv(os.path.join(TCGA_V_CACHE, "meta_spop.csv"))
    bcr = pd.read_csv(BCR_CSV)

    df = pd.DataFrame(X)
    df["case_id"] = meta["case_id"].values
    patient_X = df.groupby("case_id").mean().values
    patient_ids = df.groupby("case_id").mean().index.values

    patient_df = pd.DataFrame({"case_id": patient_ids}).merge(bcr, on="case_id", how="inner")
    id_to_idx = {cid: i for i, cid in enumerate(patient_ids)}
    idx = [id_to_idx[cid] for cid in patient_df["case_id"]]
    return patient_X[idx], patient_df["event"].values, patient_df["follow_up_y"].values


def main():
    Xt, event_t, time_t = load_tcga_patient_level_virchow()
    print(f"TCGA-PRAD (Virchow) patient-level cohort: n={len(Xt)}, events={event_t.sum()}")

    Xl = np.load(os.path.join(LEOPARD_V_CACHE, "X.npy"))
    metal = pd.read_csv(os.path.join(LEOPARD_V_CACHE, "meta.csv"))
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

    print(f"\n(Virchow) Zero-shot LEOPARD->TCGA-PRAD: C-index={c_zeroshot:.3f}  td-AUROC@5y={td_auc:.3f}")

    for horizon in [3, 5]:
        known = (time_t >= horizon) | (event_t.astype(bool) & (time_t <= horizon))
        c_l = concordance_index_censored(event_t.astype(bool)[known], time_t[known], risk_t[known])[0]
        print(f"  landmark {horizon}y: n={known.sum()} C-index={c_l:.3f}")

    cens = event_t == 0
    rho_c, p_c = stats.spearmanr(risk_t[cens], time_t[cens])
    print(f"  censored-only risk vs follow_up: rho={rho_c:+.3f} p={p_c:.4g}")

    # cross-check against the CONCH zero-shot risk scores for the same patients
    sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
    from pilot_tcga_prad_recurrence_external import load_tcga_patient_level
    Xc, event_c, time_c, ids_c = load_tcga_patient_level()
    Xl_c = np.load(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/X.npy"))
    metal_c = pd.read_csv(os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/meta.csv"))
    sc_c = StandardScaler().fit(Xl_c)
    pca_c = PCA(n_components=8, random_state=0).fit(sc_c.transform(Xl_c))
    y_l_c = to_struct(metal_c["event"].values, metal_c["follow_up_years"].values)
    cox_c = CoxPHSurvivalAnalysis(alpha=1.0).fit(pca_c.transform(sc_c.transform(Xl_c)), y_l_c)
    risk_conch = cox_c.predict(pca_c.transform(sc_c.transform(Xc)))

    # match on ids: load_tcga_patient_level and load_tcga_patient_level_virchow both merge
    # bcr.csv the same way, but confirm ordering via ids_c vs the virchow patient ids
    meta_v = pd.read_csv(os.path.join(TCGA_V_CACHE, "meta_spop.csv"))
    bcr = pd.read_csv(BCR_CSV)
    vdf = pd.DataFrame(np.load(os.path.join(TCGA_V_CACHE, "X_spop.npy")))
    vdf["case_id"] = meta_v["case_id"].values
    v_ids = vdf.groupby("case_id").mean().index.values
    v_patient_df = pd.DataFrame({"case_id": v_ids}).merge(bcr, on="case_id", how="inner")
    common_ids = set(ids_c) & set(v_patient_df["case_id"])
    print(f"\n  n patients common to both CONCH and Virchow TCGA-PRAD scoring: {len(common_ids)}")
    conch_map = dict(zip(ids_c, risk_conch))
    virchow_map = dict(zip(v_patient_df["case_id"], risk_t))
    common_ids = sorted(common_ids)
    rc = np.array([conch_map[i] for i in common_ids])
    rv = np.array([virchow_map[i] for i in common_ids])
    rho, p = stats.spearmanr(rc, rv)
    print(f"  CONCH vs Virchow zero-shot risk score correlation (TCGA-PRAD, n={len(common_ids)}): "
          f"rho={rho:+.3f} p={p:.4g}")


if __name__ == "__main__":
    main()
