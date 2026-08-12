"""External-institution validation of marker (2) (NADT Phenotype: BENIGN vs TUMOR, CONCH raw
embedding + LogisticRegression probe, AUROC 0.824 slide-level / rho +0.805 patient-level) on
PANDA. Same logic as pilot_conch_panda_external.py's marker (1) test, but reuses its cached
PANDA embeddings (resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache/X_panda.npy, meta_panda.csv, 1137 slides) directly --
NO new download or GPU embedding needed, since the tiling/embedding step is identical and
independent of which downstream label is being predicted.

PANDA label mapping: isup_grade==0 (benign, gleason_score '0+0' or 'negative') -> BENIGN (0),
isup_grade>=1 (any cancer grade) -> TUMOR (1). This is the natural PANDA equivalent of NADT's
Phenotype field.

Two tests, mirroring marker (1)'s PANDA validation exactly:
  (a) Zero-shot transfer: NADT-fitted phenotype probe (refit on ALL 463 NADT phenotype slides)
      applied to PANDA with zero retraining.
  (b) PANDA-native cross-institution refit: train on one provider's isup_grade-derived binary
      label, test on the other.

Run with the CONCH-only venv (fast -- no embedding, just probe fit + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_panda_phenotype_external.py
"""
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
PANDA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache")


def main():
    X_nadt = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
    y_nadt = meta_nadt["label"].values
    print(f"NADT phenotype training set: n={len(y_nadt)} slides "
          f"(tumor={y_nadt.sum()}, benign={(y_nadt==0).sum()})")

    X_panda = np.load(os.path.join(PANDA_CACHE, "X_panda.npy"))
    meta_panda = pd.read_csv(os.path.join(PANDA_CACHE, "meta_panda.csv"))
    y_panda = (meta_panda["isup_grade"].values >= 1).astype(int)
    providers = meta_panda["data_provider"].values
    print(f"PANDA eval set: n={len(y_panda)} slides (tumor={y_panda.sum()}, "
          f"benign={(y_panda==0).sum()})")

    # --- (a) zero-shot transfer: NADT-fitted probe, no PANDA training ---
    nadt_probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    nadt_probe.fit(X_nadt, y_nadt)
    pred_zeroshot = nadt_probe.predict_proba(X_panda)[:, 1]

    print(f"\n{'='*80}\n(a) ZERO-SHOT TRANSFER: NADT-fitted phenotype probe -> PANDA, "
          f"no PANDA training\n{'='*80}")
    auroc = roc_auc_score(y_panda, pred_zeroshot)
    print(f"ALL (n={len(y_panda)}): AUROC(NADT-probe pred, PANDA tumor-vs-benign) = {auroc:.3f}")
    for prov in np.unique(providers):
        mask = providers == prov
        if len(np.unique(y_panda[mask])) < 2:
            print(f"  {prov}: skipped (single class in subset)")
            continue
        auroc_p = roc_auc_score(y_panda[mask], pred_zeroshot[mask])
        print(f"  {prov} (n={mask.sum()}): AUROC={auroc_p:.3f}")

    # --- (b) PANDA-native cross-institution refit ---
    print(f"\n{'='*80}\n(b) PANDA-NATIVE CROSS-INSTITUTION: train one provider, test the other\n"
          f"{'='*80}")
    for train_prov in np.unique(providers):
        test_prov = [p for p in np.unique(providers) if p != train_prov][0]
        tr_mask = providers == train_prov
        te_mask = providers == test_prov
        probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
        probe.fit(X_panda[tr_mask], y_panda[tr_mask])
        pred = probe.predict_proba(X_panda[te_mask])[:, 1]
        auroc_ci = roc_auc_score(y_panda[te_mask], pred)
        print(f"train={train_prov} (n={tr_mask.sum()}) -> test={test_prov} (n={te_mask.sum()}): "
              f"AUROC={auroc_ci:.3f}")

    # significance check (Mann-Whitney) for the pooled zero-shot result
    u, p = stats.mannwhitneyu(pred_zeroshot[y_panda == 1], pred_zeroshot[y_panda == 0],
                               alternative="two-sided")
    print(f"\nzero-shot pooled Mann-Whitney p={p:.4g}")

    results = pd.DataFrame(dict(image_id=meta_panda["image_id"], data_provider=providers,
                                 isup_grade=meta_panda["isup_grade"], y_tumor=y_panda,
                                 pred_zeroshot_nadt=pred_zeroshot))
    results.to_csv(os.path.join(PANDA_CACHE, "panda_phenotype_results.csv"), index=False)


if __name__ == "__main__":
    main()
