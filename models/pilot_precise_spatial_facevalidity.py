"""PRECISE spatial face-validity check (docs/04_publication_strategy.md §7-2 step 5): do
markers 1 (H&E->Gleason) and 2 (H&E->Phenotype/tumor probability), fit zero-shot on NADT and
never trained on PRECISE, spatially make sense against PRECISE's pixel-level expert
annotations? NOT a cribriform check (PRECISE's 8 label classes have no cribriform category).

Label classes (label_descriptions.json): 0=background, 1=Tumor, 2=Benign gland, 3=Artifact,
4=HGPIN, 5=Intraductal carcinoma, 6=Atypical intraductal proliferation, 7=Stroma.

Physical scale: PRECISE H&E OME-TIFFs are single-page (baseline only, no separate pyramid
IFDs despite the OME "PyramidResolution" annotation listing theoretical levels) at
PhysicalSizeX=0.2433um/px -- much finer than this project's ~0.88um/px CONCH tiling
convention (NADT/PANDA/TCGA-PRAD/LEOPARD all target roughly this scale). To keep the physical
field of view comparable (not just resize a tiny native crop, which would change what's
actually IN the tile), each "tile" is sampled as a native ~1621x1621px window (448 *
0.88/0.243284) then resized down to 448x448 before CONCH preprocessing.

Per grid cell (window_px stride, non-overlapping): crop the matching mask window, compute the
label histogram, keep the cell only if one non-background class has >=70% majority (drops
ambiguous boundary tiles). Markers 1/2 probes are refit on the FULL NADT cohort (same recipe
as pilot_leopard_marker_scores.py) -- zero-shot, no PRECISE data used in fitting.

Also checks marker 1 against PRECISE's REAL Gleason score (participants.csv) for Tumor-labeled
tiles, averaged per image -- a genuine small-n (n<=26) external check unavailable on LEOPARD
(which has no clinical covariates in its public labels).

Run with the CONCH-only venv, on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        models/.venv-conch/bin/python models/pilot_precise_spatial_facevalidity.py
"""
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
import zarr
from PIL import Image
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

ROOT = str(Path(__file__).resolve().parents[1])
PRECISE_DIR = os.path.join(ROOT, "opendataset/PRECISE/extracted/data")
PARTICIPANTS_CSV = os.path.join(ROOT, "opendataset/PRECISE/participants.csv")
NADT_CACHE = os.path.join(ROOT, "models/nadt_conch_cache")
OUT_CSV = os.path.join(ROOT, "opendataset/PRECISE/spatial_facevalidity_results_150um.csv")

LABEL_NAMES = {0: "background", 1: "Tumor", 2: "Benign_gland", 3: "Artifact",
               4: "HGPIN", 5: "Intraductal_carcinoma", 6: "Atypical_intraductal_proliferation",
               7: "Stroma"}
# 2026-07-31 REVISION: first pass used TARGET_MPP=0.88 (this project's standard CONCH tiling
# scale) -> a ~394um window. PRECISE's expert annotations turned out to be sparse and
# small-footprint (e.g. sub-19: Tumor 0.94%, Benign gland 0.70% of all pixels) -- at 394um the
# majority-vote grid found ZERO qualifying Benign-gland windows (everything was diluted by
# surrounding stroma). Switched to a fixed 150um physical window (~617 native px at this
# dataset's 0.2433um/px, downsampled to 448x448 -- mpp_effective~=0.335um/px, finer than this
# project's usual 0.88um/px convention) specifically to fit inside PRECISE's small annotated
# regions. This is a deliberate, documented deviation from the standard scale for this one
# dataset's annotation granularity, not a new default.
WINDOW_UM = 150.0
TILE_SIZE = 448
MAJORITY_FRACTION_MIN = 0.70
MAX_TILES_PER_CLASS_PER_IMAGE = 20
BATCH_SIZE = 16


def fit_nadt_probes():
    X1 = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta1 = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    m1 = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    m1.fit(X1, meta1["gleason_total"].values)

    X2 = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
    meta2 = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
    m2 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0,
                                                             class_weight="balanced"))
    m2.fit(X2, meta2["label"].values)
    return m1, m2


def find_images():
    images = []
    for sub in sorted(os.listdir(PRECISE_DIR)):
        sub_dir = os.path.join(PRECISE_DIR, sub)
        if not os.path.isdir(sub_dir):
            continue
        for ses in sorted(os.listdir(sub_dir)):
            he_dir = os.path.join(sub_dir, ses, "wsi_h-e")
            if not os.path.isdir(he_dir):
                continue
            main = os.path.join(he_dir, f"{sub}_{ses}_h-e.ome.tif")
            mask = os.path.join(he_dir, f"{sub}_{ses}_h-e_mask.ome.tif")
            if os.path.exists(main) and os.path.exists(mask):
                images.append((f"{sub}_{ses}", main, mask))
    return images


def get_native_mpp(main_path):
    t = tifffile.TiffFile(main_path)
    m = re.search(r'PhysicalSizeX="([\d.]+)"', t.ome_metadata)
    return float(m.group(1)) if m else 0.25


