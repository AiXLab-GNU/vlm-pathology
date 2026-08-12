"""QWK (quadratic weighted kappa) recalculation for marker 1 (H&E->Gleason), docs/04
publication_strategy.md item 3/6: Spearman rho isn't directly comparable to literature F1/QWK
numbers (different units). This converts marker 1's continuous predictions to ordinal
categories (via quantile binning matched to each cohort's own number of true grade
categories -- a standard, transparent continuous-to-ordinal conversion that does not peek at
true-label thresholds beyond how many categories exist) and computes QWK against each
cohort's real grade labels, using ONE consistent protocol throughout (same discipline as
pilot_statistical_corrections.py): RidgeCV on raw CONCH embeddings, patient-disjoint
GroupKFold where relevant.

Five QWK numbers, each with an explicit note on input unit / eval unit / external validation
status, per docs/04's own requirement not to blur these together:
  1. NADT own-cohort (patient-disjoint 5-fold OOF) -- slide input, patient-level eval
  2. PANDA zero-shot (NADT-fitted probe, no PANDA data in training) -- biopsy input, external
  3. PANDA native refit, Karolinska->Radboud and Radboud->Karolinska -- biopsy input, external
     institution but NOT a held-out zero-shot test of the same coefficients
  4. TCGA-PRAD zero-shot (NADT-fitted probe) -- resection specimen input, external, 3rd cohort
  5. PRECISE zero-shot (NADT-fitted probe, Tumor-labeled tiles only, real pathologist Gleason)
     -- core-biopsy input, external, real (not proxy) ground truth, n=17 images (small)

Literature reference points (already vetted in docs/04, not re-verified here): DeepGleason
F1=0.806 (tile-level, not QWK, not directly comparable); PANDA challenge external test QWK
~0.862 (US cohort) / ~0.868 (European cohort), both biopsy-level.

Run with the CONCH-only venv (fast, all embeddings already cached, no GPU needed):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_qwk_comparison.py
"""
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.metrics import cohen_kappa_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
PANDA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/panda_conch_cache")
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
PRECISE_RESULTS = os.path.join(ROOT, "resources/data/shared/opendataset/PRECISE/spatial_facevalidity_results_150um.csv")
PRECISE_PARTICIPANTS = os.path.join(ROOT, "resources/data/shared/opendataset/PRECISE/participants.csv")


def fit_ridge(X, y):
    m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    m.fit(X, y)
    return m


def qwk_from_continuous(pred, true):
    """Quantile-bin pred into as many ordinal categories as `true` has unique values, then QWK."""
    n_classes = len(np.unique(true))
    pred_bins = pd.qcut(pred, q=n_classes, labels=False, duplicates="drop")
    true_sorted = np.unique(true)
    true_bins = np.searchsorted(true_sorted, true)
    return cohen_kappa_score(true_bins, pred_bins, weights="quadratic"), n_classes, len(np.unique(pred_bins))


