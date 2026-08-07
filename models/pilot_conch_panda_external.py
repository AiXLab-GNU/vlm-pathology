"""External-institution validation of marker (1) (H&E -> Gleason severity, CONCH raw
embedding + RidgeCV probe) on PANDA (Kaggle prostate-cancer-grade-assessment).

Context: marker (1) was validated on NADT-Prostate (single institution, 334 H&E slides /
39 patients, patient-disjoint 5-fold GroupKFold): slide rho=+0.312 (p=5.8e-9), patient
rho=+0.478 (p=0.0021) -- see models/pilot_conch_nadt_probe.py and memory
project-vlm-pathology-status. PANDA is a completely different cohort: two institutions
(Karolinska, Radboud), different scanners, different staining/prep protocols, official
ISUP grade group (0-5) labels instead of NADT's raw Gleason-total (6-10) -- a genuine
external-institution test, not another split of the same data.

Two tests, reusing the same CONCH embeddings (embedding is the expensive step):
  (a) Zero-shot transfer: refit the marker-(1) probe on ALL 334 cached NADT slides (no
      NADT held-out needed -- PANDA itself is now the held-out set), predict on PANDA
      tiles with ZERO PANDA-specific training, Spearman vs isup_grade. This is the
      strictest test of "does the NADT-trained marker generalize to another institution".
  (b) PANDA-native cross-institution refit: train a fresh probe on Karolinska slides,
      test on Radboud, and vice versa. Weaker/different question ("is there Gleason
      signal in PANDA that a CONCH probe can find general enough to cross scanners"),
      but useful supporting evidence and doesn't depend on how well NADT's specific
      scale/coefficients transfer.

Tiling: unlike NADT (single scanner, fixed pyramid level 2 confirmed uniform ~0.88 um/px),
PANDA has two scanners with different native resolutions (Karolinska ~0.5 um/px at level 0,
Radboud ~0.24 um/px at level 0, both usually 4x-downsampled per pyramid level) -- a fixed
page index would give physically different tile sizes per institution, confounding
"external validation" with a scale mismatch. Instead we read each page's XResolution/
ResolutionUnit tags and pick whichever pyramid level's implied microns-per-pixel is
closest to the ~0.88 um/px NADT was tiled at.

Run with the CONCH-only venv (long job -- embeds thousands of tiles):
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        models/.venv-conch/bin/python models/pilot_conch_panda_external.py
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

ROOT = str(Path(__file__).resolve().parents[1])
PANDA_ROOT = os.path.join(ROOT, "opendataset/PANDA_extracted")
TRAIN_CSV = os.path.join(PANDA_ROOT, "train.csv")
IMG_DIR = os.path.join(PANDA_ROOT, "train_images")
NADT_CACHE = os.path.join(ROOT, "models/nadt_conch_cache")
OUT_DIR = os.path.join(ROOT, "models/panda_conch_cache")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
TARGET_MPP = 0.88          # match NADT's tiling scale
TILE_SIZE = 448
TILES_PER_SLIDE = 16       # match NADT's marker-(1) probe exactly (fair zero-shot test)
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 16
SEED = 0
CELLS_CAP = 100            # max slides per (provider, isup_grade) stratum


def load_labels():
    df = pd.read_csv(TRAIN_CSV)
    return df


def stratified_subsample(df, cap, seed):
    rng = np.random.default_rng(seed)
    parts = []
    for (_, _), g in df.groupby(["data_provider", "isup_grade"]):
        if len(g) > cap:
            idx = rng.choice(g.index.values, size=cap, replace=False)
            parts.append(df.loc[idx])
        else:
            parts.append(g)
    out = pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return out


def get_mpp(page):
    try:
        xres = page.tags["XResolution"].value
        num, den = xres
        if num == 0:
            return None
        px_per_unit = num / den
        resunit_tag = page.tags.get("ResolutionUnit")
        unit = resunit_tag.value if resunit_tag is not None else 2
        if int(unit) == 3:  # centimeter
            mpp = (1.0 / px_per_unit) * 1e4
        else:  # inch (default)
            mpp = 25400.0 / px_per_unit
        return mpp
    except Exception:
        return None


def pick_level(tf, target_mpp=TARGET_MPP):
    # Exclude page 0 (full-resolution "level 0", ~0.45-0.49 um/px on PANDA's scanners):
    # a plain nearest-mpp search over ALL pages picks it because it happens to be closer in
    # linear um/px terms than level 1 (~1.8-1.95 um/px) to our 0.88 um/px target -- but reading
    # level 0's full-size array (e.g. 29440x27648) per slide is what NADT's fixed-level-2
    # approach was specifically designed to avoid, and was never the intended scale (docstring:
    # matching SICAPv2's ~1um/px "10X" patches, not full/"40X" resolution). Restrict the search
    # to downsampled levels only, matching the original intent.
    candidates = list(enumerate(tf.pages))[1:] if len(tf.pages) > 1 else list(enumerate(tf.pages))
    best_idx, best_diff, any_mpp = candidates[0][0], float("inf"), False
    for i, page in candidates:
        mpp = get_mpp(page)
        if mpp is None:
            continue
        any_mpp = True
        diff = abs(mpp - target_mpp)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    if not any_mpp:
        best_idx = min(1, len(tf.pages) - 1)  # fallback: middle-ish level
    return best_idx


def sample_tissue_tiles(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    level = pick_level(tf)
    page = tf.pages[level]
    arr = page.asarray()
    if arr.ndim == 2:  # unlikely, but guard against grayscale pages
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
def embed_tiles(model, preprocess, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([preprocess(Image.fromarray(t).convert("RGB")) for t in batch]).to(device)
        f = model.encode_image(x, proj_contrast=False, normalize=False)
        feats.append(f.cpu().numpy())
    return np.concatenate(feats, axis=0)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    df = load_labels()
    print(f"PANDA train.csv: {len(df)} slides, providers={df['data_provider'].unique().tolist()}, "
          f"isup_grade counts=\n{df['isup_grade'].value_counts().sort_index()}")

    sub = stratified_subsample(df, CELLS_CAP, SEED)
    print(f"stratified subsample: {len(sub)} slides "
          f"(cap={CELLS_CAP}/provider x isup_grade cell)")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    slide_vecs, image_ids, providers, isup, gleason_str, n_tiles_used, levels_used = \
        [], [], [], [], [], [], []
    for i, row in sub.iterrows():
        path = os.path.join(IMG_DIR, row["image_id"] + ".tiff")
        if not os.path.exists(path):
            print(f"  [skip] file not found: {path}")
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['image_id']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        slide_vecs.append(feats.mean(axis=0))
        image_ids.append(row["image_id"])
        providers.append(row["data_provider"])
        isup.append(row["isup_grade"])
        gleason_str.append(row["gleason_score"])
        n_tiles_used.append(len(tiles))
        if len(slide_vecs) % 50 == 0:
            print(f"  ... {len(slide_vecs)}/{len(sub)} slides embedded")

    X_panda = np.stack(slide_vecs)
    isup = np.array(isup)
    providers = np.array(providers)
    np.save(os.path.join(OUT_DIR, "X_panda.npy"), X_panda)
    meta = pd.DataFrame(dict(image_id=image_ids, data_provider=providers, isup_grade=isup,
                              gleason_score=gleason_str, n_tiles=n_tiles_used))
    meta.to_csv(os.path.join(OUT_DIR, "meta_panda.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} PANDA slides ({X_panda.shape[1]}-dim), saved to {OUT_DIR}")

    # --- (a) zero-shot transfer: NADT-fitted probe, no PANDA training ---
    X_nadt = np.load(os.path.join(NADT_CACHE, "X.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_CACHE, "meta.csv"))
    y_nadt = meta_nadt["gleason_total"].values
    nadt_probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    nadt_probe.fit(X_nadt, y_nadt)
    pred_zeroshot = nadt_probe.predict(X_panda)

    print(f"\n{'='*80}\n(a) ZERO-SHOT TRANSFER: NADT-fitted probe -> PANDA, no PANDA training\n{'='*80}")
    rho, p = stats.spearmanr(pred_zeroshot, isup)
    print(f"ALL (n={len(isup)}): Spearman(NADT-probe pred, PANDA isup_grade) = {rho:+.3f}  p={p:.4g}")
    for prov in np.unique(providers):
        mask = providers == prov
        rho_p, p_p = stats.spearmanr(pred_zeroshot[mask], isup[mask])
        print(f"  {prov} (n={mask.sum()}): rho={rho_p:+.3f}  p={p_p:.4g}")

    # --- (b) PANDA-native cross-institution refit ---
    print(f"\n{'='*80}\n(b) PANDA-NATIVE CROSS-INSTITUTION: train one provider, test the other\n{'='*80}")
    for train_prov in np.unique(providers):
        test_prov = [p for p in np.unique(providers) if p != train_prov][0]
        tr_mask = providers == train_prov
        te_mask = providers == test_prov
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X_panda[tr_mask], isup[tr_mask])
        pred = probe.predict(X_panda[te_mask])
        rho_ci, p_ci = stats.spearmanr(pred, isup[te_mask])
        print(f"train={train_prov} (n={tr_mask.sum()}) -> test={test_prov} (n={te_mask.sum()}): "
              f"rho={rho_ci:+.3f}  p={p_ci:.4g}")

    results = pd.DataFrame(dict(image_id=image_ids, data_provider=providers, isup_grade=isup,
                                 pred_zeroshot_nadt=pred_zeroshot))
    results.to_csv(os.path.join(OUT_DIR, "panda_results.csv"), index=False)


if __name__ == "__main__":
    main()
