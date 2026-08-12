"""Confounder audit, step 1 of docs/04_publication_strategy.md's execution order §7-1 /
docs/10_protocol_freeze.md's qualified-pool gate 4 ("confounder audit 통과").

Question: for PTEN loss (marker 4), AR activity score (marker 6), and TCGA-PRAD H&E->ERG
FUSION STATUS (a separate, not-yet-promoted candidate -- see naming note below) -- all
molecular statuses plausibly correlated with Gleason grade -- does the H&E-image-derived
signal add predictive value BEYOND grade alone, or is the image probe just a roundabout way
of detecting grade?

NAMING CORRECTION (caught while writing this script, logged so it isn't repeated -- the
project memory already flagged this exact conflation once): "erg_fusion" in
tcga_prad_conch_cache/meta.csv is TCGA-PRAD H&E -> real TMPRSS2:ERG fusion status. This is
NOT marker (3) of the 6-marker pool (marker 3 = NADT ERG-STAINED image -> Gleason GRADE,
a continuous target on a totally different dataset). Marker (3)'s target IS Gleason grade
itself, so a "does image add value beyond grade" audit is circular for it, exactly like
marker (1) -- both are excluded from this script for that reason. The erg_fusion audit here
is included because it IS a molecular-status-vs-grade question in the PTEN/AR sense, just
under a different, unpromoted candidate name; its result says nothing about marker (3)'s own
open question (the residual-hematoxylin-architecture hypothesis, still unresolved).

Marker 2 (H&E->tumor/normal phenotype) is also out of scope: benign slides have no grade at
all, so the same clinical(grade)-vs-image framing doesn't apply.

Design (fixed by docs/10_protocol_freeze.md, not invented after seeing results):
  - Clinical-only model: target ~ REVIEWED_GLEASON_SUM alone (the only real clinical covariate
    available in TCGA-PRAD's cBioPortal sample-level export -- no PSA/age/stage here, noted
    honestly rather than assumed).
  - Image-only model: target ~ full 512-dim frozen CONCH embedding (the marker's existing
    probe, refit here with the exact protocol from pilot_statistical_corrections.py for
    consistency: RidgeCV/LogisticRegression(C=1.0, class_weight="balanced"), patient-disjoint
    GroupKFold(n_splits=5)), reduced to a single out-of-fold scalar score per slide.
  - Combined model: target ~ grade + image_oof_score (2-feature second-stage model, same CV
    discipline) -- tests whether image adds value ONCE grade is already in the model, not
    whether image alone beats grade alone.
  - delta_AUROC / delta_R2 = combined - clinical (marginal value of adding image to clinical).
  - Likelihood-ratio test (nested, in-sample fit on the full cohort, standard confounder-
    analysis practice): H0 = clinical-only model, H1 = clinical+image model, chi2 statistic
    with df=1 (one additional coefficient: image_oof_score). This is the primary "does the
    image carry information beyond grade" test -- reusing the OOF image score keeps it honest
    (that scalar was never fit using the label of the row it's scoring), while the LRT itself
    is computed in-sample because comparing two already-fixed nested nested nested designs
    on the full n gives the standard, well-calibrated LRT null distribution.

Run with the CONCH-only venv (fast -- no embedding, just probe fits + eval):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit.py
"""
import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
N_SPLITS = 5


def load_data():
    if not os.path.exists(CBIOPORTAL_SAMPLE_JSON):
        raise FileNotFoundError(
            f"Missing {CBIOPORTAL_SAMPLE_JSON}; run resources/projects/prostate_biomarker_validation/model_workspace/fetch_tcga_prad_clinical_extra.py")
    with open(CBIOPORTAL_SAMPLE_JSON) as f:
        data = json.load(f)
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))

    meta["gleason_sum"] = meta["case_id"].map(by_attr["REVIEWED_GLEASON_SUM"]).astype(float)
    meta["pten_loss"] = meta["case_id"].map(by_attr["PTEN_CNA"]).isin(["hetloss", "homdel"]).astype(float)
    missing_pten = meta["case_id"].map(by_attr["PTEN_CNA"]).isna()
    meta.loc[missing_pten, "pten_loss"] = np.nan
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    # erg_fusion already present in meta.csv (0/1, from the GDC-derived merge upstream)

    return X, meta


def image_oof_binary(X, y, groups):
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]
    return oof


def image_oof_continuous(X, y, groups):
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict(X[te])
    return oof


