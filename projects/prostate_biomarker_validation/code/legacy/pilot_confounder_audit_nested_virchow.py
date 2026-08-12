"""Virchow cross-check of the nested confounder audit for markers 4 (PTEN) and 6 (AR)
(major-revision follow-up, 2026-08-03): the CONCH nested audit
(pilot_confounder_audit_nested.py) found that PTEN's and AR's held-out incremental value over
grade is NOT statistically significant (95% CIs cross zero), reversing the earlier in-sample
LRT conclusion. Before restructuring the manuscript around that weakened claim, check whether
it's CONCH-specific or holds for an independently trained encoder too -- this project has
repeatedly found CONCH/Virchow results diverge (marker 7's zero-shot transfer asymmetry is the
clearest prior example), so a single-encoder nested result is not yet the strongest form of
evidence available.

Marker 7 is deliberately NOT re-audited here: its Virchow zero-shot transfer to TCGA-PRAD
already failed near-chance (C-index 0.545/0.533, Section~\ref{sec:res-marker7}), so a nested
Virchow marker-7 audit would not add information beyond what's already reported.

Reuses the exact nested pipeline from pilot_confounder_audit_nested.py (same outer/inner
patient-disjoint GroupKFold(5), same probe protocol, same 2,000-resample patient bootstrap) --
only the embedding source changes: resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/X_spop.npy (2560-dim Virchow
embeddings for the same 300-slide/273-patient TCGA-PRAD universe as the CONCH cache, confirmed
via direct row-order comparison to be in identical file_name/case_id order -- see
resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache/meta_spop.csv). Labels (gleason_sum, pten_loss, ar_score) are
pulled from the same cBioPortal JSON as the CONCH audit for an apples-to-apples comparison.

Run with the CONCH-only venv (CPU only, no GPU/re-embedding needed -- reuses cached Virchow
embeddings):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit_nested_virchow.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pilot_confounder_audit_nested import audit_tabular  # noqa: E402
from pilot_confounder_audit import CBIOPORTAL_SAMPLE_JSON  # noqa: E402

VIRCHOW_CACHE = os.path.join(ROOT, "virchow_tcga_prad_cache")
CONCH_META = os.path.join(ROOT, "tcga_prad_conch_cache", "meta.csv")
OUT_DIR = ROOT


def load_data_virchow():
    with open(CBIOPORTAL_SAMPLE_JSON) as f:
        data = json.load(f)
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]

    X = np.load(os.path.join(VIRCHOW_CACHE, "X_spop.npy"))
    meta = pd.read_csv(CONCH_META)  # same 300-row file_name/case_id order, confirmed directly
    assert len(meta) == len(X), f"row count mismatch: meta={len(meta)} X={len(X)}"

    meta["gleason_sum"] = meta["case_id"].map(by_attr["REVIEWED_GLEASON_SUM"]).astype(float)
    meta["pten_loss"] = meta["case_id"].map(by_attr["PTEN_CNA"]).isin(["hetloss", "homdel"]).astype(float)
    missing_pten = meta["case_id"].map(by_attr["PTEN_CNA"]).isna()
    meta.loc[missing_pten, "pten_loss"] = np.nan
    meta["ar_score"] = meta["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    return X, meta


def main():
    X, meta = load_data_virchow()
    print(f"Virchow TCGA-PRAD: n_slide={len(meta)}, n_patient={meta['case_id'].nunique()}")

    all_summary, all_folds, all_boot, all_predictions = [], [], [], []
    for args in ((X, meta, "pten_loss", "marker4_pten_virchow", "binary"),
                 (X, meta, "ar_score", "marker6_ar_virchow", "continuous")):
        summary, folds, boot, predictions = audit_tabular(*args)
        all_summary.extend(summary)
        all_folds.extend(folds)
        all_boot.append(boot)
        all_predictions.append(predictions)

    summary_df = pd.DataFrame(all_summary)
    for col in ("ci_low", "ci_high"):
        if col not in summary_df:
            summary_df[col] = np.nan
    summary_df.to_csv(os.path.join(OUT_DIR, "confounder_nested_virchow_summary.csv"), index=False)
    pd.DataFrame(all_folds).to_csv(
        os.path.join(OUT_DIR, "confounder_nested_virchow_folds.csv"), index=False)
    pd.concat(all_boot, ignore_index=True).to_csv(
        os.path.join(OUT_DIR, "confounder_nested_virchow_bootstrap.csv"), index=False)
    pd.concat(all_predictions, ignore_index=True, sort=False).to_csv(
        os.path.join(OUT_DIR, "confounder_nested_virchow_predictions.csv"), index=False)

    print(summary_df.to_string(index=False))
    print("\nComparison to CONCH nested result (pilot_confounder_audit_nested.py):")
    conch_path = os.path.join(OUT_DIR, "confounder_nested_summary.csv")
    if os.path.exists(conch_path):
        conch = pd.read_csv(conch_path)
        conch_patient = conch[(conch["scope"] == "patient") & (conch["analysis"] == "grade_only")]
        print(conch_patient[["marker", "delta", "ci_low", "ci_high"]].to_string(index=False))


if __name__ == "__main__":
    main()
