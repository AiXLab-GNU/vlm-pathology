"""Stability check for pilot_conch_nadt_mil.py's attention-MIL result (single seed: slide
rho=+0.545, patient rho=+0.628, vs 16-tile-mean baseline +0.312/+0.478) -- the attention model
has ~66k params against ~267 training slides/fold, so before trusting the improvement, rerun
training across multiple random seeds and report the distribution, not just one lucky draw.

Reuses cached tile embeddings (embedding itself is deterministic given SEED=0 tile sampling,
so it's cached to disk once here rather than recomputed per training seed -- only the attention
model's training stochasticity varies across runs).

Run with the CONCH-only venv:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_mil_seeds.py
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
from scipy import stats
from sklearn.model_selection import GroupKFold
from conch.open_clip_custom import create_model_from_pretrained

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_conch_nadt_probe import load_labels, resolve_path, MODEL_CFG, HF_HUB_ID
from pilot_conch_nadt_mil import sample_tissue_tiles, embed_tiles, AttentionMIL, TILES_PER_SLIDE

OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
BAGS_PATH = os.path.join(OUT_DIR, "bags_64tile.npy")
META_PATH = os.path.join(OUT_DIR, "meta_64tile_bags.csv")
TILE_SAMPLING_SEED = 0
N_SEEDS = 10
N_SPLITS = 5


def build_or_load_cache():
    if os.path.exists(BAGS_PATH) and os.path.exists(META_PATH):
        print(f"loading cached bags from {BAGS_PATH}")
        return np.load(BAGS_PATH), pd.read_csv(META_PATH)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_labels()
    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(TILE_SAMPLING_SEED)

    bags, patient_ids, gleason, fnames = [], [], [], []
    for i, row in df.iterrows():
        path = resolve_path(row["File Name"])
        if path is None:
            continue
        tiles = sample_tissue_tiles(path, rng, TILES_PER_SLIDE)
        if len(tiles) < TILES_PER_SLIDE:
            print(f"  [skip] incomplete tiles ({len(tiles)}): {row['File Name']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        bags.append(feats)
        patient_ids.append(row["Patient ID"])
        gleason.append(row["gleason_total"])
        fnames.append(row["File Name"])
        if len(bags) % 40 == 0:
            print(f"  ... {len(bags)}/{len(df)} embedded")

    bags_arr = np.stack(bags)  # (n_slides, TILES_PER_SLIDE, 512) -- fixed tile count, dense array
    np.save(BAGS_PATH, bags_arr)
    meta = pd.DataFrame(dict(file_name=fnames, patient_id=patient_ids, gleason_total=gleason))
    meta.to_csv(META_PATH, index=False)
    print(f"cached {bags_arr.shape} to {BAGS_PATH}")
    return bags_arr, meta


def train_attention_mil_seeded(bags_train, y_train, bags_test, device, seed, epochs=40, lr=1e-3, wd=1e-2):
    torch.manual_seed(seed)
    rs = np.random.RandomState(seed)
    model = AttentionMIL().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    bags_train_t = [torch.tensor(b, dtype=torch.float32, device=device) for b in bags_train]
    y_train_t = torch.tensor(y_train, dtype=torch.float32, device=device)
    for epoch in range(epochs):
        perm = rs.permutation(len(bags_train_t))
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
            pred, _ = model(torch.tensor(b, dtype=torch.float32, device=device))
            preds.append(pred.item())
    return np.array(preds)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    bags_arr, meta = build_or_load_cache()
    y = meta["gleason_total"].values
    groups = meta["patient_id"].values
    gkf = GroupKFold(n_splits=N_SPLITS)
    fold_splits = list(gkf.split(bags_arr, y, groups))

    slide_rhos, patient_rhos = [], []
    for seed in range(N_SEEDS):
        oof = np.full(len(y), np.nan)
        for tr_idx, te_idx in fold_splits:
            train_concat = bags_arr[tr_idx].reshape(-1, bags_arr.shape[-1])
            mu, sigma = train_concat.mean(axis=0), train_concat.std(axis=0) + 1e-6
            bags_train = [(bags_arr[i] - mu) / sigma for i in tr_idx]
            bags_test = [(bags_arr[i] - mu) / sigma for i in te_idx]
            preds = train_attention_mil_seeded(bags_train, y[tr_idx], bags_test, device, seed=seed)
            oof[te_idx] = preds
        rho_s, _ = stats.spearmanr(oof, y)
        df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof, true=y))
        pp = df_eval.groupby("patient_id").mean()
        rho_p, _ = stats.spearmanr(pp["pred"], pp["true"])
        slide_rhos.append(rho_s)
        patient_rhos.append(rho_p)
        print(f"seed {seed}: slide rho={rho_s:+.3f}  patient rho={rho_p:+.3f}")

    print(f"\n{'='*80}\nSTABILITY ACROSS {N_SEEDS} SEEDS\n{'='*80}")
    print(f"slide-level:   mean={np.mean(slide_rhos):+.3f}  std={np.std(slide_rhos):.3f}  "
          f"min={min(slide_rhos):+.3f}  max={max(slide_rhos):+.3f}")
    print(f"patient-level: mean={np.mean(patient_rhos):+.3f}  std={np.std(patient_rhos):.3f}  "
          f"min={min(patient_rhos):+.3f}  max={max(patient_rhos):+.3f}")
    print(f"\nreference -- 16-tile mean baseline: slide rho=+0.312, patient rho=+0.478")
    print(f"reference -- 64-tile mean (coverage only): slide rho=+0.411, patient rho=+0.479")


if __name__ == "__main__":
    main()
