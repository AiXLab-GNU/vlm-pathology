"""Improve on pilot_conch_nadt_probe.py's aggregation (random 16 tiles -> plain mean, the
weakest link the user flagged: "some tumor-relevant patches may simply not get sampled, or get
diluted by averaging with irrelevant stroma"). Tests two changes, isolated so we know which one
actually matters, not conflated:

  (1) COVERAGE ONLY: same plain mean-pooling, but 64 tiles/slide instead of 16 -- cheap, safe,
      no new learned component, isolates whether more coverage alone helps.
  (2) ATTENTION MIL: a small learned attention-pooling head (Ilse et al. 2018 style, the same
      core mechanism CLAM uses -- report.tex §8.1) replaces the plain mean, letting the model
      learn per-tile weights instead of treating every sampled patch as equally relevant.
      Deliberately tiny (512->128->1 attention MLP + linear head, ~66k params) and regularized
      (weight decay, few epochs) given the small patient count (39) -- the whole point of this
      project's fusion experiment was that small-sample *learned* combination is fragile, so
      this is evaluated skeptically against the same risk, not assumed to help.

Both use the same patient-disjoint 5-fold GroupKFold as every other NADT experiment this
session. Baseline for comparison: original 16-tile mean, slide rho=+0.312, patient rho=+0.478
(pilot_conch_nadt_probe.py).

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_mil.py
"""
import os
import sys

import numpy as np
import pandas as pd
import tifffile
import torch
import torch.nn as nn
from PIL import Image
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_conch_nadt_probe import load_labels, resolve_path, MODEL_CFG, HF_HUB_ID, PYRAMID_LEVEL, TILE_SIZE

OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
TILES_PER_SLIDE = 64
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 400
BATCH_SIZE = 32
SEED = 0
N_SPLITS = 5


def sample_tissue_tiles(path, rng, n_tiles):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []  # corrupted/empty TIFF (seen once in NADT: no IFDs at all)
    page = tf.pages[PYRAMID_LEVEL] if len(tf.pages) > PYRAMID_LEVEL else tf.pages[-1]
    arr = page.asarray()
    h, w = arr.shape[0], arr.shape[1]
    if h < TILE_SIZE or w < TILE_SIZE:
        return []
    tiles = []
    attempts = 0
    while len(tiles) < n_tiles and attempts < MAX_GRID_ATTEMPTS:
        attempts += 1
        y0 = rng.integers(0, h - TILE_SIZE)
        x0 = rng.integers(0, w - TILE_SIZE)
        crop = arr[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE]
        gray = crop.mean(axis=2)
        if (gray < 205).mean() >= TISSUE_FRACTION_MIN:
            tiles.append(crop)
    return tiles


