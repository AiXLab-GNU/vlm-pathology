"""Systematic cross-model comparison for markers (1)/(4)/(6) on TCGA-PRAD: CONCH-alone vs
Virchow-alone vs fixed 50:50 z-score ensemble of the two models' predictions on the SAME 300
slides (verified identical file order between resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/X.npy and
resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/X_spop.npy -- the Virchow cache built for the SPOP experiment
reuses the identical corrected-resolution H&E tiles, so it's directly reusable here with no new
GPU work).

This follows the established small-sample fusion discipline (G-N6c lesson): fixed 50:50 average
of standardized (z-scored, per-fold) out-of-fold predictions, NOT a learned combiner -- learned
combiners were shown to be unstable at this patient scale (NADT n=39) and PANDA-scale evidence
showed learned combiners don't beat a fixed average anyway when there IS synergy, and actively
hurt when one component marker is locally weak.

Run with the CONCH-only venv (fast -- no embedding, just probe fits + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_virchow_tcga_prad_ensemble.py
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
CONCH_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
VIRCHOW_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")


def load_data():
    conch_meta = pd.read_csv(os.path.join(CONCH_CACHE, "meta.csv"))
    virchow_meta = pd.read_csv(os.path.join(VIRCHOW_CACHE, "meta_spop.csv"))
    assert (conch_meta["file_name"].values == virchow_meta["file_name"].values).all(), \
        "CONCH/Virchow slide order mismatch -- do not proceed without realigning"

    X_conch = np.load(os.path.join(CONCH_CACHE, "X.npy"))
    X_virchow = np.load(os.path.join(VIRCHOW_CACHE, "X_spop.npy"))

    by_attr = {}
    for d in json.load(open(CBIOPORTAL_SAMPLE_JSON)):
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    meta = conch_meta.copy()
    meta["gleason_sum"] = meta["case_id"].map(by_attr["REVIEWED_GLEASON_SUM"]).astype(float)
    pten_cna = meta["case_id"].map(by_attr["PTEN_CNA"])
    meta["pten_loss"] = pten_cna.isin(["hetloss", "homdel"]).astype(float)
    meta.loc[pten_cna.isna(), "pten_loss"] = np.nan
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)

    return X_conch, X_virchow, meta


def oof_regression(X, y, groups):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict(X[te])
    return oof


def oof_classification(X, y, groups):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]
    return oof


def zscore_by_fold(pred, groups, n_splits=5):
    """Standardize predictions using train-fold statistics only (avoids leakage), matching the
    G-N6c fixed-fusion recipe."""
    gkf = GroupKFold(n_splits=n_splits)
    z = np.full(len(pred), np.nan)
    dummy_y = np.zeros(len(pred))
    for tr, te in gkf.split(pred.reshape(-1, 1), dummy_y, groups):
        mu, sd = pred[tr].mean(), pred[tr].std()
        z[te] = (pred[te] - mu) / (sd + 1e-9)
    return z


def report_continuous(name, oof_c, oof_v, y, groups):
    print(f"\n{'='*80}\n{name} (continuous, Spearman rho)\n{'='*80}")
    rho_c, p_c = stats.spearmanr(oof_c, y)
    rho_v, p_v = stats.spearmanr(oof_v, y)
    z_c = zscore_by_fold(oof_c, groups)
    z_v = zscore_by_fold(oof_v, groups)
    ens = (z_c + z_v) / 2
    rho_e, p_e = stats.spearmanr(ens, y)
    print(f"CONCH only:   rho={rho_c:+.3f}  p={p_c:.4g}")
    print(f"Virchow only: rho={rho_v:+.3f}  p={p_v:.4g}")
    print(f"Fixed 50:50 ensemble: rho={rho_e:+.3f}  p={p_e:.4g}")


def report_binary(name, oof_c, oof_v, y, groups):
    print(f"\n{'='*80}\n{name} (binary, AUROC)\n{'='*80}")
    auroc_c = roc_auc_score(y, oof_c)
    auroc_v = roc_auc_score(y, oof_v)
    z_c = zscore_by_fold(oof_c, groups)
    z_v = zscore_by_fold(oof_v, groups)
    ens = (z_c + z_v) / 2
    auroc_e = roc_auc_score(y, ens)
    print(f"CONCH only:   AUROC={auroc_c:.3f}")
    print(f"Virchow only: AUROC={auroc_v:.3f}")
    print(f"Fixed 50:50 ensemble: AUROC={auroc_e:.3f}")


def main():
    X_conch, X_virchow, meta = load_data()
    groups_all = meta["case_id"].values

    # marker (1): Gleason score regression
    mask = meta["gleason_sum"].notna()
    y = meta.loc[mask, "gleason_sum"].values
    groups = groups_all[mask.values]
    oof_c = oof_regression(X_conch[mask.values], y, groups)
    oof_v = oof_regression(X_virchow[mask.values], y, groups)
    report_continuous("MARKER (1) H&E -> Gleason score (TCGA-PRAD, n=300)", oof_c, oof_v, y, groups)

    # marker (4): PTEN loss classification
    mask = meta["pten_loss"].notna()
    y = meta.loc[mask, "pten_loss"].astype(int).values
    groups = groups_all[mask.values]
    oof_c = oof_classification(X_conch[mask.values], y, groups)
    oof_v = oof_classification(X_virchow[mask.values], y, groups)
    report_binary("MARKER (4) H&E -> PTEN loss (TCGA-PRAD, n=300)", oof_c, oof_v, y, groups)

    # marker (6): AR score regression
    mask = meta["ar_score"].notna()
    y = meta.loc[mask, "ar_score"].values
    groups = groups_all[mask.values]
    oof_c = oof_regression(X_conch[mask.values], y, groups)
    oof_v = oof_regression(X_virchow[mask.values], y, groups)
    report_continuous("MARKER (6) H&E -> AR activity score (TCGA-PRAD, n=300)", oof_c, oof_v, y, groups)


if __name__ == "__main__":
    main()
