"""CONCH embedding of the LEOPARD cohort (508 patients, Radboudumc, real biochemical
recurrence labels), for docs/04_publication_strategy.md execution-order step 3 (LEOPARD
3-pool survival analysis).

Pyramid structure verified across 6 random samples + slide 0000 before committing to this
(same discipline as the TCGA-PRAD resolution-bug fix -- always confirm the physical scale,
don't assume): every LEOPARD main WSI has XResolution -> mpp level0 = 0.2425 um/px
(consistent across all checked slides), page 1 is a clean 4x downsample (~0.97 um/px, close
to this project's established ~0.88 um/px NADT/PANDA CONCH tiling scale -- a ~10% mismatch,
far smaller than the ~2x/~4x mismatches seen in the PANDA/Virchow cross-cohort work, so used
directly rather than resampled). Each WSI ships with its own tissue mask
(case_*_tissue.tif, binary 0/1), whose page 0 always matches the MAIN image's page 2 shape
exactly (one more 4x downsample from page 1) -- i.e. main-page1 pixel (x,y) maps to
mask-page0 pixel (x//4, y//4). Using the provided mask instead of a hand-rolled
non-white-pixel heuristic, since it's real tissue segmentation, not a proxy.

Tiles are read via tifffile's aszarr()+zarr windowed access (not page.asarray(), which
would decode the entire ~6GB page per slide) -- confirmed fast (~50ms/tile) and avoids
loading full pages for these very large (up to 20+GB) files.

64 tiles/slide (this project's established "more tiles helps" convention from the NADT
patch-aggregation saga), mean-pooled to one 512-dim CONCH embedding per slide -- same
recipe as NADT/PANDA/TCGA-PRAD (pilot_conch_nadt_probe.py etc.), so the existing
NADT/PANDA-trained marker probes can be applied zero-shot with no retraining.

Run with the CONCH-only venv, on a free GPU, in the background (508 large slides):
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_leopard_embed.py
"""
import os

import numpy as np
import pandas as pd
import tifffile
import torch
import zarr
from PIL import Image
from conch.open_clip_custom import create_model_from_pretrained

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
LEOPARD_DIR = os.path.join(ROOT, "resources/data/shared/opendataset/LEOPARD/training")
LABELS_CSV = os.path.join(ROOT, "resources/data/shared/opendataset/LEOPARD/training_labels.csv")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/leopard_conch_cache")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
MAIN_LEVEL = 1              # ~0.97 um/px
MASK_LEVEL = 0              # aligned with main page 2 (4x coarser than MAIN_LEVEL)
MASK_DOWNSAMPLE_FROM_MAIN = 4
TILE_SIZE = 448
TILES_PER_SLIDE = 64
TISSUE_FRACTION_MIN = 0.5   # mask mean fraction required (real tissue mask, not a heuristic)
GRID_STRIDE = 448           # non-overlapping grid
BATCH_SIZE = 16
SEED = 0


def tissue_tile_coords(mask_arr, main_h, main_w):
    """Non-overlapping grid over main-image coords, kept if the corresponding mask patch
    has enough tissue. Returns list of (y0, x0) in MAIN_LEVEL pixel coords."""
    mh, mw = mask_arr.shape
    coords = []
    for y0 in range(0, main_h - TILE_SIZE + 1, GRID_STRIDE):
        my0 = y0 // MASK_DOWNSAMPLE_FROM_MAIN
        my1 = my0 + TILE_SIZE // MASK_DOWNSAMPLE_FROM_MAIN
        if my1 > mh:
            continue
        for x0 in range(0, main_w - TILE_SIZE + 1, GRID_STRIDE):
            mx0 = x0 // MASK_DOWNSAMPLE_FROM_MAIN
            mx1 = mx0 + TILE_SIZE // MASK_DOWNSAMPLE_FROM_MAIN
            if mx1 > mw:
                continue
            frac = mask_arr[my0:my1, mx0:mx1].mean()
            if frac >= TISSUE_FRACTION_MIN:
                coords.append((y0, x0))
    return coords


def sample_tiles(case_fname, rng):
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
    mask_arr = tk.pages[MASK_LEVEL].asarray()  # small (~100-150MB), safe to load fully

    coords = tissue_tile_coords(mask_arr, main_h, main_w)
    if len(coords) == 0:
        return []
    if len(coords) > TILES_PER_SLIDE:
        idx = rng.choice(len(coords), size=TILES_PER_SLIDE, replace=False)
        coords = [coords[i] for i in idx]

    store = main_page.aszarr()
    z = zarr.open(store, mode="r")
    tiles = [z[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE] for y0, x0 in coords]
    return tiles


@torch.inference_mode()
def embed_tiles(model, preprocess, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([preprocess(Image.fromarray(np.asarray(t)).convert("RGB"))
                          for t in batch]).to(device)
        f = model.encode_image(x, proj_contrast=False, normalize=False)
        feats.append(f.cpu().numpy())
    return np.concatenate(feats, axis=0)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    labels = pd.read_csv(LABELS_CSV)
    print(f"{len(labels)} labeled cases")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    done_path = os.path.join(OUT_DIR, "meta.csv")
    done_cases = set()
    slide_vecs = []
    if os.path.exists(done_path):
        prev = pd.read_csv(done_path)
        done_cases = set(prev["case_id"])
        slide_vecs = list(np.load(os.path.join(OUT_DIR, "X.npy")))
        print(f"resuming: {len(done_cases)} slides already embedded")
    else:
        prev = pd.DataFrame(columns=["case_id", "event", "follow_up_years", "n_tiles"])

    rows = list(prev.to_dict("records"))
    for i, row in labels.iterrows():
        case_id = row["case_id"]
        if case_id in done_cases:
            continue
        tiles = sample_tiles(case_id, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {case_id}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        vec = feats.mean(axis=0)
        slide_vecs.append(vec)
        rows.append(dict(case_id=case_id, event=row["event"],
                          follow_up_years=row["follow_up_years"], n_tiles=len(tiles)))
        print(f"[{i+1}/{len(labels)}] {case_id}: {len(tiles)} tiles embedded", flush=True)

        # save after every slide -- these are long, expensive jobs (lesson from the Virchow
        # crash incident: never let a late crash lose completed GPU work)
        np.save(os.path.join(OUT_DIR, "X.npy"), np.array(slide_vecs))
        pd.DataFrame(rows).to_csv(done_path, index=False)

    print("Done.")


if __name__ == "__main__":
    main()
