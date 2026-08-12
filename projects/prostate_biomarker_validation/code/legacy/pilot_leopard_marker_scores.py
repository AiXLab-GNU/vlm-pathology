"""Score the LEOPARD cohort (508 patients) with this project's existing marker probes,
zero-shot (no retraining, no LEOPARD data used to fit anything) -- the same discipline as
the NADT-fitted probe -> PANDA zero-shot transfer that established marker 1/2 as "Externally
transportable" (docs/03_experimental_results.md §1).

Markers scored: ① (H&E->Gleason, NADT-fitted), ② (H&E->Phenotype, NADT-fitted),
④ (H&E->PTEN loss, TCGA-PRAD-fitted), ⑤ (H&E->SPOP mutation, TCGA-PRAD-fitted, null --
included only for the All-candidate pool), ⑥ (H&E->AR score, TCGA-PRAD-fitted).

Marker ③ (ERG-stained image -> Gleason) is NOT scored: LEOPARD only has H&E prostatectomy
images, no ERG immunohistochemistry -- the modality marker 3 needs simply doesn't exist for
this cohort. This is a data-availability constraint, not a re-evaluation of marker 3's
qualification status (docs/10_protocol_freeze.md §8 keeps marker 3 qualified on its own
NADT/TCGA-PRAD evidence). Consequently, for LEOPARD specifically:
  - Naive pool   = {1, 2, 4, 6}   (all nominally-significant single-cohort candidates)
  - Qualified pool = {1, 2, 4}    (marker 6 excluded: site-instability, protocol_freeze §8)
  - All-candidate pool = {1, 2, 4, 5, 6}  (adds the null marker 5 and unstable marker 6)

Each probe is trained on its ENTIRE original training cohort (all of NADT / all of
TCGA-PRAD, not cross-validated folds) using the standardized protocol from
pilot_statistical_corrections.py (RidgeCV / LogisticRegression(C=1.0,
class_weight="balanced")) -- this matches exactly how the NADT-probe->PANDA zero-shot
transfer was done (docs/03 §2), so the resulting numbers are directly comparable in kind to
that prior transportability evidence.

Run with the CONCH-only venv (fast, no embedding, just probe fits + scoring):
    HF_HOME=~/.cache/huggingface-jhkim resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python \
        resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_marker_scores.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
OUT_CSV = os.path.join(LEOPARD_CACHE, "marker_scores.csv")

sys.path.insert(0, os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace"))
from pilot_confounder_audit import load_data as load_tcga_data  # noqa: E402


def fit_ridge(X, y):
    m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    m.fit(X, y)
    return m


def fit_logit(X, y):
    m = make_pipeline(StandardScaler(),
                       LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
    m.fit(X, y)
    return m


def main():
    leopard_X = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    leopard_meta = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    print(f"LEOPARD: {len(leopard_meta)} scored slides")

    scores = pd.DataFrame({"case_id": leopard_meta["case_id"],
                            "event": leopard_meta["event"],
                            "follow_up_years": leopard_meta["follow_up_years"]})

    # Marker 1: H&E -> Gleason score (NADT-fitted, full cohort)
    X_nadt1 = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta_nadt1 = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    m1 = fit_ridge(X_nadt1, meta_nadt1["gleason_total"].values)
    scores["marker1_gleason"] = m1.predict(leopard_X)
    print("marker 1 (Gleason) scored, NADT n=", len(meta_nadt1))

    # Marker 2: H&E -> Phenotype (tumor vs benign, NADT-fitted, full cohort)
    X_nadt2 = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
    meta_nadt2 = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
    m2 = fit_logit(X_nadt2, meta_nadt2["label"].values)
    scores["marker2_phenotype"] = m2.predict_proba(leopard_X)[:, 1]
    print("marker 2 (Phenotype) scored, NADT n=", len(meta_nadt2))

    # Markers 4/5/6: TCGA-PRAD-fitted (reuse pilot_confounder_audit's loader)
    X_tcga, meta_tcga = load_tcga_data()

    mask4 = meta_tcga["pten_loss"].notna()
    m4 = fit_logit(X_tcga[mask4.values], meta_tcga.loc[mask4, "pten_loss"].astype(int).values)
    scores["marker4_pten_loss"] = m4.predict_proba(leopard_X)[:, 1]
    print("marker 4 (PTEN loss) scored, TCGA-PRAD n=", mask4.sum())

    # SPOP label not in pilot_confounder_audit's loader -- pull it the same way as
    # pilot_conch_tcga_prad_multi.py (same cBioPortal JSON, already cached locally).
    import json
    from pilot_confounder_audit import CBIOPORTAL_SAMPLE_JSON, TCGA_CACHE
    data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
    meta_tcga["spop_mut"] = meta_tcga["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)
    mask5 = meta_tcga["spop_mut"].notna()
    m5 = fit_logit(X_tcga[mask5.values], meta_tcga.loc[mask5, "spop_mut"].astype(int).values)
    scores["marker5_spop_mut"] = m5.predict_proba(leopard_X)[:, 1]
    print("marker 5 (SPOP mutation, null) scored, TCGA-PRAD n=", mask5.sum())

    mask6 = meta_tcga["ar_score"].notna()
    m6 = fit_ridge(X_tcga[mask6.values], meta_tcga.loc[mask6, "ar_score"].values)
    scores["marker6_ar_score"] = m6.predict(leopard_X)
    print("marker 6 (AR score) scored, TCGA-PRAD n=", mask6.sum())

    scores.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV}")
    print(scores.describe())


if __name__ == "__main__":
    main()