def combined_oof_binary(grade, image_oof, y, groups):
    """Second-stage 2-feature model (grade, image_oof) -> target, same CV discipline."""
    feats = np.column_stack([grade, image_oof])
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(feats, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(feats[tr], y[tr])
        oof[te] = probe.predict_proba(feats[te])[:, 1]
    return oof


def combined_oof_continuous(grade, image_oof, y, groups):
    feats = np.column_stack([grade, image_oof])
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(feats, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(feats[tr], y[tr])
        oof[te] = probe.predict(feats[te])
    return oof


def clinical_only_oof_binary(grade, y, groups):
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    grade2d = grade.reshape(-1, 1)
    for tr, te in gkf.split(grade2d, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(grade2d[tr], y[tr])
        oof[te] = probe.predict_proba(grade2d[te])[:, 1]
    return oof


def clinical_only_oof_continuous(grade, y, groups):
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = np.full(len(y), np.nan)
    grade2d = grade.reshape(-1, 1)
    for tr, te in gkf.split(grade2d, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(grade2d[tr], y[tr])
        oof[te] = probe.predict(grade2d[te])
    return oof


def lrt_binary(grade, image_oof, y):
    """In-sample nested LRT: H0 target~grade, H1 target~grade+image_oof. df=1 chi2."""
    X0 = sm.add_constant(grade.reshape(-1, 1))
    X1 = sm.add_constant(np.column_stack([grade, image_oof]))
    m0 = sm.Logit(y, X0).fit(disp=0)
    m1 = sm.Logit(y, X1).fit(disp=0)
    lr_stat = 2 * (m1.llf - m0.llf)
    p = stats.chi2.sf(lr_stat, df=1)
    return lr_stat, p, m1.params[-1]


def lrt_continuous(grade, image_oof, y):
    X0 = sm.add_constant(grade.reshape(-1, 1))
    X1 = sm.add_constant(np.column_stack([grade, image_oof]))
    m0 = sm.OLS(y, X0).fit()
    m1 = sm.OLS(y, X1).fit()
    lr_stat = 2 * (m1.llf - m0.llf)
    p = stats.chi2.sf(lr_stat, df=1)
    return lr_stat, p, m1.params[-1]


def audit_binary(X, meta, label_col, name, min_class_count=10):
    print(f"\n{'='*90}\n{name} -- confounder audit vs REVIEWED_GLEASON_SUM\n{'='*90}")
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].astype(int).values
    grade = meta.loc[mask, "gleason_sum"].values.astype(float)
    Xb = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"n={len(y)} slides (positive={y.sum()}, negative={(y==0).sum()})")
    if y.sum() < min_class_count or (y == 0).sum() < min_class_count:
        print("  too few positive/negative examples, skipping")
        return None

    img_oof = image_oof_binary(Xb, y, groups)
    clin_oof = clinical_only_oof_binary(grade, y, groups)
    comb_oof = combined_oof_binary(grade, img_oof, y, groups)

    auroc_img = roc_auc_score(y, img_oof)
    auroc_clin = roc_auc_score(y, clin_oof)
    auroc_comb = roc_auc_score(y, comb_oof)
    delta = auroc_comb - auroc_clin

    lr_stat, lr_p, coef = lrt_binary(grade, img_oof, y)

    print(f"  clinical-only (grade)         AUROC = {auroc_clin:.3f}")
    print(f"  image-only (CONCH probe)      AUROC = {auroc_img:.3f}")
    print(f"  combined (grade+image)        AUROC = {auroc_comb:.3f}")
    print(f"  delta AUROC (combined-clinical)      = {delta:+.3f}")
    print(f"  LRT (image beyond grade): chi2={lr_stat:.2f}  p={lr_p:.4g}  "
          f"image_coef={coef:+.3f}")
    return dict(name=name, n=len(y), auroc_clin=auroc_clin, auroc_img=auroc_img,
                auroc_comb=auroc_comb, delta_auroc=delta, lr_stat=lr_stat, lr_p=lr_p)


def audit_continuous(X, meta, label_col, name):
    print(f"\n{'='*90}\n{name} -- confounder audit vs REVIEWED_GLEASON_SUM\n{'='*90}")
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].values.astype(float)
    grade = meta.loc[mask, "gleason_sum"].values.astype(float)
    Xc = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"n={len(y)} slides")

    img_oof = image_oof_continuous(Xc, y, groups)
    clin_oof = clinical_only_oof_continuous(grade, y, groups)
    comb_oof = combined_oof_continuous(grade, img_oof, y, groups)

    r2_img = r2_score(y, img_oof)
    r2_clin = r2_score(y, clin_oof)
    r2_comb = r2_score(y, comb_oof)
    delta = r2_comb - r2_clin

    lr_stat, lr_p, coef = lrt_continuous(grade, img_oof, y)

    print(f"  clinical-only (grade)         R2 (OOF) = {r2_clin:+.3f}")
    print(f"  image-only (CONCH probe)      R2 (OOF) = {r2_img:+.3f}")
    print(f"  combined (grade+image)        R2 (OOF) = {r2_comb:+.3f}")
    print(f"  delta R2 (combined-clinical)           = {delta:+.3f}")
    print(f"  LRT (image beyond grade): chi2={lr_stat:.2f}  p={lr_p:.4g}  "
          f"image_coef={coef:+.4f}")
    return dict(name=name, n=len(y), r2_clin=r2_clin, r2_img=r2_img, r2_comb=r2_comb,
                delta_r2=delta, lr_stat=lr_stat, lr_p=lr_p)


def main():
    X, meta = load_data()
    results = []
    results.append(audit_binary(X, meta, "erg_fusion",
                                 "H&E -> ERG fusion status (unpromoted candidate, NOT marker 3)"))
    results.append(audit_binary(X, meta, "pten_loss", "Marker 4: PTEN loss"))
    results.append(audit_continuous(X, meta, "ar_score", "Marker 6: AR activity score"))

    print(f"\n{'='*90}\nSUMMARY (protocol_freeze.md gate 4 input)\n{'='*90}")
    for r in results:
        if r is None:
            continue
        if "auroc_comb" in r:
            print(f"{r['name']:35s} n={r['n']:4d}  dAUROC={r['delta_auroc']:+.3f}  "
                  f"LRT p={r['lr_p']:.4g}")
        else:
            print(f"{r['name']:35s} n={r['n']:4d}  dR2={r['delta_r2']:+.3f}  "
                  f"LRT p={r['lr_p']:.4g}")


if __name__ == "__main__":
    main()
