"""Second NADT marker (G-N6 pool expansion): Phenotype classification (BENIGN vs TUMOR),
reusing pilot_conch_nadt_probe.py's tiling/embedding machinery. Unlike the Gleason-score probe
(restricted to Phenotype=='TUMOR' slides only), this uses the broader H&E cohort (463 slides,
39 patients, 128 BENIGN + 335 TUMOR) -- a different, independent marker for the G-N6 pool, not
just the same one restated.

HGPIN (18) and ATYPICAL (8) phenotypes exist in the data but are too small for a trustworthy
held-out multi-class evaluation alongside patient-disjoint CV, so this pilot deliberately scopes
to the two large classes (BENIGN vs TUMOR) rather than force a 4-class problem on cells too
small to trust -- consistent with this project's practice of not overclaiming from underpowered
splits (same reasoning as the CONCH GNUH pilot's small per-slide n).

17/39 patients have BOTH benign and tumor H&E slides -- expected biologically (a patient can
have some benign and some cancerous cores), not a leakage problem, since GroupKFold keeps all
of a patient's slides (whichever phenotype) in the same fold.

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_phenotype.py
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_conch_nadt_probe import (NADT_ROOT, CLINICAL_XLSX, MODEL_CFG, HF_HUB_ID,
                                     resolve_path, sample_tissue_tiles, embed_tiles)

OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
SEED = 0


def load_phenotype_labels():
    df = pd.read_excel(CLINICAL_XLSX)
    df = df[(df["Stain"] == "H&E") & (df["Phenotype"].isin(["BENIGN", "TUMOR"]))].copy()
    df["label"] = (df["Phenotype"] == "TUMOR").astype(int)
    return df.reset_index(drop=True)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_phenotype_labels()
    print(f"{len(df)} H&E slides (BENIGN/TUMOR only) across {df['Patient ID'].nunique()} patients")
    print(df["Phenotype"].value_counts().to_dict())

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    slide_vecs, patient_ids, labels, fnames = [], [], [], []
    for i, row in df.iterrows():
        path = resolve_path(row["File Name"])
        if path is None:
            print(f"  [skip] file not found: {row['File Name']}")
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['File Name']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        slide_vecs.append(feats.mean(axis=0))
        patient_ids.append(row["Patient ID"])
        labels.append(row["label"])
        fnames.append(row["File Name"])
        if len(slide_vecs) % 40 == 0:
            print(f"  ... {len(slide_vecs)}/{len(df)} slides embedded")

    X = np.stack(slide_vecs)
    y = np.array(labels)
    groups = np.array(patient_ids)
    np.save(os.path.join(OUT_DIR, "X_phenotype.npy"), X)
    pd.DataFrame(dict(file_name=fnames, patient_id=patient_ids, label=labels)).to_csv(
        os.path.join(OUT_DIR, "meta_phenotype.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} slides, saved to {OUT_DIR}")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof_pred = np.full(len(y), np.nan)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups)):
        probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
        probe.fit(X[tr_idx], y[tr_idx])
        oof_pred[te_idx] = probe.predict_proba(X[te_idx])[:, 1]
        print(f"fold {fold}: train={len(tr_idx)} test={len(te_idx)}")

    print(f"\n{'='*80}\nPHENOTYPE (BENIGN vs TUMOR), patient-disjoint pooled out-of-fold\n{'='*80}")
    auc = roc_auc_score(y, oof_pred)
    print(f"n={len(y)} slides, AUROC(pred, true phenotype) = {auc:.3f}")

    df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof_pred, true=y))
    per_patient = df_eval.groupby("patient_id").mean()
    if per_patient["true"].nunique() > 1:
        rho_p, p_p = stats.spearmanr(per_patient["pred"], per_patient["true"])
        print(f"patient-level (n={len(per_patient)}, mean pred vs mean true fraction-tumor): "
              f"Spearman rho={rho_p:+.3f} p={p_p:.4g}")
    per_patient.to_csv(os.path.join(OUT_DIR, "per_patient_phenotype_results.csv"))


if __name__ == "__main__":
    main()
