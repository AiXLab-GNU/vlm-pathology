"""Re-embeds TCGA-PRAD with Virchow at LEOPARD's tile scale (~0.97um/px, TILES_PER_SLIDE=64)
instead of Virchow's own native ~0.5um/px (which pilot_virchow_tcga_prad_spop.py used) -- to
test whether the marker-7 zero-shot transfer failure with Virchow (C-index=0.545, near chance;
pilot_tcga_prad_recurrence_external_virchow.py) is a genuine absence of transferable Virchow
signal, or the same tile-scale-mismatch pitfall already established in this project (NADT/PANDA:
Virchow's zero-shot transfer collapsed at ~4x scale mismatch, recovered once re-embedded at a
matching scale -- CONCH tolerated the mismatch fine, Virchow did not). LEOPARD Virchow embeddings
were deliberately done at CONCH's scale (0.97um/px, ~2x off Virchow's native 0.5um/px) rather
than Virchow's own recommended scale, for a clean same-tiles cross-encoder comparison within
LEOPARD -- but that means applying the LEOPARD-fitted Virchow model zero-shot to TCGA-PRAD's
Virchow embeddings (tiled at the DIFFERENT 0.5um/px) carries exactly this kind of physical scale
mismatch. This script removes that confound by re-tiling TCGA-PRAD Virchow at 0.97um/px too.

Same tiling infrastructure as pilot_virchow_tcga_prad_spop.py (whole-page decode + random tissue
tiles, AppMag-derived pick_level, same 300-slide universe), only TARGET_MPP and TILES_PER_SLIDE
changed to match LEOPARD's Virchow recipe.

Run with the CONCH venv, on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_tcga_prad_recurrence_scalematch.py
"""
import os
import sys

import numpy as np
import pandas as pd
import timm
import torch
from PIL import Image
from timm.layers import SwiGLUPacked

sys.path.insert(0, os.path.dirname(__file__))
from pilot_virchow_tcga_prad_spop import (TCGA_ROOT, MANIFEST, SLIDE_DIR,  # noqa: E402
                                           pick_level, embed_tiles)
import tifffile

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache")

TARGET_MPP = 0.97          # matches LEOPARD Virchow's scale (deliberately not Virchow-native)
TILE_SIZE = 224
TILES_PER_SLIDE = 64       # matches LEOPARD Virchow's tile count
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 300
BATCH_SIZE = 32
SEED = 0


def load_slide_list():
    df = pd.read_csv(MANIFEST)
    df = df[df["erg_status"].isin(["fusion", "none"])].copy()  # same 300-slide universe
    return df.reset_index(drop=True)


def sample_tissue_tiles_scalematch(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    page = tf.pages[pick_level(tf, target_mpp=TARGET_MPP)]
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


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_slide_list()
    print(f"{len(df)} candidate slides across {df['case_id'].nunique()} patients")

    model = timm.create_model("hf-hub:paige-ai/Virchow", pretrained=True,
                               mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU)
    model = model.to(device).eval()
    cfg = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
    transform = timm.data.create_transform(**cfg)
    rng = np.random.default_rng(SEED)

    slide_vecs, case_ids, fnames, n_tiles_used = [], [], [], []
    for i, row in df.iterrows():
        path = os.path.join(SLIDE_DIR, row["file_name"])
        if not os.path.exists(path):
            continue
        tiles = sample_tissue_tiles_scalematch(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['file_name']}")
            continue
        feats = embed_tiles(model, transform, device, tiles)
        slide_vecs.append(feats.mean(axis=0))
        case_ids.append(row["case_id"])
        fnames.append(row["file_name"])
        n_tiles_used.append(len(tiles))
        print(f"[{i+1}/{len(df)}] {row['file_name']}: {len(tiles)} tiles embedded", flush=True)

        X = np.stack(slide_vecs)
        meta = pd.DataFrame(dict(file_name=fnames, case_id=case_ids, n_tiles=n_tiles_used))
        np.save(os.path.join(OUT_DIR, "X_scalematch_0.97mpp.npy"), X)
        meta.to_csv(os.path.join(OUT_DIR, "meta_scalematch_0.97mpp.csv"), index=False)

    print(f"\nDone. {len(slide_vecs)} slides embedded at {TARGET_MPP}um/px, cached to {OUT_DIR}")


if __name__ == "__main__":
    main()
