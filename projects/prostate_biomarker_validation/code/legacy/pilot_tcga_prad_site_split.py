"""Partial external-validation substitute for markers (4)/(5)/(6), which currently have no
cross-institution check because their labels (PTEN_CNA, SPOP_MUTATION, AR_SCORE) come only
from TCGA-PRAD's cBioPortal molecular data -- NADT/PANDA don't have these labels at all.

TCGA-PRAD is itself a pooled multi-institution cohort (unlike PANDA's clean 2-site structure):
tissue_source_site codes embedded in the TCGA barcode (e.g. TCGA-EJ-xxxx -> site "EJ") show 22
distinct contributing hospitals, 6 with >=20 patients (EJ=59, HC=47, YL=22, KK=31, G9=27,
CH=23 -- slide counts; patient counts similar). This is NOT as strong as a genuinely separate
external cohort, but it's a real, free (already-downloaded) way to check whether these markers
generalize across different contributing hospitals within the same GDC-hosted dataset, rather
than only within a single patient-disjoint CV on pooled data.

Method: leave-one-site-out. For each of the 6 largest sites, train the probe on ALL OTHER
sites' data, test on that site alone. This is a stronger generalization test than plain
patient-disjoint CV (which mixes all sites in both train and test).

Run with the CONCH-only venv (fast, CPU only, reuses cached embeddings):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_site_split.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = str(Path(__file__).resolve().parents[4])
TCGA_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
MIN_SITE_SLIDES = 20


def load_data():
    meta = pd.read_csv(os.path.join(TCGA_CACHE, "meta.csv"))
    meta["site"] = meta["case_id"].str.split("-").str[1]

    by_attr = {}
    for d in json.load(open(CBIOPORTAL_SAMPLE_JSON)):
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    pten = meta["case_id"].map(by_attr["PTEN_CNA"])
    meta["pten_loss"] = pten.isin(["hetloss", "homdel"]).astype(float)
    meta.loc[pten.isna(), "pten_loss"] = np.nan
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    meta["spop_mut"] = meta["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)

    X = np.load(os.path.join(TCGA_CACHE, "X.npy"))
    return X, meta


def leave_site_out(X, y, sites, task, min_site_slides=MIN_SITE_SLIDES):
    mask = ~np.isnan(y)
    X, y, sites = X[mask], y[mask], sites[mask]
    if task == "binary":
        y = y.astype(int)

    site_counts = pd.Series(sites).value_counts()
    big_sites = site_counts[site_counts >= min_site_slides].index.tolist()

    per_site = []
    for site in big_sites:
        te_mask = sites == site
        tr_mask = ~te_mask
        y_tr, y_te = y[tr_mask], y[te_mask]
        if task == "binary":
            if len(np.unique(y_te)) < 2 or min((y_te == 0).sum(), (y_te == 1).sum()) < 5:
                continue
            probe = make_pipeline(StandardScaler(),
                                   LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
            probe.fit(X[tr_mask], y_tr)
            pred = probe.predict_proba(X[te_mask])[:, 1]
            m = roc_auc_score(y_te, pred)
        else:
            probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
            probe.fit(X[tr_mask], y_tr)
            pred = probe.predict(X[te_mask])
            m = stats.spearmanr(pred, y_te)[0]
        per_site.append((site, te_mask.sum(), m))
    return per_site


def main():
    X, meta = load_data()
    sites = meta["site"].values

    for name, col, task in [
        ("④ H&E -> PTEN loss", "pten_loss", "binary"),
        ("⑤ H&E -> SPOP mutation", "spop_mut", "binary"),
        ("⑥ H&E -> AR score", "ar_score", "continuous"),
    ]:
        print(f"\n{'='*70}\n{name}: leave-one-site-out (train on other sites, test on held-out site)\n{'='*70}")
        results = leave_site_out(X, meta[col].values, sites, task)
        metric_name = "AUROC" if task == "binary" else "rho"
        for site, n, m in results:
            sign = "+" if (task == "continuous" and m >= 0) else ""
            print(f"  held-out site {site} (n={n}): {metric_name}={sign}{m:.3f}")
        vals = [m for _, _, m in results]
        if vals:
            print(f"  mean across {len(vals)} held-out sites: {metric_name}={np.mean(vals):.3f} "
                  f"(range {min(vals):.3f} to {max(vals):.3f})")


if __name__ == "__main__":
    main()
