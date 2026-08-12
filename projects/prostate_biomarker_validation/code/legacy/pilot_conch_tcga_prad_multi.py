"""Second wave of TCGA-PRAD experiments, all reusing the cached H&E embeddings from the ERG
job (resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/X.npy, meta.csv, 266 slides / ~265 patients) -- NO new
download or GPU embedding needed. cBioPortal's prad_tcga_pub study (same source as ERG_STATUS)
has real SAMPLE-level molecular/clinical labels for most of these same cases:
  - REVIEWED_GLEASON_SUM (273/273 overlap): real reviewed Gleason score, 6-10.
  - PTEN_CNA (273/273 overlap): diploid(192) / hetloss(37) / homdel(44) -- PTEN loss (via copy
    number, not point mutation -- PTEN_MUTATION is far too rare, 7/273, skipped) is a
    well-known aggressive-morphology correlate in prostate cancer literature.
  - SPOP_MUTATION (273/273 overlap): 29/273 (~11%) mutated -- some literature associates SPOP
    mutation with distinct (often cribriform) morphology, worth an honest test even though the
    ERG fusion-status experiment (a different gene, same general "molecular status from H&E"
    question) came back weak/null.

Three independent tests:
  (a) Marker (1) THIRD external validation: does the NADT-fitted AND the PANDA-fitted marker
      (1) probe (both already exist, zero retraining) correlate with TCGA-PRAD's real Gleason
      score? This is now a three-institution generalization chain (NADT -> PANDA -> TCGA-PRAD)
      for the same marker.
  (b) NEW marker candidate: H&E -> PTEN loss (binary: hetloss/homdel vs diploid).
  (c) NEW marker candidate: H&E -> SPOP mutation (binary), expecting a weak/null result similar
      to the ERG fusion-status experiment, but tested honestly rather than assumed.

Run with the CONCH-only venv (fast -- no embedding, just probe fits + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_tcga_prad_multi.py
"""
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
NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
PANDA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache")
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")


def load_tcga_labels():
    import json
    data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))

    meta["gleason_sum"] = meta["case_id"].map(by_attr["REVIEWED_GLEASON_SUM"]).astype(float)
    meta["pten_cna"] = meta["case_id"].map(by_attr["PTEN_CNA"])
    meta["pten_loss"] = meta["pten_cna"].isin(["hetloss", "homdel"]).astype(int)
    meta["spop_mut"] = meta["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)

    return X, meta


def test_marker1_transfer(X, meta):
    print(f"\n{'='*80}\n(a) MARKER (1) THIRD EXTERNAL VALIDATION: NADT-probe & PANDA-probe -> "
          f"TCGA-PRAD real Gleason score\n{'='*80}")
    mask = meta["gleason_sum"].notna()
    y = meta.loc[mask, "gleason_sum"].values
    Xg = X[mask.values]
    print(f"n={len(y)} slides with real Gleason score (REVIEWED_GLEASON_SUM)")

    # NADT-fitted probe (trained on NADT's 334 H&E slides, target=gleason_total 6-10)
    X_nadt = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    nadt_probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    nadt_probe.fit(X_nadt, meta_nadt["gleason_total"].values)
    pred_nadt = nadt_probe.predict(Xg)
    rho_nadt, p_nadt = stats.spearmanr(pred_nadt, y)
    print(f"NADT-fitted probe -> TCGA-PRAD: rho={rho_nadt:+.3f}  p={p_nadt:.4g}")

    # PANDA-fitted probe (trained on all 1137 PANDA TUMOR slides, target=isup_grade 1-5)
    X_panda = np.load(os.path.join(PANDA_CACHE, "X_panda.npy"))
    meta_panda = pd.read_csv(os.path.join(PANDA_CACHE, "meta_panda.csv"))
    panda_tumor = meta_panda["isup_grade"].values >= 1
    panda_probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    panda_probe.fit(X_panda[panda_tumor], meta_panda.loc[panda_tumor, "isup_grade"].values)
    pred_panda = panda_probe.predict(Xg)
    rho_panda, p_panda = stats.spearmanr(pred_panda, y)
    print(f"PANDA-fitted probe -> TCGA-PRAD: rho={rho_panda:+.3f}  p={p_panda:.4g}")


def test_binary_marker(X, meta, label_col, name, min_class_count=10):
    print(f"\n{'='*80}\n{name}\n{'='*80}")
    mask = meta[label_col].notna()
    y = meta.loc[mask, label_col].astype(int).values
    Xb = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"n={len(y)} slides (positive={y.sum()}, negative={(y==0).sum()})")
    if y.sum() < min_class_count or (y == 0).sum() < min_class_count:
        print("  too few positive/negative examples, skipping CV")
        return

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(Xb, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(Xb[tr], y[tr])
        oof[te] = probe.predict_proba(Xb[te])[:, 1]

    auroc = roc_auc_score(y, oof)
    u, p = stats.mannwhitneyu(oof[y == 1], oof[y == 0], alternative="two-sided")
    print(f"slide-level (n={len(y)}): AUROC={auroc:.3f}  Mann-Whitney p={p:.4g}")

    df_eval = pd.DataFrame(dict(case_id=groups, pred=oof, true=y))
    per_patient = df_eval.groupby("case_id").mean()
    y_p = per_patient["true"].round().astype(int)
    if y_p.nunique() > 1 and y_p.sum() >= 5 and (y_p == 0).sum() >= 5:
        auroc_p = roc_auc_score(y_p, per_patient["pred"])
        print(f"patient-level (n={len(per_patient)}): AUROC={auroc_p:.3f}")


def main():
    X, meta = load_tcga_labels()
    test_marker1_transfer(X, meta)
    test_binary_marker(X, meta, "pten_loss", "(b) NEW MARKER CANDIDATE: H&E -> PTEN loss "
                                              "(hetloss/homdel vs diploid)")
    test_binary_marker(X, meta, "spop_mut", "(c) NEW MARKER CANDIDATE: H&E -> SPOP mutation")


if __name__ == "__main__":
    main()