def nadt_own_cohort():
    """QWK needs genuinely categorical ground truth -- computed at the SLIDE level (each
    slide has one well-defined integer gleason_total) rather than patient-aggregated, since
    35/39 NADT patients have multiple slides with DIFFERING true grades and averaging them
    produces a fractional, non-categorical "true" value that QWK can't sensibly use. This also
    matches this project's own "slide-level pooled out-of-fold" convention already used for
    the Spearman rho version of this same result, and is the more literature-comparable unit
    anyway (DeepGleason is tile-level, PANDA QWK is slide/biopsy-level)."""
    X = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    y = meta["gleason_total"].values
    groups = meta["patient_id"].values
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        m = fit_ridge(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    return qwk_from_continuous(oof, y), len(y)


def panda_zeroshot():
    X_nadt = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    probe = fit_ridge(X_nadt, meta_nadt["gleason_total"].values)

    X_panda = np.load(os.path.join(PANDA_CACHE, "X_panda.npy"))
    meta_panda = pd.read_csv(os.path.join(PANDA_CACHE, "meta_panda.csv"))
    pred = probe.predict(X_panda)
    return qwk_from_continuous(pred, meta_panda["isup_grade"].values), len(meta_panda)


def panda_native_refit():
    X_panda = np.load(os.path.join(PANDA_CACHE, "X_panda.npy"))
    meta_panda = pd.read_csv(os.path.join(PANDA_CACHE, "meta_panda.csv"))
    results = {}
    for train_prov, test_prov in [("karolinska", "radboud"), ("radboud", "karolinska")]:
        tr_mask = (meta_panda["data_provider"] == train_prov).values
        te_mask = (meta_panda["data_provider"] == test_prov).values
        probe = fit_ridge(X_panda[tr_mask], meta_panda.loc[tr_mask, "isup_grade"].values)
        pred = probe.predict(X_panda[te_mask])
        qwk, nc, np_ = qwk_from_continuous(pred, meta_panda.loc[te_mask, "isup_grade"].values)
        results[f"{train_prov}->{test_prov}"] = (qwk, nc, np_, te_mask.sum())
    return results


def tcga_prad_zeroshot():
    X_nadt = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    probe = fit_ridge(X_nadt, meta_nadt["gleason_total"].values)

    import sys
    sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
    from pilot_confounder_audit import load_data as load_tcga_data
    X_tcga, meta_tcga = load_tcga_data()
    mask = meta_tcga["gleason_sum"].notna()
    pred = probe.predict(X_tcga[mask.values])
    true = meta_tcga.loc[mask, "gleason_sum"].values
    return qwk_from_continuous(pred, true), int(mask.sum())


def precise_zeroshot():
    import re
    df = pd.read_csv(PRECISE_RESULTS)
    participants = pd.read_csv(PRECISE_PARTICIPANTS).set_index("IMAGE_NAME")
    tumor_df = df[df["label_class"] == 1]
    per_image = tumor_df.groupby("image_id")["marker1_gleason"].mean()
    rows = []
    for image_id, pred in per_image.items():
        if image_id not in participants.index:
            continue
        m = re.match(r"(\d)\+(\d)=(\d+)", str(participants.loc[image_id, "Gleason_score"]))
        if not m:
            continue
        rows.append((pred, int(m.group(3))))
    comp = pd.DataFrame(rows, columns=["pred", "true"])
    return qwk_from_continuous(comp["pred"].values, comp["true"].values), len(comp)


def main():
    print(f"{'='*90}\nQWK (quadratic weighted kappa) comparison, marker 1 (H&E->Gleason)\n{'='*90}")

    (qwk, nc, npred), n = nadt_own_cohort()
    print(f"\n1. NADT own-cohort (patient-disjoint OOF, n={n}, {nc} true classes, "
          f"{npred} pred bins): QWK={qwk:.3f}")
    print("   input=biopsy, eval=SLIDE-level (pooled OOF), NOT externally validated")

    (qwk, nc, npred), n = panda_zeroshot()
    print(f"\n2. PANDA zero-shot (NADT-fitted probe, n={n}, {nc} classes): QWK={qwk:.3f}")
    print("   input=biopsy, eval=slide-level, EXTERNAL (2 institutions, zero retraining)")

    native = panda_native_refit()
    for k, (qwk, nc, npred, n) in native.items():
        print(f"\n3. PANDA native refit {k} (n={n}, {nc} classes): QWK={qwk:.3f}")
        print("   input=biopsy, eval=slide-level, external institution but refit (not zero-shot)")

    (qwk, nc, npred), n = tcga_prad_zeroshot()
    print(f"\n4. TCGA-PRAD zero-shot (NADT-fitted probe, n={n}, {nc} classes): QWK={qwk:.3f}")
    print("   input=RESECTION specimen (differs from NADT/PANDA biopsy), eval=slide-level, "
          "EXTERNAL (3rd institution)")

    (qwk, nc, npred), n = precise_zeroshot()
    print(f"\n5. PRECISE zero-shot (NADT-fitted probe, Tumor tiles only, REAL pathologist "
          f"Gleason, n={n} images, {nc} classes): QWK={qwk:.3f}")
    print("   input=core biopsy, eval=IMAGE-level (tile-averaged), EXTERNAL, real (non-proxy) "
          "ground truth, SMALL n")

    print(f"\n{'='*90}\nLiterature reference points (NOT recomputed here, already vetted in docs/04)\n{'='*90}")
    print("DeepGleason: F1=0.806 (tile-level -- different metric, not directly QWK-comparable)")
    print("PANDA challenge external test: QWK~0.862 (US cohort) / ~0.868 (European cohort), "
          "both biopsy-level, large N (thousands)")


if __name__ == "__main__":
    main()