def sample_labeled_tiles(main_path, mask_path, rng):
    native_mpp = get_native_mpp(main_path)
    window_px = round(WINDOW_UM / native_mpp)

    tmask = tifffile.TiffFile(mask_path)
    mask_arr = tmask.pages[0].asarray()
    h, w = mask_arr.shape

    tmain = tifffile.TiffFile(main_path)
    main_page = tmain.pages[0]

    by_class = {}
    for y0 in range(0, h - window_px + 1, window_px):
        for x0 in range(0, w - window_px + 1, window_px):
            win = mask_arr[y0:y0 + window_px, x0:x0 + window_px]
            vals, counts = np.unique(win, return_counts=True)
            total = win.size
            order = np.argsort(-counts)
            top_val, top_count = vals[order[0]], counts[order[0]]
            if top_val == 0:
                continue
            if top_count / total < MAJORITY_FRACTION_MIN:
                continue
            by_class.setdefault(int(top_val), []).append((y0, x0))

    store = main_page.aszarr()
    z = zarr.open(store, mode="r")

    results = []  # (class_id, tile_image)
    for cls, coords in by_class.items():
        if len(coords) > MAX_TILES_PER_CLASS_PER_IMAGE:
            idx = rng.choice(len(coords), size=MAX_TILES_PER_CLASS_PER_IMAGE, replace=False)
            coords = [coords[i] for i in idx]
        for y0, x0 in coords:
            crop = np.asarray(z[y0:y0 + window_px, x0:x0 + window_px])
            img = Image.fromarray(crop).resize((TILE_SIZE, TILE_SIZE), Image.BILINEAR)
            results.append((cls, img))
    return results


@torch.inference_mode()
def score_tiles(model, preprocess, device, m1, m2, images):
    rows_gleason, rows_phenotype = [], []
    for i in range(0, len(images), BATCH_SIZE):
        batch = images[i:i + BATCH_SIZE]
        x = torch.stack([preprocess(img.convert("RGB")) for img in batch]).to(device)
        f = model.encode_image(x, proj_contrast=False, normalize=False).cpu().numpy()
        rows_gleason.append(m1.predict(f))
        rows_phenotype.append(m2.predict_proba(f)[:, 1])
    return np.concatenate(rows_gleason), np.concatenate(rows_phenotype)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    m1, m2 = fit_nadt_probes()
    model, preprocess = create_model_from_pretrained("conch_ViT-B-16", "hf_hub:MahmoodLab/conch")
    model = model.to(device).eval()
    rng = np.random.default_rng(0)

    images = find_images()
    print(f"{len(images)} PRECISE H&E images found")
    participants = pd.read_csv(PARTICIPANTS_CSV).set_index("IMAGE_NAME")

    all_rows = []
    for image_id, main_path, mask_path in images:
        tiles = sample_labeled_tiles(main_path, mask_path, rng)
        if not tiles:
            print(f"  [skip] no qualifying tiles: {image_id}")
            continue
        classes = [c for c, _ in tiles]
        crops = [img for _, img in tiles]
        gleason_pred, phenotype_pred = score_tiles(model, preprocess, device, m1, m2, crops)
        for cls, g, p in zip(classes, gleason_pred, phenotype_pred):
            all_rows.append(dict(image_id=image_id, label_class=cls,
                                  label_name=LABEL_NAMES.get(cls, str(cls)),
                                  marker1_gleason=g, marker2_phenotype=p))
        print(f"  {image_id}: {len(tiles)} tiles across classes "
              f"{sorted(set(LABEL_NAMES.get(c,c) for c in classes))}", flush=True)

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {len(df)} tile-level scores to {OUT_CSV}")

    print(f"\n{'='*80}\nmarker2 (tumor probability) by mask class\n{'='*80}")
    print(df.groupby("label_name")["marker2_phenotype"].agg(["count", "mean", "median", "std"]))

    print(f"\n{'='*80}\nmarker1 (predicted Gleason) by mask class\n{'='*80}")
    print(df.groupby("label_name")["marker1_gleason"].agg(["count", "mean", "median", "std"]))

    # bonus: marker1 vs REAL Gleason score, per-image mean over Tumor-labeled tiles
    print(f"\n{'='*80}\nmarker1 vs REAL Gleason score (Tumor-labeled tiles only, per image)\n{'='*80}")
    tumor_df = df[df["label_class"] == 1]
    per_image = tumor_df.groupby("image_id")["marker1_gleason"].mean()
    rows = []
    for image_id, pred in per_image.items():
        if image_id not in participants.index:
            continue
        real = participants.loc[image_id, "Gleason_score"]
        m = re.match(r"(\d)\+(\d)=(\d+)", str(real))
        if not m:
            continue
        rows.append(dict(image_id=image_id, marker1_pred=pred, real_gleason=int(m.group(3))))
    comp = pd.DataFrame(rows)
    print(comp)
    if len(comp) >= 4:
        from scipy import stats
        rho, p = stats.spearmanr(comp["marker1_pred"], comp["real_gleason"])
        print(f"\nSpearman rho={rho:+.3f}  p={p:.4g}  (n={len(comp)} images)")


if __name__ == "__main__":
    main()
