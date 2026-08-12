"""Third independent G-N6 marker: same CONCH + RidgeCV + patient-disjoint methodology as
pilot_conch_nadt_probe.py (H&E -> Gleason score), but on ERG-stained slides instead of H&E.
ERG is the largest non-H&E IHC stain in NADT (151 TUMOR slides) and is a real, independent
image channel (not just a different patch sample of the same H&E image) -- this tests whether
CONCH's general-purpose embedding also carries useful signal on a stain it presumably saw far
less of during pretraining than routine H&E.

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_erg_probe.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd
import torch
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_conch_nadt_probe import (NADT_ROOT, CLINICAL_XLSX, MODEL_CFG, HF_HUB_ID,
                                     resolve_path, sample_tissue_tiles, embed_tiles)

OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
SEED = 0
STAIN = "ERG"


def load_erg_labels():
    df = pd.read_excel(CLINICAL_XLSX)
    df = df[(df["Stain"] == STAIN) & (df["Phenotype"] == "TUMOR")].copy()
    df = df[df["Gleason Score"].notna() & (df["Gleason Score"] != "N/A (metastatic)")]

    def parse_total(s):
        m = re.match(r"\s*(\d)\s*\+\s*(\d)\s*=\s*(\d+)", str(s))
        return int(m.group(3)) if m else None

    df["gleason_total"] = df["Gleason Score"].apply(parse_total)
    df = df[df["gleason_total"].notna()]
    return df.reset_index(drop=True)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_erg_labels()
    print(f"{len(df)} valid TUMOR {STAIN} slides across {df['Patient ID'].nunique()} patients")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    slide_vecs, patient_ids, gleason, fnames, n_tiles_used = [], [], [], [], []
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
        gleason.append(row["gleason_total"])
        fnames.append(row["File Name"])
        n_tiles_used.append(len(tiles))
        if len(slide_vecs) % 20 == 0:
            print(f"  ... {len(slide_vecs)}/{len(df)} slides embedded")

    X = np.stack(slide_vecs)
    y = np.array(gleason)
    groups = np.array(patient_ids)
    np.save(os.path.join(OUT_DIR, f"X_{STAIN}.npy"), X)
    pd.DataFrame(dict(file_name=fnames, patient_id=patient_ids, gleason_total=gleason,
                       n_tiles=n_tiles_used)).to_csv(
        os.path.join(OUT_DIR, f"meta_{STAIN}.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} slides ({X.shape[1]}-dim), saved to {OUT_DIR}")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof_pred = np.full(len(y), np.nan)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups)):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[tr_idx], y[tr_idx])
        oof_pred[te_idx] = probe.predict(X[te_idx])
        print(f"fold {fold}: train={len(tr_idx)} test={len(te_idx)}")

    print(f"\n{'='*80}\nPER-SLIDE ({STAIN} -> Gleason total, patient-disjoint pooled out-of-fold)\n{'='*80}")
    rho, p = stats.spearmanr(oof_pred, y)
    print(f"n={len(y)} slides, Spearman(pred, true gleason_total) = {rho:+.3f}  p={p:.4g}")

    df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof_pred, true=y))
    per_patient = df_eval.groupby("patient_id").mean()
    rho_p, p_p = stats.spearmanr(per_patient["pred"], per_patient["true"])
    print(f"n={len(per_patient)} patients, Spearman(mean pred, mean true gleason_total) = "
          f"{rho_p:+.3f}  p={p_p:.4g}")
    per_patient.to_csv(os.path.join(OUT_DIR, f"per_patient_{STAIN}_results.csv"))


if __name__ == "__main__":
    main()
