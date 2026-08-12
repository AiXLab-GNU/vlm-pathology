"""G-N6c: does combining our two independently-validated NADT markers (CONCH-embedding Gleason
regressor, CONCH-embedding Phenotype classifier) beat the Gleason regressor alone?

Reuses cached embeddings from pilot_conch_nadt_probe.py (X.npy/meta.csv, 334 TUMOR slides) and
pilot_conch_nadt_phenotype.py (X_phenotype.npy/meta_phenotype.csv, 463 BENIGN/TUMOR slides) --
no re-embedding needed. Both markers' own out-of-fold (OOF) predictions are recomputed (fast,
just refitting linear probes on cached features) via the same patient-disjoint GroupKFold
discipline as before, then used as a 2-feature "verdict vector" for a meta-regressor predicting
Gleason total -- literal verdict fusion, not re-concatenating raw 512-dim embeddings.

Run with the CONCH-only venv (fast, no GPU/embedding needed):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_fusion.py
"""
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CACHE = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
SEED = 0
N_SPLITS = 5


def oof_predict(X, y, groups, classifier=False):
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    for tr_idx, te_idx in gkf.split(X, y, groups):
        if classifier:
            probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
            probe.fit(X[tr_idx], y[tr_idx])
            oof[te_idx] = probe.predict_proba(X[te_idx])[:, 1]
        else:
            probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
            probe.fit(X[tr_idx], y[tr_idx])
            oof[te_idx] = probe.predict(X[te_idx])
    return oof


def main():
    gleason_meta = pd.read_csv(os.path.join(CACHE, "meta.csv"))
    gleason_X = np.load(os.path.join(CACHE, "X.npy"))
    pheno_meta = pd.read_csv(os.path.join(CACHE, "meta_phenotype.csv"))
    pheno_X = np.load(os.path.join(CACHE, "X_phenotype.npy"))

    # marker 1: Gleason regressor OOF (baseline, already reported: rho=+0.312 slide / +0.478 patient)
    gleason_oof = oof_predict(gleason_X, gleason_meta["gleason_total"].values,
                               gleason_meta["patient_id"].values, classifier=False)

    # marker 2: Phenotype classifier OOF, computed on the full 463-slide set, then subset to
    # the TUMOR slides that overlap with the Gleason cohort
    pheno_oof_full = oof_predict(pheno_X, pheno_meta["label"].values,
                                  pheno_meta["patient_id"].values, classifier=True)
    pheno_meta = pheno_meta.assign(pheno_oof=pheno_oof_full)
    merged = gleason_meta.merge(
        pheno_meta[["file_name", "pheno_oof"]], on="file_name", how="left")
    print(f"gleason cohort: {len(gleason_meta)} slides; matched to phenotype OOF: "
          f"{merged['pheno_oof'].notna().sum()} slides")
    merged = merged.dropna(subset=["pheno_oof"])

    y = merged["gleason_total"].values
    groups = merged["patient_id"].values
    # merge with how='left' on gleason_meta preserves its original positional index, so this
    # correctly re-aligns gleason_oof (computed on the pre-merge gleason_meta row order)
    marker1 = gleason_oof[merged.index.values]
    marker2 = merged["pheno_oof"].values

    print(f"\n{'='*80}\nBASELINE: Gleason-probe alone (recomputed on matched subset, n={len(y)})\n{'='*80}")
    rho1, p1 = stats.spearmanr(marker1, y)
    print(f"Spearman(gleason_probe_oof, true gleason_total) = {rho1:+.3f}  p={p1:.4g}")

    print(f"\n{'='*80}\nFUSION: Gleason-probe + Phenotype-probe verdicts -> meta-regressor\n{'='*80}")
    X_fusion = np.column_stack([marker1, marker2])
    fusion_oof = oof_predict(X_fusion, y, groups, classifier=False)
    rho2, p2 = stats.spearmanr(fusion_oof, y)
    print(f"Spearman(fused_pred, true gleason_total) = {rho2:+.3f}  p={p2:.4g}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    print(f"Gleason-probe alone:        rho={rho1:+.3f}  p={p1:.4g}")
    print(f"Gleason-probe + Phenotype:  rho={rho2:+.3f}  p={p2:.4g}")
    print(f"delta rho = {rho2-rho1:+.3f}  ({'fusion helps' if rho2>rho1 else 'fusion does not help'})")

    # patient level too
    df_eval = pd.DataFrame(dict(patient_id=groups, marker1=marker1, fused=fusion_oof, true=y))
    pp = df_eval.groupby("patient_id").mean()
    rho1p, p1p = stats.spearmanr(pp["marker1"], pp["true"])
    rho2p, p2p = stats.spearmanr(pp["fused"], pp["true"])
    print(f"\npatient-level (n={len(pp)}):")
    print(f"Gleason-probe alone:        rho={rho1p:+.3f}  p={p1p:.4g}")
    print(f"Gleason-probe + Phenotype:  rho={rho2p:+.3f}  p={p2p:.4g}")


if __name__ == "__main__":
    main()