@torch.inference_mode()
def embed_tiles(model, preprocess, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([preprocess(Image.fromarray(t).convert("RGB")) for t in batch]).to(device)
        f = model.encode_image(x, proj_contrast=False, normalize=False)
        feats.append(f.cpu().numpy())
    return np.concatenate(feats, axis=0)


class AttentionMIL(nn.Module):
    def __init__(self, dim=512, hidden=128):
        super().__init__()
        self.attention = nn.Sequential(nn.Linear(dim, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.regressor = nn.Linear(dim, 1)

    def forward(self, tiles):  # tiles: (n_tiles, dim), standardized
        logits = self.attention(tiles).squeeze(-1)
        weights = torch.softmax(logits, dim=0)
        pooled = (weights.unsqueeze(-1) * tiles).sum(dim=0)
        return self.regressor(pooled).squeeze(-1), weights


def train_attention_mil(bags_train, y_train, bags_test, device, epochs=40, lr=1e-3, wd=1e-2):
    torch.manual_seed(SEED)
    model = AttentionMIL().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    bags_train_t = [torch.tensor(b, dtype=torch.float32, device=device) for b in bags_train]
    y_train_t = torch.tensor(y_train, dtype=torch.float32, device=device)
    for epoch in range(epochs):
        perm = np.random.permutation(len(bags_train_t))
        model.train()
        for i in perm:
            opt.zero_grad()
            pred, _ = model(bags_train_t[i])
            loss = (pred - y_train_t[i]) ** 2
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for b in bags_test:
            bt = torch.tensor(b, dtype=torch.float32, device=device)
            pred, _ = model(bt)
            preds.append(pred.item())
    return np.array(preds)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_labels()
    print(f"{len(df)} valid TUMOR H&E slides across {df['Patient ID'].nunique()} patients")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    bags, patient_ids, gleason, fnames = [], [], [], []
    for i, row in df.iterrows():
        path = resolve_path(row["File Name"])
        if path is None:
            continue
        tiles = sample_tissue_tiles(path, rng, TILES_PER_SLIDE)
        if len(tiles) < 8:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['File Name']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        bags.append(feats)
        patient_ids.append(row["Patient ID"])
        gleason.append(row["gleason_total"])
        fnames.append(row["File Name"])
        if len(bags) % 40 == 0:
            print(f"  ... {len(bags)}/{len(df)} slides embedded (mean n_tiles so far: "
                  f"{np.mean([len(b) for b in bags]):.1f})")

    y = np.array(gleason)
    groups = np.array(patient_ids)
    n_tiles_actual = [len(b) for b in bags]
    print(f"\nembedded {len(bags)} slides, tiles/slide: mean={np.mean(n_tiles_actual):.1f} "
          f"min={min(n_tiles_actual)} max={max(n_tiles_actual)}")

    mean_pooled = np.stack([b.mean(axis=0) for b in bags])
    np.save(os.path.join(OUT_DIR, "X_64tile_mean.npy"), mean_pooled)
    pd.DataFrame(dict(file_name=fnames, patient_id=patient_ids, gleason_total=gleason,
                       n_tiles=n_tiles_actual)).to_csv(
        os.path.join(OUT_DIR, "meta_64tile.csv"), index=False)

    gkf = GroupKFold(n_splits=N_SPLITS)

    print(f"\n{'='*80}\n(1) COVERAGE ONLY: 64-tile mean pooling + RidgeCV\n{'='*80}")
    oof_mean = np.full(len(y), np.nan)
    for tr_idx, te_idx in gkf.split(mean_pooled, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(mean_pooled[tr_idx], y[tr_idx])
        oof_mean[te_idx] = probe.predict(mean_pooled[te_idx])
    rho_mean, p_mean = stats.spearmanr(oof_mean, y)
    print(f"slide-level (n={len(y)}): Spearman rho={rho_mean:+.3f} p={p_mean:.4g} "
          f"(baseline with 16 tiles was rho=+0.312)")
    df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof_mean, true=y))
    pp = df_eval.groupby("patient_id").mean()
    rho_mean_p, p_mean_p = stats.spearmanr(pp["pred"], pp["true"])
    print(f"patient-level (n={len(pp)}): Spearman rho={rho_mean_p:+.3f} p={p_mean_p:.4g} "
          f"(baseline with 16 tiles was rho=+0.478)")

    print(f"\n{'='*80}\n(2) ATTENTION MIL: learned per-tile weighting\n{'='*80}")
    oof_attn = np.full(len(y), np.nan)
    # standardize per-fold using train-fold statistics (fit on the concatenation of all training tiles)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(mean_pooled, y, groups)):
        train_concat = np.concatenate([bags[i] for i in tr_idx], axis=0)
        mu, sigma = train_concat.mean(axis=0), train_concat.std(axis=0) + 1e-6
        bags_train = [(bags[i] - mu) / sigma for i in tr_idx]
        bags_test = [(bags[i] - mu) / sigma for i in te_idx]
        preds = train_attention_mil(bags_train, y[tr_idx], bags_test, device)
        oof_attn[te_idx] = preds
        print(f"fold {fold}: train={len(tr_idx)} test={len(te_idx)} done")

    rho_attn, p_attn = stats.spearmanr(oof_attn, y)
    print(f"slide-level (n={len(y)}): Spearman rho={rho_attn:+.3f} p={p_attn:.4g}")
    df_eval2 = pd.DataFrame(dict(patient_id=groups, pred=oof_attn, true=y))
    pp2 = df_eval2.groupby("patient_id").mean()
    rho_attn_p, p_attn_p = stats.spearmanr(pp2["pred"], pp2["true"])
    print(f"patient-level (n={len(pp2)}): Spearman rho={rho_attn_p:+.3f} p={p_attn_p:.4g}")

    print(f"\n{'='*80}\nSUMMARY (baseline: 16-tile mean, slide rho=+0.312, patient rho=+0.478)\n{'='*80}")
    print(f"64-tile mean (coverage only):  slide rho={rho_mean:+.3f}  patient rho={rho_mean_p:+.3f}")
    print(f"64-tile attention MIL:         slide rho={rho_attn:+.3f}  patient rho={rho_attn_p:+.3f}")


if __name__ == "__main__":
    main()
