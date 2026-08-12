"""Systematic cross-model extension (2026-07-28): markers (1) and (2) external validation on
PANDA with Virchow instead of CONCH, on the same stratified subsample recipe as
pilot_conch_panda_external.py / pilot_conch_panda_phenotype_external.py. Completes the
CONCH+Virchow cross-model discipline (already applied to markers 3 and 5) across the whole
marker pool.

Tiling: PANDA has two scanners with different native resolutions (Karolinska ~0.5um/px at level
0, Radboud ~0.24um/px at level 0), so pick_level dynamically reads each page's XResolution tag
(these ARE present and reliable on PANDA, unlike TCGA-PRAD) and picks the closest tiled level to
Virchow's ~0.5um/px target, explicitly excluding page 0 (full-res, too large/slow) -- same
discipline as the original CONCH PANDA script's fix.

Run with the CONCH venv (long job -- embeds thousands of tiles) on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_panda_external.py
"""
import os

import numpy as np
import pandas as pd
import tifffile
import timm
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from timm.layers import SwiGLUPacked

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
PANDA_ROOT = os.path.join(ROOT, "resources/data/shared/opendataset/PANDA_extracted")
TRAIN_CSV = os.path.join(PANDA_ROOT, "train.csv")
IMG_DIR = os.path.join(PANDA_ROOT, "train_images")
NADT_VIRCHOW_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_nadt_cache")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_panda_cache")
os.makedirs(OUT_DIR, exist_ok=True)

TARGET_MPP = 0.5
TILE_SIZE = 224
TILES_PER_SLIDE = 16
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 32
SEED = 0
CELLS_CAP = 100


def load_labels():
    return pd.read_csv(TRAIN_CSV)


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
        if int(unit) == 3:
            return (1.0 / px_per_unit) * 1e4
        return 25400.0 / px_per_unit
    except Exception:
        return None


def pick_level(tf, target_mpp=TARGET_MPP):
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
        best_idx = min(1, len(tf.pages) - 1)
    return best_idx


def sample_tissue_tiles(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    level = pick_level(tf)
    page = tf.pages[level]
    arr = page.asarray()
    if arr.ndim == 2:
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
    df = load_labels()
    sub = stratified_subsample(df, CELLS_CAP, SEED)
    print(f"stratified subsample: {len(sub)} slides (cap={CELLS_CAP}/provider x isup_grade cell)")

    model = timm.create_model("hf-hub:paige-ai/Virchow", pretrained=True,
                               mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU)
    model = model.to(device).eval()
    cfg = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
    transform = timm.data.create_transform(**cfg)
    rng = np.random.default_rng(SEED)

    slide_vecs, image_ids, providers, isup, gleason_str, n_tiles_used = \
        [], [], [], [], [], []
    for i, row in sub.iterrows():
        path = os.path.join(IMG_DIR, row["image_id"] + ".tiff")
        if not os.path.exists(path):
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            continue
        feats = embed_tiles(model, transform, device, tiles)
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
    print(f"\nembedded {len(slide_vecs)} PANDA slides ({X_panda.shape[1]}-dim Virchow), "
          f"saved to {OUT_DIR}")

    # marker (1): zero-shot transfer using Virchow-fitted NADT probe
    X_nadt = np.load(os.path.join(NADT_VIRCHOW_CACHE, "X.npy"))
    meta_nadt = pd.read_csv(os.path.join(NADT_VIRCHOW_CACHE, "meta.csv"))
    nadt_probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
    nadt_probe.fit(X_nadt, meta_nadt["gleason_total"].values)
    pred_zeroshot = nadt_probe.predict(X_panda)
    print(f"\n{'='*80}\nMARKER (1) ZERO-SHOT TRANSFER (Virchow, NADT-fitted probe -> PANDA)\n{'='*80}")
    rho, p = stats.spearmanr(pred_zeroshot, isup)
    print(f"ALL (n={len(isup)}): rho={rho:+.3f}  p={p:.4g}")
    for prov in np.unique(providers):
        mask = providers == prov
        rho_p, p_p = stats.spearmanr(pred_zeroshot[mask], isup[mask])
        print(f"  {prov} (n={mask.sum()}): rho={rho_p:+.3f}  p={p_p:.4g}")

    # marker (2): phenotype zero-shot transfer using Virchow-fitted NADT phenotype probe
    X_nadt_ph = np.load(os.path.join(NADT_VIRCHOW_CACHE, "X_phenotype.npy"))
    meta_nadt_ph = pd.read_csv(os.path.join(NADT_VIRCHOW_CACHE, "meta_phenotype.csv"))
    ph_probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    ph_probe.fit(X_nadt_ph, meta_nadt_ph["label"].values)
    pred_ph = ph_probe.predict_proba(X_panda)[:, 1]
    y_tumor = (isup >= 1).astype(int)
    print(f"\n{'='*80}\nMARKER (2) ZERO-SHOT TRANSFER (Virchow, NADT phenotype probe -> PANDA)\n{'='*80}")
    auroc = roc_auc_score(y_tumor, pred_ph)
    print(f"ALL (n={len(y_tumor)}): AUROC={auroc:.3f}")
    for prov in np.unique(providers):
        mask = providers == prov
        auroc_p = roc_auc_score(y_tumor[mask], pred_ph[mask])
        print(f"  {prov} (n={mask.sum()}): AUROC={auroc_p:.3f}")

    results = pd.DataFrame(dict(image_id=image_ids, data_provider=providers, isup_grade=isup,
                                 pred_zeroshot_gleason=pred_zeroshot, pred_zeroshot_phenotype=pred_ph))
    results.to_csv(os.path.join(OUT_DIR, "panda_results.csv"), index=False)
    print(f"\nFor comparison, CONCH marker(1): rho=+0.398 all, +0.354 kar, +0.519 rad")
    print(f"For comparison, CONCH marker(2): AUROC=0.823 all, 0.786 kar, 0.871 rad")


if __name__ == "__main__":
    main()
