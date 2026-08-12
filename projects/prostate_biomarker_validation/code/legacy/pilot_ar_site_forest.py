"""AR-activity (marker 6) per-site forest plot with bootstrap 95% CIs (Tier-1 review item 1.3:
"could you provide per-site effect sizes with confidence intervals (e.g. a forest plot)?").

pilot_tcga_prad_site_split.py already computes the 6-site leave-one-site-out point estimates
(docs/03_experimental_results.md §3b: site rho ranging ~-0.13 at CH to +0.27 at KK, mean 0.151
vs pooled 0.195) but reports point estimates only. This script adds a per-site bootstrap 95% CI
-- patient-cluster resample WITHIN the held-out site's test patients only (not across sites,
since each site's estimate comes from a separately-trained held-out model), 2000 reps. Site
sample sizes are small (~20-60 slides), so these CIs will be wide -- reported honestly rather
than papering over the uncertainty, per the reviewer's request.

The "pooled" row is the standard patient-level pooled estimate from
resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv (5-fold patient-disjoint internal CV across all
sites combined, already BH-FDR corrected and bootstrap-CI'd in pilot_statistical_corrections.py)
-- not a re-estimated random-effects meta-analytic pooled value, since the per-site estimates
come from six different held-out models (leave-one-site-out), not from a common-effect model
that a formal meta-analysis pooling would assume.

Run with the CONCH-only venv (fast, CPU only, reuses cached embeddings):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_ar_site_forest.py
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_tcga_prad_site_split import load_data, MIN_SITE_SLIDES  # noqa: E402

N_BOOT = 2000
SEED = 0
OUT_CSV = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/ar_site_forest_summary.csv")
STAT_CORR_CSV = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv")


def fit_predict_site(X, y, sites, case_ids, site, min_site_slides=MIN_SITE_SLIDES):
    mask = ~np.isnan(y)
    X, y, sites, case_ids = X[mask], y[mask], sites[mask], case_ids[mask]

    te_mask = sites == site
    tr_mask = ~te_mask
    probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    probe.fit(X[tr_mask], y[tr_mask])
    pred_te = probe.predict(X[te_mask])
    return pred_te, y[te_mask], case_ids[te_mask]


def patient_cluster_bootstrap_rho(pred, true, patient_ids, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    unique_patients = np.unique(patient_ids)
    idx_by_patient = {p: np.where(patient_ids == p)[0] for p in unique_patients}
    boot_rhos = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_patients, size=len(unique_patients), replace=True)
        idx = np.concatenate([idx_by_patient[p] for p in sampled])
        p_, t_ = pred[idx], true[idx]
        if len(np.unique(t_)) < 2:
            continue
        rho = stats.spearmanr(p_, t_)[0]
        if not np.isnan(rho):
            boot_rhos.append(rho)
    lo, hi = np.percentile(boot_rhos, [2.5, 97.5])
    return lo, hi, len(boot_rhos)


def main():
    X, meta = load_data()
    sites = meta["site"].values
    case_ids = meta["case_id"].values
    y = meta["ar_score"].values

    mask_valid = ~np.isnan(y)
    site_counts = pd.Series(sites[mask_valid]).value_counts()
    big_sites = sorted(site_counts[site_counts >= MIN_SITE_SLIDES].index.tolist())

    rows = []
    for site in big_sites:
        pred, true, pids = fit_predict_site(X, y, sites, case_ids, site)
        rho, _ = stats.spearmanr(pred, true)
        lo, hi, n_valid_boot = patient_cluster_bootstrap_rho(pred, true, pids)
        n_patients = len(np.unique(pids))
        print(f"site {site}: n_slides={len(true)}, n_patients={n_patients}, rho={rho:+.3f}, "
              f"95% CI=[{lo:+.3f}, {hi:+.3f}] ({n_valid_boot}/{N_BOOT} valid resamples)")
        rows.append(dict(site=site, n_slides=len(true), n_patients=n_patients, rho=rho,
                          ci_lo=lo, ci_hi=hi, kind="leave-one-site-out"))

    stat_corr = pd.read_csv(STAT_CORR_CSV)
    pooled = stat_corr[stat_corr["test"].str.contains("AR score")].iloc[0]
    rows.append(dict(site="Pooled (5-fold internal CV, all sites)",
                      n_slides=int(pooled["n_slide"]), n_patients=int(pooled["n_patient"]),
                      rho=pooled["patient_metric"], ci_lo=pooled["patient_ci_lo"],
                      ci_hi=pooled["patient_ci_hi"], kind="pooled"))
    print(f"\nPooled (all-sites internal CV): rho={pooled['patient_metric']:+.3f} "
          f"[{pooled['patient_ci_lo']:+.3f}, {pooled['patient_ci_hi']:+.3f}]")

    loo_vals = [r["rho"] for r in rows if r["kind"] == "leave-one-site-out"]
    print(f"\nmean across {len(loo_vals)} held-out sites: {np.mean(loo_vals):+.3f} "
          f"(range {min(loo_vals):+.3f} to {max(loo_vals):+.3f})")

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    print(f"\nsaved {OUT_CSV}")


if __name__ == "__main__":
    main()
