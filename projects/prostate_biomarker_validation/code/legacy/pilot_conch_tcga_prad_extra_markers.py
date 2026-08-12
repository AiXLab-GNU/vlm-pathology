"""Fourth wave of TCGA-PRAD experiments -- expanding the marker pool using labels that were
ALREADY downloaded in the same cBioPortal prad_tcga_pub clinical-sample JSON used for PTEN/SPOP
(pilot_conch_tcga_prad_multi.py), but never tested. Zero new download, zero new GPU embedding --
reuses resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/X.npy (266 slides, 512-dim CONCH embedding, mean-pooled over
16 random tissue tiles per slide) exactly as before.

Candidates tested (chosen for biological plausibility + adequate class balance, n>=10 per class):
  - TP53_MUTATION (23 positive / 310 negative): well-known aggressive-morphology correlate.
  - TP53_CNA loss (hetloss/homdel, 102 positive / 231 negative): same gene, copy-number axis.
  - RB1_CNA loss (hetloss/homdel, 90 positive / 243 negative): TP53+RB1 co-loss is associated
    with treatment-emergent neuroendocrine prostate cancer, which DOES have a distinct
    (small-cell-like) morphology -- most biologically-motivated new candidate here.
  - AR_SCORE (continuous, androgen-receptor activity signature): regression target like
    marker (1), central to prostate cancer biology.
  - SPINK1_HIGH (17 positive / 316 negative): a known ETS-fusion-negative molecular subtype.
  - ETV1_STATUS, ETV4_STATUS altered-vs-none (29 and 16 positive respectively): other ETS-family
    fusion partners, same family as ERG (marker 3) -- interesting comparison point.
  Skipped: FLI1_STATUS (4 positive total) and CDK12_MUT (6 positive) -- too few for CV.

Run with the CONCH-only venv (fast -- no embedding, just probe fits + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_tcga_prad_extra_markers.py
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
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")


def load_data():
    data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))

    meta["tp53_mut"] = meta["case_id"].map(by_attr["TP53_MUTATION"]).astype(float)
    meta["tp53_cna_loss"] = meta["case_id"].map(by_attr["TP53_CNA"]).isin(["hetloss", "homdel"]).astype(float)
    meta["rb1_cna_loss"] = meta["case_id"].map(by_attr["RB1_CNA"]).isin(["hetloss", "homdel"]).astype(float)
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    meta["spink1_high"] = meta["case_id"].map(by_attr["SPINK1_HIGH"]).astype(float)
    meta["etv1_altered"] = meta["case_id"].map(by_attr["ETV1_STATUS"]).isin(["fusion", "high"]).astype(float)
    meta["etv4_altered"] = meta["case_id"].map(by_attr["ETV4_STATUS"]).isin(["fusion", "high"]).astype(float)

    # tp53_cna_loss / rb1_cna_loss / etv*_altered: .isin() on a Series with NaN silently gives
    # False instead of NaN, so re-null out cases missing the raw attribute entirely.
    for col, attr in [("tp53_cna_loss", "TP53_CNA"), ("rb1_cna_loss", "RB1_CNA"),
                       ("etv1_altered", "ETV1_STATUS"), ("etv4_altered", "ETV4_STATUS")]:
        missing = meta["case_id"].map(by_attr[attr]).isna()
        meta.loc[missing, col] = np.nan

    return meta


def test_binary_marker(X, meta, label_col, name, min_class_count=10):
    print(f"\n{'='*80}\n{name}\n{'='*80}")
    mask = meta[label_col].notna()
    y = meta.loc[mask, label_col].astype(int).values
    Xb = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"n={len(y)} slides (positive={y.sum()}, negative={(y==0).sum()})")
    if y.sum() < min_class_count or (y == 0).sum() < min_class_count:
        print("  too few positive/negative examples, skipping CV")
        return None

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
    auroc_p = None
    if y_p.nunique() > 1 and y_p.sum() >= 5 and (y_p == 0).sum() >= 5:
        auroc_p = roc_auc_score(y_p, per_patient["pred"])
        print(f"patient-level (n={len(per_patient)}): AUROC={auroc_p:.3f}")
    return dict(slide_auroc=auroc, slide_p=p, patient_auroc=auroc_p, n=len(y), n_pos=int(y.sum()))


def test_continuous_marker(X, meta, label_col, name):
    print(f"\n{'='*80}\n{name}\n{'='*80}")
    mask = meta[label_col].notna()
    y = meta.loc[mask, label_col].values
    Xc = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"n={len(y)} slides")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(Xc, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(Xc[tr], y[tr])
        oof[te] = probe.predict(Xc[te])

    rho, p = stats.spearmanr(oof, y)
    print(f"slide-level (n={len(y)}): rho={rho:+.3f}  p={p:.4g}")

    df_eval = pd.DataFrame(dict(case_id=groups, pred=oof, true=y))
    per_patient = df_eval.groupby("case_id").mean()
    rho_p, p_p = stats.spearmanr(per_patient["pred"], per_patient["true"])
    print(f"patient-level (n={len(per_patient)}): rho={rho_p:+.3f}  p={p_p:.4g}")
    return dict(slide_rho=rho, slide_p=p, patient_rho=rho_p, patient_p=p_p, n=len(y))


def main():
    meta = load_data()
    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))

    results = {}
    results["TP53 mutation"] = test_binary_marker(X, meta, "tp53_mut", "H&E -> TP53 mutation")
    results["TP53 CNA loss"] = test_binary_marker(X, meta, "tp53_cna_loss", "H&E -> TP53 CNA loss (hetloss/homdel)")
    results["RB1 CNA loss"] = test_binary_marker(X, meta, "rb1_cna_loss", "H&E -> RB1 CNA loss (hetloss/homdel)")
    results["SPINK1 high"] = test_binary_marker(X, meta, "spink1_high", "H&E -> SPINK1 high expression")
    results["ETV1 altered"] = test_binary_marker(X, meta, "etv1_altered", "H&E -> ETV1 fusion/high (ETS family, cf. marker 3 ERG)")
    results["ETV4 altered"] = test_binary_marker(X, meta, "etv4_altered", "H&E -> ETV4 fusion/high (ETS family, cf. marker 3 ERG)")
    results["AR score"] = test_continuous_marker(X, meta, "ar_score", "H&E -> AR activity score (continuous)")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    for name, r in results.items():
        if r is None:
            print(f"{name:20s} skipped (too few examples)")
        elif "slide_auroc" in r:
            pl = f", patient AUROC={r['patient_auroc']:.3f}" if r["patient_auroc"] else ""
            print(f"{name:20s} n={r['n']:4d} (pos={r['n_pos']:3d})  slide AUROC={r['slide_auroc']:.3f} "
                  f"(p={r['slide_p']:.3g}){pl}")
        else:
            print(f"{name:20s} n={r['n']:4d}  slide rho={r['slide_rho']:+.3f} (p={r['slide_p']:.3g}), "
                  f"patient rho={r['patient_rho']:+.3f} (p={r['patient_p']:.3g})")


if __name__ == "__main__":
    main()
