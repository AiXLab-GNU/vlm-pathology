"""Virchow (Paige AI) embedding of the LEOPARD cohort -- cross-encoder check for the
2026-07-31 domain-shift finding (docs/03_experimental_results.md §6d): CONCH found real
in-cohort recurrence signal (C-index 0.60-0.66, stable across PCA dims/seeds, survives a
landmark analysis restricted to patients with a known 3y/5y outcome) even though the
NADT/TCGA-PRAD-trained marker probes fail to zero-shot transfer. Before trusting that
CONCH-specific finding, check whether an entirely different foundation model (different
company, training corpus, architecture) finds the same kind of signal -- same discipline as
the marker 3 (ERG) and tile-scale-mismatch cross-model checks earlier in this project.

Reuses pilot_conch_leopard_embed.py's zarr-windowed tiling infrastructure (tissue-mask-based
tile selection, MAIN_LEVEL=1 ~0.97um/px) UNCHANGED -- same tiles, same scale, only the encoder
differs, so this is a clean like-for-like comparison of "does a different model see the same
signal," not confounded by also changing the tiling recipe. Honest caveat: 0.97um/px is
Virchow's own recommended native scale (~0.5um/px) off by roughly 2x in the coarse direction
-- LEOPARD's pyramid only offers 0.24um/px (2x too fine) or 0.97um/px (2x too coarse) as
alternatives, so some mismatch is unavoidable; kept identical to the CONCH run rather than
"optimized for Virchow" specifically to keep the comparison clean.

Embedding recipe matches pilot_virchow_nadt_probe.py: forward_features -> concat(CLS token,
mean of patch tokens) = 2560-dim (Virchow ViT-H/14, 1280-dim CLS + 1280-dim patch-mean).

Run with the CONCH venv (has timm/torch already), on a free GPU, in the background:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_leopard_embed.py
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
from pilot_conch_leopard_embed import LEOPARD_DIR, LABELS_CSV, tissue_tile_coords, MASK_LEVEL  # noqa: E402
import tifffile
import zarr

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_virchow_cache")
os.makedirs(OUT_DIR, exist_ok=True)

MAIN_LEVEL = 1
TILE_SIZE = 224            # Virchow native tile size (vs CONCH's 448) -- same MAIN_LEVEL,
                            # so this covers a quarter of the physical area per tile
TILES_PER_SLIDE = 64
BATCH_SIZE = 32


def sample_tiles_224(case_fname, rng):
    main_path = os.path.join(LEOPARD_DIR, case_fname)
    mask_path = os.path.join(LEOPARD_DIR, case_fname.replace(".tif", "_tissue.tif"))
    if not os.path.exists(main_path) or not os.path.exists(mask_path):
        return []
    tm = tifffile.TiffFile(main_path)
    tk = tifffile.TiffFile(mask_path)
    if MAIN_LEVEL >= len(tm.pages) or MASK_LEVEL >= len(tk.pages):
        return []
    main_page = tm.pages[MAIN_LEVEL]
    main_h, main_w = main_page.shape[0], main_page.shape[1]
    mask_arr = tk.pages[MASK_LEVEL].asarray()

    # reuse the shared coordinate-finding logic, just with this module's TILE_SIZE
    import pilot_conch_leopard_embed as embed_mod
    orig_tile_size, orig_stride = embed_mod.TILE_SIZE, embed_mod.GRID_STRIDE
    embed_mod.TILE_SIZE = TILE_SIZE
    embed_mod.GRID_STRIDE = TILE_SIZE
    try:
        coords = tissue_tile_coords(mask_arr, main_h, main_w)
    finally:
        embed_mod.TILE_SIZE, embed_mod.GRID_STRIDE = orig_tile_size, orig_stride

    if len(coords) == 0:
        return []
    if len(coords) > TILES_PER_SLIDE:
        idx = rng.choice(len(coords), size=TILES_PER_SLIDE, replace=False)
        coords = [coords[i] for i in idx]
    store = main_page.aszarr()
    z = zarr.open(store, mode="r")
    return [z[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE] for y0, x0 in coords]


@torch.inference_mode()
def embed_tiles(model, transform, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([transform(Image.fromarray(np.asarray(t)).convert("RGB"))
                          for t in batch]).to(device)
        out = model.forward_features(x)
        cls_token = out[:, 0]
        patch_mean = out[:, 1:].mean(dim=1)
        emb = torch.cat([cls_token, patch_mean], dim=-1)
        feats.append(emb.cpu().numpy())
    return np.concatenate(feats, axis=0)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    labels = pd.read_csv(LABELS_CSV)
    print(f"{len(labels)} labeled cases")

    model = timm.create_model("hf-hub:paige-ai/Virchow", pretrained=True,
                               mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU)
    model = model.to(device).eval()
    cfg = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
    transform = timm.data.create_transform(**cfg)
    rng = np.random.default_rng(0)

    done_path = os.path.join(OUT_DIR, "meta.csv")
    slide_vecs, rows = [], []
    done_cases = set()
    if os.path.exists(done_path):
        prev = pd.read_csv(done_path)
        done_cases = set(prev["case_id"])
        slide_vecs = list(np.load(os.path.join(OUT_DIR, "X.npy")))
        rows = prev.to_dict("records")
        print(f"resuming: {len(done_cases)} already embedded")

    for i, row in labels.iterrows():
        case_id = row["case_id"]
        if case_id in done_cases:
            continue
        tiles = sample_tiles_224(case_id, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tiles ({len(tiles)}): {case_id}")
            continue
        feats = embed_tiles(model, transform, device, tiles)
        slide_vecs.append(feats.mean(axis=0))
        rows.append(dict(case_id=case_id, event=row["event"],
                          follow_up_years=row["follow_up_years"], n_tiles=len(tiles)))
        print(f"[{i+1}/{len(labels)}] {case_id}: {len(tiles)} tiles embedded", flush=True)
        np.save(os.path.join(OUT_DIR, "X.npy"), np.array(slide_vecs))
        pd.DataFrame(rows).to_csv(done_path, index=False)

    print("Done.")


if __name__ == "__main__":
    main()
