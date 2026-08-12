"""Systematic cross-model extension (2026-07-28): marker (1) (NADT H&E -> Gleason score) with
Virchow (Paige AI) instead of CONCH, on the identical 334-slide/39-patient cohort as
pilot_conch_nadt_probe.py. Part of extending the CONCH+Virchow cross-model discipline (already
applied to markers 3 and 5) to the whole marker pool, so every marker in the paper gets the same
treatment rather than an ad hoc subset.

Tiling: NADT's ERG files were confirmed (2026-07-28) to carry a valid, consistent XResolution
tag with native mpp=0.220 at pyramid level 0; level 1 (2x downsample) gives ~0.44um/px, the
closest match to Virchow's ~0.5um/px native training scale (vs CONCH's fixed level 2, ~0.88um/px).
Assumed consistent across NADT's H&E files too (same scanner/pipeline as ERG).

Run with the CONCH venv (has timm/torch already) on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_nadt_probe.py
"""
import glob
import os
import re

import numpy as np
import pandas as pd
import tifffile
import timm
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from timm.layers import SwiGLUPacked

NADT_ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/NADT-Prostate_v1"
CLINICAL_XLSX = os.path.join(NADT_ROOT, "Biopsy-Clinical-Data.xlsx")
OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache"
os.makedirs(OUT_DIR, exist_ok=True)

PYRAMID_LEVEL = 1
TILE_SIZE = 224
TILES_PER_SLIDE = 16
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 32
SEED = 0


def resolve_path(fname):
    hits = glob.glob(os.path.join(NADT_ROOT, "*", fname))
    return hits[0] if hits else None


def load_gleason_labels():
    df = pd.read_excel(CLINICAL_XLSX)
    df = df[(df["Stain"] == "H&E") & (df["Phenotype"] == "TUMOR")].copy()
    df = df[df["Gleason Score"].notna() & (df["Gleason Score"] != "N/A (metastatic)")]

    def parse_total(s):
        m = re.match(r"\s*(\d)\s*\+\s*(\d)\s*=\s*(\d+)", str(s))
        return int(m.group(3)) if m else None

    df["gleason_total"] = df["Gleason Score"].apply(parse_total)
    df = df[df["gleason_total"].notna()]
    return df.reset_index(drop=True)


def sample_tissue_tiles(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    page = tf.pages[PYRAMID_LEVEL] if len(tf.pages) > PYRAMID_LEVEL else tf.pages[-1]
    arr = page.asarray()
    if arr.ndim != 3:
        return []
    h, w = arr.shape[0], arr.shape[1]
    if h < TILE_SIZE or w < TILE_SIZE:
        return []
    tiles = []
    attempts = 0
    while len(tiles) < TILES_PER_SLIDE and attempts < MAX_GRID_ATTEMPTS:
        attempts += 1
        y0 = rng.integers(0, h - TILE_SIZE)
        x0 = rng.integers(0, w - TILE_SIZE)
        crop = arr[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE]
        gray = crop[..., :3].mean(axis=2)
        tissue_frac = (gray < 205).mean()
        if tissue_frac >= TISSUE_FRACTION_MIN:
            tiles.append(crop[..., :3])
    return tiles


@torch.inference_mode()
def embed_tiles(model, transform, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([transform(Image.fromarray(t).convert("RGB")) for t in batch]).to(device)
        out = model.forward_features(x)
        cls_token = out[:, 0]
        patch_mean = out[:, 1:].mean(dim=1)
        emb = torch.cat([cls_token, patch_mean], dim=-1)
        feats.append(emb.cpu().numpy())
    return np.concatenate(feats, axis=0)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}")
    df = load_gleason_labels()
    print(f"{len(df)} valid TUMOR H&E slides across {df['Patient ID'].nunique()} patients")

    model = timm.create_model("hf-hub:paige-ai/Virchow", pretrained=True,
                               mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU)
    model = model.to(device).eval()
    cfg = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
    transform = timm.data.create_transform(**cfg)
    rng = np.random.default_rng(SEED)

    slide_vecs, patient_ids, gleason, fnames, n_tiles_used = [], [], [], [], []
    for i, row in df.iterrows():
        path = resolve_path(row["File Name"])
        if path is None:
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['File Name']}")
            continue
        feats = embed_tiles(model, transform, device, tiles)
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
    np.save(os.path.join(OUT_DIR, "X.npy"), X)
    meta = pd.DataFrame(dict(file_name=fnames, patient_id=patient_ids, gleason_total=gleason,
                              n_tiles=n_tiles_used))
    meta.to_csv(os.path.join(OUT_DIR, "meta.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} slides ({X.shape[1]}-dim Virchow), cached to {OUT_DIR}")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof_pred = np.full(len(y), np.nan)
    for tr_idx, te_idx in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[tr_idx], y[tr_idx])
        oof_pred[te_idx] = probe.predict(X[te_idx])

    rho, p = stats.spearmanr(oof_pred, y)
    print(f"\nn={len(y)} slides, Virchow H&E->Gleason: slide rho={rho:+.3f}  p={p:.4g}")
    df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof_pred, true=y))
    per_patient = df_eval.groupby("patient_id").mean()
    rho_p, p_p = stats.spearmanr(per_patient["pred"], per_patient["true"])
    print(f"n={len(per_patient)} patients, patient rho={rho_p:+.3f}  p={p_p:.4g}")
    per_patient.to_csv(os.path.join(OUT_DIR, "per_patient_results.csv"))
    print(f"\nFor comparison, CONCH: slide rho=+0.312 (64tile +0.411), patient rho=+0.478/+0.479")


if __name__ == "__main__":
    main()
