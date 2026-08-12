"""Grade-stratified permutation test, second half of the confounder audit (docs/04
publication_strategy.md §7-1 / docs/10_protocol_freeze.md §2). Complements the nested LRT in
pilot_confounder_audit.py with a nonparametric check that doesn't assume a linear/logit-linear
relationship between grade and the image score.

Design: build a null distribution by permuting the TRUE LABEL only WITHIN each Gleason-grade
stratum (gleason_sum in {6,7,8,9,10}), never across strata -- this preserves the real
grade<->target marginal association exactly, so any leftover gap between the observed
image-vs-label statistic and the null distribution can't be explained by "the image is
secretly reading grade." The image-only out-of-fold score itself is held fixed (reused from
pilot_confounder_audit.py's already-honest OOF computation) across all permutations -- only the
label assignment is shuffled.

    observed = statistic(image_oof, y_true)
    null_k   = statistic(image_oof, permute_within_grade(y_true))  for k=1..N_PERM
    p        = (1 + #{null_k >= observed}) / (1 + N_PERM)   [one-sided, expected direction is positive]

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_permutation.py
"""
import os
import sys

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from pilot_confounder_audit import load_data, image_oof_binary, image_oof_continuous  # noqa: E402

N_PERM = 2000
RNG_SEED = 0


def permute_within_strata(y, strata, rng):
    y_perm = y.copy()
    for s in np.unique(strata):
        idx = np.where(strata == s)[0]
        if len(idx) > 1:
            y_perm[idx] = rng.permutation(y[idx])
    return y_perm


def audit_binary_permutation(X, meta, label_col, name, min_class_count=10):
    print(f"\n{'='*90}\n{name} -- grade-stratified permutation test\n{'='*90}")
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].astype(int).values
    grade = meta.loc[mask, "gleason_sum"].values.astype(float)
    Xb = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    if y.sum() < min_class_count or (y == 0).sum() < min_class_count:
        print("  too few positive/negative examples, skipping")
        return None

    img_oof = image_oof_binary(Xb, y, groups)
    observed = roc_auc_score(y, img_oof)

    rng = np.random.default_rng(RNG_SEED)
    null_stats = np.empty(N_PERM)
    for k in range(N_PERM):
        y_perm = permute_within_strata(y, grade, rng)
        # guard against a degenerate permutation collapsing one class to zero
        if y_perm.sum() == 0 or y_perm.sum() == len(y_perm):
            null_stats[k] = 0.5
        else:
            null_stats[k] = roc_auc_score(y_perm, img_oof)

    p = (1 + np.sum(null_stats >= observed)) / (1 + N_PERM)
    print(f"n={len(y)} (positive={y.sum()}, negative={(y==0).sum()}), grade strata: "
          f"{sorted(set(grade))}")
    print(f"  observed AUROC = {observed:.3f}")
    print(f"  null (grade-preserved permutation, N={N_PERM}): "
          f"mean={null_stats.mean():.3f}  sd={null_stats.std():.3f}  "
          f"95th pct={np.percentile(null_stats, 95):.3f}")
    print(f"  permutation p (one-sided) = {p:.4g}")
    return dict(name=name, n=len(y), observed=observed, null_mean=null_stats.mean(),
                null_sd=null_stats.std(), p=p)


def audit_continuous_permutation(X, meta, label_col, name):
    print(f"\n{'='*90}\n{name} -- grade-stratified permutation test\n{'='*90}")
    mask = meta[label_col].notna() & meta["gleason_sum"].notna()
    y = meta.loc[mask, label_col].values.astype(float)
    grade = meta.loc[mask, "gleason_sum"].values.astype(float)
    Xc = X[mask.values]
    groups = meta.loc[mask, "case_id"].values

    img_oof = image_oof_continuous(Xc, y, groups)
    observed, _ = stats.spearmanr(img_oof, y)

    rng = np.random.default_rng(RNG_SEED)
    null_stats = np.empty(N_PERM)
    for k in range(N_PERM):
        y_perm = permute_within_strata(y, grade, rng)
        rho, _ = stats.spearmanr(img_oof, y_perm)
        null_stats[k] = rho

    p = (1 + np.sum(null_stats >= observed)) / (1 + N_PERM)
    print(f"n={len(y)}, grade strata: {sorted(set(grade))}")
    print(f"  observed rho = {observed:+.3f}")
    print(f"  null (grade-preserved permutation, N={N_PERM}): "
          f"mean={null_stats.mean():+.3f}  sd={null_stats.std():.3f}  "
          f"95th pct={np.percentile(null_stats, 95):+.3f}")
    print(f"  permutation p (one-sided) = {p:.4g}")
    return dict(name=name, n=len(y), observed=observed, null_mean=null_stats.mean(),
                null_sd=null_stats.std(), p=p)


def main():
    X, meta = load_data()
    results = []
    results.append(audit_binary_permutation(X, meta, "pten_loss", "Marker 4: PTEN loss"))
    results.append(audit_continuous_permutation(X, meta, "ar_score", "Marker 6: AR activity score"))
    results.append(audit_binary_permutation(
        X, meta, "erg_fusion", "H&E -> ERG fusion status (unpromoted candidate, NOT marker 3)"))

    print(f"\n{'='*90}\nSUMMARY\n{'='*90}")
    for r in results:
        if r is None:
            continue
        print(f"{r['name']:50s} n={r['n']:4d}  observed={r['observed']:+.3f}  "
              f"null_mean={r['null_mean']:+.3f}  perm p={r['p']:.4g}")


if __name__ == "__main__":
    main()
