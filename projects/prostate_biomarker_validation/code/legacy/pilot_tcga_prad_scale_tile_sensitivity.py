"""Tile-count / physical-scale sensitivity grid for marker 4 (H&E -> PTEN loss) on TCGA-PRAD
(Tier-2 review item 2.1: "a systematic tile-scale sensitivity study... and consider simple
scale-normalization procedures"). Bounded scope, as agreed: one marker, one cohort, a 3x3 grid
rather than a full combinatorial sweep across every marker/cohort/encoder.

Sweep: tile count in {16, 32, 64} x physical scale in {~0.44, ~0.88, ~1.76} um/px (half, native,
and double this project's standard CONCH TCGA-PRAD scale). Reuses the AppMag-derived
`pick_level` function from pilot_conch_tcga_prad_erg.py (the same TCGA-PRAD resolution-bug fix
described there).

2026-08-03 SCOPE ADJUSTMENT #1: an initial full-300-slide run was killed after the ~0.44um/px
cells proved far slower than expected (see below for why -- at that point the level-choice bug
below hadn't been diagnosed yet, so the run was ALSO not actually varying scale). To keep this
bounded per the reviewer's own framing ("a systematic... study" does not require the full
300-slide cohort to be informative), this run uses a fixed random STRATIFIED subsample of the
300-slide universe (SUBSAMPLE_N slides, stratified by PTEN status to preserve class balance),
same seed across all 9 cells so every cell sees the identical slide set and only tile-count/
scale differ.

2026-08-03 SCOPE ADJUSTMENT #2 (bug fix): the first subsampled run completed but its 9 results
showed target_mpp=0.44/0.88/1.76 giving IDENTICAL AUROC at each tile count -- a real bug, not a
null result. Diagnosis (confirmed by direct inspection of a sample slide's pyramid): TCGA-PRAD
SVS files only have TILED pyramid levels at native mpp {0.25, 1.0, 4.0, 8.0} (level 1 is a
non-tiled thumbnail, excluded). The original `pick_level` snapped every target to whichever of
{1.0, 4.0, 8.0} was numerically closest (excluding level 0 "for cost") -- and 0.44, 0.88, and
1.76 are ALL closest to 1.0um/px, so all three "different" targets silently resolved to the
exact same page. Fix: `pick_level` now also considers level 0 (0.25um/px) as a candidate, chosen
whenever it's the finest level with mpp <= target_mpp (never upsampling blurry coarse pixels to
fake a finer scale), and tiles are read via a physically-sized native window (windowed `zarr`
reads, same pattern as this project's LEOPARD/PRECISE scripts -- not a full `page.asarray()`
decode) then resized to TILE_SIZE with PIL, exactly mirroring how
pilot_precise_spatial_facevalidity.py already handles a similar native-resolution mismatch. This
also fixes the original slowness: windowed zarr reads only decode the pixels actually used,
regardless of which level is chosen, rather than decoding an entire large page per slide.

Same protocol as everywhere else in this project: patient-disjoint GroupKFold(5), StandardScaler
+ LogisticRegression(C=1.0, class_weight="balanced"), patient-level AUROC as primary metric.

Run with the CONCH-only venv on a free GPU:
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_tcga_prad_scale_tile_sensitivity.py
"""
import json
import os
import re

import numpy as np
import pandas as pd
import tifffile
import torch
import zarr
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TCGA_ROOT = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD")
SLIDE_DIR = os.path.join(TCGA_ROOT, "slides")
CACHE_META = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/meta.csv")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
OUT_CSV = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_scale_tile_sensitivity_summary.csv")

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
TILE_SIZE = 448
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 16
SEED = 0

TILE_COUNTS = [16, 32, 64]
TARGET_MPPS = [1.76, 0.44, 0.88]  # cheapest (level2, small window) first, slowest (level0, largest window) last
SUBSAMPLE_N = 90


def get_appmag(page0):
    desc = page0.tags.get("ImageDescription")
    if desc is None:
        return None
    m = re.search(r"AppMag\s*=\s*([\d.]+)", desc.value)
    return float(m.group(1)) if m else None


