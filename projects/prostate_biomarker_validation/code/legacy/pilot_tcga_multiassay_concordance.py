"""TCGA-PRAD multi-assay molecular concordance, third item of docs/04_publication_strategy.md's
§7-1 / docs/10_protocol_freeze.md's confounder-audit step. Two distinct questions, kept
separate deliberately:

  (A) Assay concordance itself: does the categorical CNA/fusion-status label we trained the
      image probe against actually agree with independent molecular layers (mRNA expression,
      RPPA protein), i.e. is it measuring something real and not a CNA-calling artifact?
  (B) Does the IMAGE-derived probe score track those independent layers directly -- not just
      the training label -- which is a stronger check than (A) alone: if the image score only
      correlated with the possibly-noisy CNA call but not with mRNA/protein, that would suggest
      the probe learned to detect calling-pipeline artifacts rather than real PTEN-loss biology.

Per docs/04's existing (pre-registered) strength grading, kept as the interpretive frame here,
not re-derived: PTEN (CNA->mRNA->RPPA, three genuinely different measurement layers) = strong;
ERG (fusion status->expression) = medium; AR (expression->target-gene score, both RNA-derived,
less independent) = weaker, "pathway-level consistency" not "orthogonal assay validation".

Data: PTEN/ERG mRNA (RNA Seq V2 RSEM) and PTEN RPPA fetched from the public cBioPortal REST API
(prad_tcga_pub study) and cached locally in resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/{mrna_pten_erg,
rppa_pten}.json (see the curl commands in git history / session log for the exact fetch). AR
mRNA/protein were already present in the previously-downloaded clinical-sample JSON
(AR_MRNA, AR_PROTEIN attributes) -- no new fetch needed for AR.

Run with the CONCH-only venv:
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_multiassay_concordance.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from pilot_confounder_audit import (CBIOPORTAL_SAMPLE_JSON, TCGA_CACHE,  # noqa: E402
                                     image_oof_binary, image_oof_continuous)

MRNA_JSON = os.path.join(TCGA_CACHE, "mrna_pten_erg.json")
RPPA_JSON = os.path.join(TCGA_CACHE, "rppa_pten.json")


def load_all():
    data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
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
    meta["ar_mrna"] = meta["case_id"].map(by_attr["AR_MRNA"]).astype(float)
    meta["ar_protein"] = meta["case_id"].map(by_attr["AR_PROTEIN"]).astype(float)

    mrna = json.load(open(MRNA_JSON))
    mrna_df = pd.DataFrame(mrna)
    pten_mrna = mrna_df[mrna_df.entrezGeneId == 5728].set_index("patientId")["value"]
    erg_mrna = mrna_df[mrna_df.entrezGeneId == 2078].set_index("patientId")["value"]
    meta["pten_mrna"] = meta["case_id"].map(pten_mrna).astype(float)
    meta["erg_mrna"] = meta["case_id"].map(erg_mrna).astype(float)

    rppa = json.load(open(RPPA_JSON))
    rppa_df = pd.DataFrame(rppa).set_index("patientId")["value"]
    meta["pten_rppa"] = meta["case_id"].map(rppa_df).astype(float)

    return X, meta


def report_group_diff(y_binary, continuous, name_binary, name_continuous):
    mask = ~pd.isna(y_binary) & ~pd.isna(continuous)
    y = y_binary[mask].astype(int).values
    c = continuous[mask].values
    if y.sum() < 5 or (y == 0).sum() < 5:
        print(f"  [{name_binary} vs {name_continuous}] too few samples (n={mask.sum()}), skipping")
        return None
    u, p = stats.mannwhitneyu(c[y == 1], c[y == 0], alternative="two-sided")
    med1, med0 = np.median(c[y == 1]), np.median(c[y == 0])
    print(f"  [{name_binary} vs {name_continuous}] n={mask.sum()} "
          f"(pos={y.sum()}, neg={(y==0).sum()}): median[pos]={med1:.2f} vs "
          f"median[neg]={med0:.2f}, Mann-Whitney p={p:.4g}")
    return dict(n=int(mask.sum()), median_pos=med1, median_neg=med0, p=p)


def report_corr(a, b, name_a, name_b):
    mask = ~pd.isna(a) & ~pd.isna(b)
    if mask.sum() < 10:
        print(f"  [{name_a} vs {name_b}] too few samples (n={mask.sum()}), skipping")
        return None
    rho, p = stats.spearmanr(a[mask], b[mask])
    print(f"  [{name_a} vs {name_b}] n={mask.sum()}: rho={rho:+.3f}  p={p:.4g}")
    return dict(n=int(mask.sum()), rho=rho, p=p)


def pten_concordance(X, meta):
    print(f"\n{'='*90}\nPTEN: CNA loss -> mRNA -> RPPA concordance (assay layers, independent of image)\n{'='*90}")
    report_group_diff(meta["pten_loss"], meta["pten_mrna"], "PTEN CNA loss", "PTEN mRNA")
    report_group_diff(meta["pten_loss"], meta["pten_rppa"], "PTEN CNA loss", "PTEN RPPA protein")
    report_corr(meta["pten_mrna"], meta["pten_rppa"], "PTEN mRNA", "PTEN RPPA protein")

    print(f"\n{'-'*90}\nPTEN: does the IMAGE-derived probe score track mRNA/RPPA directly "
          f"(not just the CNA training label)?\n{'-'*90}")
    mask = meta["pten_loss"].notna()
    y = meta.loc[mask, "pten_loss"].astype(int).values
    groups = meta.loc[mask, "case_id"].values
    img_oof = image_oof_binary(X[mask.values], y, groups)
    img_series = pd.Series(img_oof, index=meta.index[mask])
    report_corr(img_series, meta["pten_mrna"], "image PTEN-loss score", "PTEN mRNA")
    report_corr(img_series, meta["pten_rppa"], "image PTEN-loss score", "PTEN RPPA protein")


def erg_concordance(X, meta):
    print(f"\n{'='*90}\nERG: fusion status -> mRNA concordance (assay layers, independent of image)\n{'='*90}")
    report_group_diff(meta["erg_fusion"].astype(float), meta["erg_mrna"], "ERG fusion", "ERG mRNA")

    print(f"\n{'-'*90}\nERG: does the IMAGE-derived probe score (H&E->fusion status, NOT marker 3) "
          f"track ERG mRNA directly?\n{'-'*90}")
    mask = meta["erg_fusion"].notna()
    y = meta.loc[mask, "erg_fusion"].astype(int).values
    groups = meta.loc[mask, "case_id"].values
    img_oof = image_oof_binary(X[mask.values], y, groups)
    img_series = pd.Series(img_oof, index=meta.index[mask])
    report_corr(img_series, meta["erg_mrna"], "image ERG-fusion score", "ERG mRNA")


def ar_concordance(X, meta):
    print(f"\n{'='*90}\nAR: SCORE vs mRNA vs RPPA protein (all partly RNA-derived, weaker "
          f"independence per docs/04 -- 'pathway-level consistency' not orthogonal validation)\n{'='*90}")
    report_corr(meta["ar_score"], meta["ar_mrna"], "AR_SCORE", "AR mRNA")
    report_corr(meta["ar_score"], meta["ar_protein"], "AR_SCORE", "AR RPPA protein")
    report_corr(meta["ar_mrna"], meta["ar_protein"], "AR mRNA", "AR RPPA protein")

    print(f"\n{'-'*90}\nAR: does the IMAGE-derived probe score (trained on AR_SCORE, marker 6) "
          f"track AR mRNA/protein directly?\n{'-'*90}")
    mask = meta["ar_score"].notna()
    y = meta.loc[mask, "ar_score"].values
    groups = meta.loc[mask, "case_id"].values
    img_oof = image_oof_continuous(X[mask.values], y, groups)
    img_series = pd.Series(img_oof, index=meta.index[mask])
    report_corr(img_series, meta["ar_mrna"], "image AR-score probe", "AR mRNA")
    report_corr(img_series, meta["ar_protein"], "image AR-score probe", "AR RPPA protein")


def main():
    X, meta = load_all()
    pten_concordance(X, meta)
    erg_concordance(X, meta)
    ar_concordance(X, meta)


if __name__ == "__main__":
    main()
