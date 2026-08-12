"""G-N5 pilot: linear probe on frozen CONCH embeddings, targeting our own dab_ring, evaluated
by WITHIN-SLIDE relative ranking only (never pooled absolute value) -- this discipline is the
direct lesson from the NADT P1 test (patient-level null; slide-level positive was
pseudo-replication) and is written into report.tex G-N5 for exactly this reason.

Unlike the zero-shot pilot (pilot_conch_similarity_feature.py, 6 hand-picked crops per slide,
weak/inconsistent), this uses ALL candidates find_gland_candidates() finds per slide (14-152
per slide, ~319 total after the shape-filter fix) -- each already has an auto-computed dab_ring,
no manual labeling needed.

Design:
  1. Crop every candidate lumen (in-memory, no PNGs written) and extract CONCH's raw
     pre-projection image feature (proj_contrast=False, normalize=False -- CONCH's own
     documented convention for image-only/downstream tasks, not the contrastive/text space).
  2. Target = within-slide percentile rank of dab_ring (0=lowest/most suspect-like,
     1=highest/most benign-like) -- rank-transforming per slide before pooling sidesteps the
     cross-slide absolute-scale problem (tab:dabvalues) instead of ignoring it.
  3. Leave-one-slide-out CV (4 folds): fit RidgeCV (with built-in efficient LOOCV alpha
     selection) on the other 3 slides' pooled (embedding, rank) pairs, predict on the held-out
     slide, then Spearman-correlate predictions against that slide's TRUE dab_ring -- entirely
     within-slide, matching G-N5's evaluation criterion.

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_linear_probe.py
"""
import os
import sys
import numpy as np
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "song-datasets", "_previews", "scripts"))
from common import FILES, load_level2, find_gland_candidates  # noqa: E402

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
CROP_SIZE = 900


def crop_array(arr, cx, cy, crop_size):
    half = crop_size // 2
    h, w, _ = arr.shape
    x0, x1 = int(max(0, cx - half)), int(min(w, cx + half))
    y0, y1 = int(max(0, cy - half)), int(min(h, cy + half))
    return arr[y0:y1, x0:x1]


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()

    per_slide = {}
    for fname in FILES:
        name = fname.replace(".svs", "")
        print(f"embedding {name} ...")
        _, arr = load_level2(fname)
        candidates, _ = find_gland_candidates(arr)
        feats, dabs = [], []
        with torch.inference_mode():
            for c in candidates:
                crop = crop_array(arr, c["cx"], c["cy"], CROP_SIZE)
                x = preprocess(Image.fromarray(crop).convert("RGB")).unsqueeze(0).to(device)
                f = model.encode_image(x, proj_contrast=False, normalize=False)
                feats.append(f.squeeze(0).cpu().numpy())
                dabs.append(c["dab"])
        feats = np.stack(feats)
        dabs = np.array(dabs)
        # within-slide percentile rank of dab_ring: 0=lowest dab (most suspect-like), 1=highest
        ranks = stats.rankdata(dabs) / len(dabs)
        per_slide[name] = dict(feats=feats, dabs=dabs, ranks=ranks)
        print(f"  {len(candidates)} candidates embedded (feat dim={feats.shape[1]})")

    names = list(per_slide.keys())
    print(f"\n{'='*80}\nLEAVE-ONE-SLIDE-OUT CV: predict within-slide dab_ring rank from CONCH embedding\n{'='*80}")
    fold_rhos = []
    for holdout in names:
        train_names = [n for n in names if n != holdout]
        X_train = np.concatenate([per_slide[n]["feats"] for n in train_names], axis=0)
        y_train = np.concatenate([per_slide[n]["ranks"] for n in train_names], axis=0)
        X_test = per_slide[holdout]["feats"]

        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X_train, y_train)
        pred = probe.predict(X_test)

        rho, p = stats.spearmanr(pred, per_slide[holdout]["dabs"])
        fold_rhos.append(rho)
        print(f"holdout={holdout:10s} n_train={len(y_train):4d} n_test={len(X_test):3d} "
              f"Spearman(pred, true dab_ring)={rho:+.3f}  p={p:.4g}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    print(f"per-fold Spearman rho: {[f'{r:+.3f}' for r in fold_rhos]}")
    print(f"mean rho={np.mean(fold_rhos):+.3f}  (positive expected: higher predicted rank "
          f"should track higher true dab_ring, i.e. more benign-like)")
    t, p = stats.ttest_1samp(fold_rhos, 0)
    print(f"one-sample t-test of fold rhos vs 0: t={t:.3f} p={p:.4g} (n=4 folds, read qualitatively)")


if __name__ == "__main__":
    main()