def pick_level_for_scale(tf, target_mpp):
    """Choose the FINEST tiled level whose native mpp is <= target_mpp (never upsample blurry
    coarse pixels to fake a finer scale); fall back to level 0 if no tiled level is fine enough.
    Returns (level_index, native_mpp_at_that_level). Unlike the old pick_level (which only
    picked the nearest of a handful of discrete pyramid levels and could make different targets
    collide -- see the 2026-08-03 bug note above), this is combined with a physically-sized
    crop window (see sample_tissue_tiles) to get genuine continuous scale control even though
    TCGA-PRAD's SVS pyramids only have 3-4 discrete tiled levels."""
    page0 = tf.pages[0]
    appmag = get_appmag(page0)
    native_mpp = 10.0 / appmag if appmag else 0.25
    w0 = page0.shape[1]

    candidates = [(0, native_mpp)]  # level 0 always usable (finest possible)
    for i, page in enumerate(tf.pages):
        if i == 0 or "TileOffsets" not in {t.name for t in page.tags}:
            continue
        downsample = w0 / page.shape[1]
        candidates.append((i, native_mpp * downsample))

    finer_or_equal = [(i, mpp) for i, mpp in candidates if mpp <= target_mpp + 1e-9]
    if finer_or_equal:
        # coarsest among those still >= target resolution -> least native pixels to read
        return max(finer_or_equal, key=lambda t: t[1])
    return min(candidates, key=lambda t: t[1])  # target finer than anything available -> level 0


def sample_tissue_tiles(path, rng, target_mpp, tiles_per_slide):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    level_idx, level_mpp = pick_level_for_scale(tf, target_mpp)
    page = tf.pages[level_idx]
    h, w = page.shape[0], page.shape[1]
    window_px = max(TILE_SIZE, round(TILE_SIZE * target_mpp / level_mpp))
    if h < window_px or w < window_px:
        return []

    store = page.aszarr()
    z = zarr.open(store, mode="r")

    tiles = []
    attempts = 0
    while len(tiles) < tiles_per_slide and attempts < MAX_GRID_ATTEMPTS:
        attempts += 1
        y0 = rng.integers(0, h - window_px)
        x0 = rng.integers(0, w - window_px)
        crop = np.asarray(z[y0:y0 + window_px, x0:x0 + window_px])
        if crop.ndim != 3:
            continue
        gray = crop[..., :3].mean(axis=2)
        tissue_frac = (gray < 205).mean()
        if tissue_frac >= TISSUE_FRACTION_MIN:
            img = Image.fromarray(crop[..., :3]).resize((TILE_SIZE, TILE_SIZE), Image.BILINEAR)
            tiles.append(np.asarray(img))
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


def load_marker_labels():
    by_attr = {}
    for d in json.load(open(CBIOPORTAL_SAMPLE_JSON)):
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
    pten_map = by_attr["PTEN_CNA"]

    slides = pd.read_csv(CACHE_META)[["file_name", "case_id"]]
    pten = slides["case_id"].map(pten_map)
    slides["pten_loss"] = pten.isin(["hetloss", "homdel"]).astype(float)
    slides.loc[pten.isna(), "pten_loss"] = np.nan
    slides["ar_score"] = slides["case_id"].map(by_attr["AR_SCORE"]).astype(float)
    slides["spop_mut"] = slides["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)
    return slides.dropna(subset=["pten_loss"]).reset_index(drop=True)


def stratified_subsample(slides_df, n, seed=SEED):
    rng = np.random.default_rng(seed)
    parts = []
    for _, group in slides_df.groupby("pten_loss"):
        frac = n / len(slides_df)
        k = max(1, round(len(group) * frac))
        idx = rng.choice(group.index.values, size=min(k, len(group)), replace=False)
        parts.append(group.loc[idx])
    return pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def embed_grid_cell(model, preprocess, device, slides_df, target_mpp, tiles_per_slide):
    rng = np.random.default_rng(SEED)
    vecs, case_ids, pten_labels, ar_labels, spop_labels = [], [], [], [], []
    for i, row in slides_df.iterrows():
        path = os.path.join(SLIDE_DIR, row["file_name"])
        if not os.path.exists(path):
            continue
        tiles = sample_tissue_tiles(path, rng, target_mpp, tiles_per_slide)
        if len(tiles) < 4:
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        vecs.append(feats.mean(axis=0))
        case_ids.append(row["case_id"])
        pten_labels.append(row["pten_loss"])
        ar_labels.append(row["ar_score"])
        spop_labels.append(row["spop_mut"])
        if len(vecs) % 20 == 0:
            print(f"    ... {len(vecs)}/{len(slides_df)} slides embedded", flush=True)
    return (np.stack(vecs), np.array(case_ids), np.array(pten_labels),
            np.array(ar_labels), np.array(spop_labels))


def eval_pten(X, groups, y):
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]
    slide_auroc = roc_auc_score(y, oof)

    df = pd.DataFrame(dict(case_id=groups, pred=oof, true=y))
    pp = df.groupby("case_id").mean()
    patient_auroc = roc_auc_score(pp["true"].round().astype(int), pp["pred"])
    return slide_auroc, patient_auroc, len(pp)


