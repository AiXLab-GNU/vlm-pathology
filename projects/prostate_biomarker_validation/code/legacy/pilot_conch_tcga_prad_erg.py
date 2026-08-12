"""Adjacent experiment to marker (3) (NADT ERG-stain -> Gleason score). NOT a test of that
result's open question (whether residual hematoxylin counterstain architecture in ERG-stained
images explains why they predict Gleason grade) -- "H&E -> fusion status" (this experiment)
and "ERG image's residual H&E-like architecture -> grade" (the NADT open question) are
logically distinct claims; a result on one does not confirm or deny the other. An earlier
version of this docstring conflated the two -- see memory project-vlm-pathology-status for the
correction. What this experiment actually asks, standalone: does plain H&E (no ERG stain at
all) carry any CONCH-visible signature of TMPRSS2-ERG fusion status (real molecular ground
truth, from TCGA-PRAD's published Cell 2015 molecular subtyping, NOT our own proxy)?

Result (2026-07-27): weak/null. Slide-level (n=266) AUROC=0.574 (Mann-Whitney p=0.038),
patient-level (n=239, the more rigorous unit) AUROC=0.552, p=0.17 -- NOT significant. Much
weaker than the Phenotype marker (AUROC 0.824). Conclusion: TMPRSS2-ERG fusion status has
little to no detectable plain-H&E morphological signature in this cohort. The NADT ERG open
question remains genuinely unresolved.

NOT a replication of marker (3) itself (input is H&E, not ERG-stained tissue) -- see the
2026-07-27 conversation for why no public dataset with real Gleason-labeled ERG-STAINED WSIs
was found.

Ground truth: resources/data/shared/opendataset/TCGA-PRAD/manifest.csv (erg_status column: 'fusion'/'none', from
cBioPortal prad_tcga_pub ERG_STATUS, 300 labeled slides / 273 patients). Requires slides
downloaded first via resources/data/shared/opendataset/TCGA-PRAD/download_tcga_prad.py.

Method: same tiling/embedding/probe recipe as marker (1) (pilot_conch_nadt_probe.py) and
marker (3) (pilot_conch_nadt_erg_probe.py) for direct comparability, swapping RidgeCV
regression for LogisticRegression (binary target) and Spearman for AUROC -- same recipe used
for NADT Phenotype (marker 2), which was also a binary classification target.

Run with the CONCH-only venv (long job -- embeds thousands of tiles):
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_tcga_prad_erg.py
"""
import glob
import os
import re

import numpy as np
import pandas as pd
import tifffile
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
TCGA_ROOT = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD")
MANIFEST = os.path.join(TCGA_ROOT, "manifest.csv")
SLIDE_DIR = os.path.join(TCGA_ROOT, "slides")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
TARGET_MPP = 0.88          # match NADT/PANDA tiling scale
TILE_SIZE = 448
TILES_PER_SLIDE = 16
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 16
SEED = 0


def load_labels():
    df = pd.read_csv(MANIFEST)
    df = df[df["erg_status"].isin(["fusion", "none"])].copy()
    df["y"] = (df["erg_status"] == "fusion").astype(int)
    return df.reset_index(drop=True)


def get_appmag(page0):
    """TCGA-PRAD's Aperio SVS files carry no XResolution tag (confirmed 2026-07-28 across a
    random sample) -- fall back to the ImageDescription's AppMag field (Aperio convention:
    40x ~= 0.25um/px, 20x ~= 0.5um/px, i.e. native_mpp = 10/AppMag)."""
    desc = page0.tags.get("ImageDescription")
    if desc is None:
        return None
    m = re.search(r"AppMag\s*=\s*([\d.]+)", desc.value)
    return float(m.group(1)) if m else None


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
            return (1.0 / px_per_unit) * 1e4
        return 25400.0 / px_per_unit  # inch (default)
    except Exception:
        return None


