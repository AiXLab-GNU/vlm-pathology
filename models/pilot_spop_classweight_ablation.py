"""SPOP null robustness check: class-weight ablation (Tier-2 review item 2.2). The reviewer
asks for "ablations on class imbalance handling... to rule out underpowered or cohort-specific
effects" as SPOP's null contrasts with an earlier single-institution positive report. Site-
restricted analysis already exists (pilot_tcga_prad_site_split.py, reported in
docs/03_experimental_results.md Sec.3b). This script checks the one remaining, cheap variant:
does the project's standard `class_weight="balanced"` choice (vs. no reweighting) change the
SPOP-mutation null result? SPOP mutation prevalence is ~11% (29/273), so class weighting could
plausibly matter.

Same TCGA-PRAD embeddings and patient-disjoint GroupKFold(5) protocol as
pilot_statistical_corrections.py -- only the LogisticRegression class_weight argument varies.

Run with the CONCH-only venv (fast, CPU only, reuses cached embeddings):
    HF_HOME=~/.cache/huggingface-jhkim models/.venv-conch/bin/python \
        models/pilot_spop_classweight_ablation.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "models"))
from pilot_tcga_prad_site_split import load_data  # noqa: E402


def oof_predict(X, y, groups, class_weight):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight=class_weight))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]
    return oof


def patient_bootstrap_ci(pred, true, n_boot=2000, seed=0):
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        indices = rng.integers(0, len(true), len(true))
        if len(np.unique(true[indices])) < 2:
            continue
        values.append(roc_auc_score(true[indices], pred[indices]))
    return np.percentile(values, [2.5, 97.5])


def minimum_detectable_auroc(n_positive, n_negative, alpha=0.05, power=0.80):
    """Normal-approximation MDE using the Hanley--McNeil AUROC variance."""
    threshold = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)

    def equation(auc):
        q1 = auc / (2 - auc)
        q2 = 2 * auc ** 2 / (1 + auc)
        variance = (auc * (1 - auc) + (n_positive - 1) * (q1 - auc ** 2) +
                    (n_negative - 1) * (q2 - auc ** 2)) / (n_positive * n_negative)
        return (auc - 0.5) / np.sqrt(variance) - threshold

    return brentq(equation, 0.500001, 0.999999)


def main():
    X, meta = load_data()
    y = meta["spop_mut"].values
    groups = meta["case_id"].values
    mask = ~np.isnan(y)
    X, y, groups = X[mask], y[mask].astype(int), groups[mask]
    print(f"n_slide={len(y)}, mutated={y.sum()} ({100*y.mean():.1f}%), wild-type={(y==0).sum()}")

    rows = []
    for cw in ["balanced", None]:
        oof = oof_predict(X, y, groups, cw)
        slide_auroc = roc_auc_score(y, oof)
        slide_p = stats.mannwhitneyu(oof[y == 1], oof[y == 0], alternative="two-sided")[1]

        df = pd.DataFrame(dict(g=groups, pred=oof, true=y))
        pp = df.groupby("g").mean()
        p_true = pp["true"].round().astype(int)
        patient_auroc = roc_auc_score(p_true, pp["pred"])
        patient_p = stats.mannwhitneyu(pp["pred"][p_true == 1], pp["pred"][p_true == 0],
                                        alternative="two-sided")[1]
        label = cw if cw is not None else "None (unweighted)"
        ci_low, ci_high = patient_bootstrap_ci(pp["pred"].to_numpy(), p_true.to_numpy())
        mde = minimum_detectable_auroc(int(p_true.sum()), int((p_true == 0).sum()))
        print(f"class_weight={label}: slide AUROC={slide_auroc:.3f} (p={slide_p:.3g}), "
              f"patient AUROC={patient_auroc:.3f} (p={patient_p:.3g}), n_patients={len(pp)}")
        rows.append(dict(class_weight=label, n_slide=len(y), n_patient=len(pp),
                          slide_auroc=slide_auroc, slide_p=slide_p,
                          patient_auroc=patient_auroc, patient_p=patient_p,
                          patient_ci_low=ci_low, patient_ci_high=ci_high,
                          minimum_detectable_auroc_80pct_power=mde))

    pd.DataFrame(rows).to_csv(
        os.path.join(ROOT, "models/spop_classweight_ablation_summary.csv"), index=False)
    print(f"\nsaved models/spop_classweight_ablation_summary.csv")


if __name__ == "__main__":
    main()