def eval_ar(X, groups, y):
    mask = ~np.isnan(y)
    X, groups, y = X[mask], groups[mask], y[mask]
    oof = np.full(len(y), np.nan)
    for train, test in GroupKFold(n_splits=5).split(X, y, groups):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[train], y[train])
        oof[test] = probe.predict(X[test])
    slide_rho = stats.spearmanr(y, oof).statistic
    slide_r2 = r2_score(y, oof)
    patient = pd.DataFrame({"case_id": groups, "pred": oof, "true": y}).groupby("case_id").mean()
    return (slide_rho, slide_r2, stats.spearmanr(patient["true"], patient["pred"]).statistic,
            r2_score(patient["true"], patient["pred"]))


def eval_spop(X, groups, y):
    mask = ~np.isnan(y)
    X, groups, y = X[mask], groups[mask], y[mask].astype(int)
    if min(y.sum(), (y == 0).sum()) < 5:
        return np.nan, np.nan
    oof = np.full(len(y), np.nan)
    for train, test in GroupKFold(n_splits=5).split(X, y, groups):
        probe = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[train], y[train])
        oof[test] = probe.predict_proba(X[test])[:, 1]
    patient = pd.DataFrame({"case_id": groups, "pred": oof, "true": y}).groupby("case_id").mean()
    return roc_auc_score(y, oof), roc_auc_score(patient["true"].round().astype(int), patient["pred"])


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    slides_df = load_marker_labels()
    print(f"{len(slides_df)} PTEN-labeled slides across {slides_df['case_id'].nunique()} patients "
          f"(full universe)")
    slides_df = stratified_subsample(slides_df, SUBSAMPLE_N)
    print(f"using stratified subsample: n={len(slides_df)}, "
          f"pten_loss={slides_df['pten_loss'].sum():.0f}/{len(slides_df)} "
          f"({100*slides_df['pten_loss'].mean():.1f}%)")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()

    rows = []
    for target_mpp in TARGET_MPPS:
        for tiles_per_slide in TILE_COUNTS:
            print(f"\n{'='*80}\nGrid cell: tiles={tiles_per_slide}, target_mpp={target_mpp}\n{'='*80}")
            X, groups, y, ar, spop = embed_grid_cell(
                model, preprocess, device, slides_df, target_mpp, tiles_per_slide)
            slide_auroc, patient_auroc, n_patients = eval_pten(X, groups, y)
            ar_slide_rho, ar_slide_r2, ar_patient_rho, ar_patient_r2 = eval_ar(X, groups, ar)
            spop_slide_auroc, spop_patient_auroc = eval_spop(X, groups, spop)
            print(f"  n_slides={len(y)}, n_patients={n_patients}, PTEN patient AUROC={patient_auroc:.3f}, "
                  f"AR patient rho={ar_patient_rho:+.3f}, SPOP patient AUROC={spop_patient_auroc:.3f}")
            rows.append(dict(tiles_per_slide=tiles_per_slide, target_mpp=target_mpp,
                              n_slides=len(y), n_patients=n_patients,
                              slide_auroc=slide_auroc, patient_auroc=patient_auroc,
                              ar_slide_rho=ar_slide_rho, ar_slide_r2=ar_slide_r2,
                              ar_patient_rho=ar_patient_rho, ar_patient_r2=ar_patient_r2,
                              spop_slide_auroc=spop_slide_auroc,
                              spop_patient_auroc=spop_patient_auroc))
            pd.DataFrame(rows).to_csv(OUT_CSV, index=False)  # save incrementally

    print(f"\n{'='*80}\nSUMMARY (patient-level AUROC, rows=tile count, cols=target_mpp)\n{'='*80}")
    summary = pd.DataFrame(rows)
    pivot = summary.pivot(index="tiles_per_slide", columns="target_mpp", values="patient_auroc")
    print(pivot)
    print(f"\nsaved {OUT_CSV}")


if __name__ == "__main__":
    main()