def pick_level(tf, target_mpp=TARGET_MPP):
    """FIXED 2026-07-28: the original version fell back to `min(1, n_pages-1)` (page 1) whenever
    no page had a parseable XResolution tag -- which is EVERY TCGA-PRAD slide. Page 1 is not a
    real pyramid level: it's a separate, strip-encoded (non-tiled) ~17um/px thumbnail image
    (confirmed via its tags lacking TileOffsets), ~20x coarser than the 0.88um/px this pipeline
    was meant to sample at. This silently degraded every TCGA-PRAD H&E embedding run to date
    (marker 1 external validation, PTEN/SPOP/TP53/RB1/AR-score probes, ERG fusion status, and the
    tumor-focused SPOP retry) to near-macro-scale color-blob tiles instead of gland-level detail.
    Fix: derive mpp from AppMag + downsample ratio to page 0 for tiled (TileOffsets-bearing)
    pages only, explicitly excluding both page 0 (full-res, too large/slow) and any non-tiled
    thumbnail/label/macro page."""
    page0 = tf.pages[0]
    appmag = get_appmag(page0)
    native_mpp = 10.0 / appmag if appmag else 0.25  # 0.25 = standard Aperio 40x fallback
    w0 = page0.shape[1]
    best_idx, best_diff = None, float("inf")
    for i, page in enumerate(tf.pages):
        if i == 0:
            continue
        if "TileOffsets" not in {t.name for t in page.tags}:
            continue  # non-tiled thumbnail/label/macro image, not a real pyramid level
        downsample = w0 / page.shape[1]
        mpp = native_mpp * downsample
        diff = abs(mpp - target_mpp)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    if best_idx is None:
        best_idx = min(2, len(tf.pages) - 1)
    return best_idx


def sample_tissue_tiles(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []
    page = tf.pages[pick_level(tf)]
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
    print(f"{len(df)} labeled slides across {df['case_id'].nunique()} patients "
          f"(fusion={df['y'].sum()}, none={(df['y']==0).sum()})")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    slide_vecs, case_ids, labels, fnames, n_tiles_used = [], [], [], [], []
    for i, row in df.iterrows():
        path = os.path.join(SLIDE_DIR, row["file_name"])
        if not os.path.exists(path):
            print(f"  [skip] file not found (not downloaded yet?): {row['file_name']}")
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['file_name']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
        slide_vecs.append(feats.mean(axis=0))
        case_ids.append(row["case_id"])
        labels.append(row["y"])
        fnames.append(row["file_name"])
        n_tiles_used.append(len(tiles))
        if len(slide_vecs) % 20 == 0:
            print(f"  ... {len(slide_vecs)}/{len(df)} slides embedded")

    X = np.stack(slide_vecs)
    y = np.array(labels)
    groups = np.array(case_ids)
    np.save(os.path.join(OUT_DIR, "X.npy"), X)
    meta = pd.DataFrame(dict(file_name=fnames, case_id=case_ids, erg_fusion=labels,
                              n_tiles=n_tiles_used))
    meta.to_csv(os.path.join(OUT_DIR, "meta.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} slides ({X.shape[1]}-dim), saved to {OUT_DIR}")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof_pred = np.full(len(y), np.nan)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups)):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegressionCV(Cs=np.logspace(-3, 3, 13), max_iter=2000,
                                                     cv=3, scoring="roc_auc"))
        probe.fit(X[tr_idx], y[tr_idx])
        oof_pred[te_idx] = probe.predict_proba(X[te_idx])[:, 1]
        print(f"fold {fold}: train={len(tr_idx)} test={len(te_idx)} "
              f"test_patients={sorted(set(groups[te_idx]))[:5]}...")

    print(f"\n{'='*80}\nPER-SLIDE (pooled out-of-fold, patient-disjoint)\n{'='*80}")
    auroc = roc_auc_score(y, oof_pred)
    print(f"n={len(y)} slides, AUROC(H&E CONCH probe, ERG fusion status) = {auroc:.3f}")

    print(f"\n{'='*80}\nPATIENT-LEVEL (mean pred prob vs actual label per patient)\n{'='*80}")
    df_eval = pd.DataFrame(dict(case_id=groups, pred=oof_pred, true=y))
    per_patient = df_eval.groupby("case_id").mean()
    auroc_p = roc_auc_score(per_patient["true"].round().astype(int), per_patient["pred"])
    print(f"n={len(per_patient)} patients, AUROC(mean pred, true) = {auroc_p:.3f}")
    per_patient.to_csv(os.path.join(OUT_DIR, "per_patient_results.csv"))


if __name__ == "__main__":
    main()
