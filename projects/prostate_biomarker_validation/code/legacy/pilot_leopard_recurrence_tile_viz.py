"""Interpretability pass for the LEOPARD in-cohort recurrence signal (2026-07-31): what does
the CONCH+Virchow-shared, cross-encoder-reproducible recurrence-predictive direction actually
look at? Fits a single PCA(k=8)+Cox model on the FULL 508-patient CONCH cohort (not
cross-validated -- this script is for visualization, not a new performance claim), then scores
INDIVIDUAL TILES (not just the slide-mean embedding) from a handful of high- and low-predicted
patients to find which specific tile crops drive the score, and saves them as images for visual
inspection.

Selects patients from the extremes of the whole-cohort risk distribution (not necessarily the
extremes of true outcome, since the goal here is to see what the model is looking at, not to
re-validate accuracy).

Run with the CONCH-only venv, on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_leopard_recurrence_tile_viz.py
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis

sys.path.insert(0, os.path.dirname(__file__))
from pilot_conch_leopard_embed import sample_tiles, LEOPARD_DIR  # noqa: E402
from conch.open_clip_custom import create_model_from_pretrained

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
LEOPARD_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache/tile_viz")
os.makedirs(OUT_DIR, exist_ok=True)
N_PATIENTS_PER_EXTREME = 3
N_TILES_PER_PATIENT = 3


def main():
    X = np.load(os.path.join(LEOPARD_CACHE, "X.npy"))
    meta = pd.read_csv(os.path.join(LEOPARD_CACHE, "meta.csv"))
    event = meta["event"].values
    time = meta["follow_up_years"].values

    sc = StandardScaler().fit(X)
    Xz = sc.transform(X)
    pca = PCA(n_components=8, random_state=0).fit(Xz)
    Z = pca.transform(Xz)
    y_struct = np.array(list(zip(event.astype(bool), time)), dtype=[("event", bool), ("time", float)])
    cox = CoxPHSurvivalAnalysis(alpha=1.0).fit(Z, y_struct)
    slide_risk = cox.predict(Z)
    meta["slide_risk"] = slide_risk
    order = np.argsort(slide_risk)

    low_patients = meta.iloc[order[:N_PATIENTS_PER_EXTREME]]
    high_patients = meta.iloc[order[-N_PATIENTS_PER_EXTREME:]]
    print("Lowest-risk patients:\n", low_patients[["case_id", "event", "follow_up_years", "slide_risk"]])
    print("Highest-risk patients:\n", high_patients[["case_id", "event", "follow_up_years", "slide_risk"]])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = create_model_from_pretrained("conch_ViT-B-16", "hf_hub:MahmoodLab/conch")
    model = model.to(device).eval()
    rng = np.random.default_rng(1)  # different seed from training tiling, fresh sample

    def score_and_save(case_id, tag):
        tiles = sample_tiles(case_id, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tiles: {case_id}")
            return
        with torch.inference_mode():
            feats = []
            for i in range(0, len(tiles), 16):
                batch = tiles[i:i + 16]
                x = torch.stack([preprocess(Image.fromarray(np.asarray(t)).convert("RGB"))
                                  for t in batch]).to(device)
                f = model.encode_image(x, proj_contrast=False, normalize=False)
                feats.append(f.cpu().numpy())
        tile_feats = np.concatenate(feats, axis=0)
        tile_z = pca.transform(sc.transform(tile_feats))
        tile_scores = tile_z @ cox.coef_
        tile_order = np.argsort(tile_scores)

        for rank, idx in enumerate(list(tile_order[-N_TILES_PER_PATIENT:][::-1])):
            img = Image.fromarray(np.asarray(tiles[idx]).astype("uint8"))
            fn = os.path.join(OUT_DIR, f"{tag}_{case_id.replace('.tif','')}_topTile{rank}_score{tile_scores[idx]:.2f}.png")
            img.save(fn)
        for rank, idx in enumerate(list(tile_order[:N_TILES_PER_PATIENT])):
            img = Image.fromarray(np.asarray(tiles[idx]).astype("uint8"))
            fn = os.path.join(OUT_DIR, f"{tag}_{case_id.replace('.tif','')}_bottomTile{rank}_score{tile_scores[idx]:.2f}.png")
            img.save(fn)
        print(f"  {case_id}: tile score range [{tile_scores.min():.2f}, {tile_scores.max():.2f}], saved")

    print("\n--- Extracting extreme tiles from LOW slide-risk patients ---")
    for _, row in low_patients.iterrows():
        score_and_save(row["case_id"], "LOWslide")
    print("\n--- Extracting extreme tiles from HIGH slide-risk patients ---")
    for _, row in high_patients.iterrows():
        score_and_save(row["case_id"], "HIGHslide")

    print(f"\nSaved tile crops to {OUT_DIR}")


if __name__ == "__main__":
    main()
