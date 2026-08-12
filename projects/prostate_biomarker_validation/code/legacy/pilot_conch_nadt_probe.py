"""Re-run the project's own P1 test (structural signal vs real Gleason score on NADT-Prostate,
patient-level) using CONCH embeddings instead of our own rule-based dab_ring -- our own
algorithm was null at the patient level (all metrics p>0.28, memory: project-vlm-pathology-status).

Ground truth: Biopsy-Clinical-Data.xlsx, filtered to Stain=='H&E', Phenotype=='TUMOR', and a
parseable Gleason Score ("X+Y=Z" -> total Z) -- 334 slides across 39 patients, matching the
prior P1 test's cohort exactly.

Method:
  1. Tile each H&E WSI at pyramid level 2 (~0.88 um/px, confirmed consistent across files via
     the XResolution tag -- close to SICAPv2's ~1um/px "10X" patches, the scale CONCH was
     already validated at in pilot_conch_sicap_diagnostic.py). Randomly sample tissue-containing
     448x448 tiles (simple non-white-fraction tissue filter, no fixed sample count guarantee --
     slides with less tissue yield fewer tiles).
  2. Extract CONCH raw (proj_contrast=False) embeddings per tile, batched; mean-pool to one
     512-dim vector per slide. Saved to disk (embeddings + metadata) so this expensive step
     never needs re-running.
  3. GroupKFold (group=Patient ID) RidgeCV: this is the fix for the prior test's
     pseudo-replication mistake -- a patient's slides never split across train/test.
  4. Evaluate two ways: (a) pooled per-slide Spearman (all held-out slide predictions across
     folds vs each slide's own actual Gleason total -- respects that Gleason grade genuinely
     varies core-to-core within a patient, confirmed empirically: 35/39 patients have >1
     distinct score among their own slides), and (b) patient-level Spearman (mean predicted vs
     mean actual Gleason total per patient, n=39) for direct comparability with the prior test's
     framing.

Run with the CONCH-only venv (this is a long job -- embeds thousands of tiles -- consider
run_in_background):
    CUDA_VISIBLE_DEVICES=<free_gpu> HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_nadt_probe.py
"""
import glob
import os
import re

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

NADT_ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/NADT-Prostate_v1"
CLINICAL_XLSX = os.path.join(NADT_ROOT, "Biopsy-Clinical-Data.xlsx")
OUT_DIR = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
PYRAMID_LEVEL = 2          # ~0.88 um/px, matches SICAPv2's ~1um/px scale
TILE_SIZE = 448
TILES_PER_SLIDE = 16
TISSUE_FRACTION_MIN = 0.35  # fraction of non-white pixels required to keep a tile
MAX_GRID_ATTEMPTS = 200     # cap random tile attempts per slide (some slides are mostly background)
BATCH_SIZE = 16
SEED = 0


def load_labels():
    df = pd.read_excel(CLINICAL_XLSX)
    df = df[(df["Stain"] == "H&E") & (df["Phenotype"] == "TUMOR")].copy()
    df = df[df["Gleason Score"].notna() & (df["Gleason Score"] != "N/A (metastatic)")]

    def parse_total(s):
        m = re.match(r"\s*(\d)\s*\+\s*(\d)\s*=\s*(\d+)", str(s))
        return int(m.group(3)) if m else None

    df["gleason_total"] = df["Gleason Score"].apply(parse_total)
    df = df[df["gleason_total"].notna()]
    return df.reset_index(drop=True)


def resolve_path(fname):
    hits = glob.glob(os.path.join(NADT_ROOT, "*", fname))
    return hits[0] if hits else None


def sample_tissue_tiles(path, rng):
    tf = tifffile.TiffFile(path)
    if len(tf.pages) == 0:
        return []  # corrupted/empty TIFF (seen once in NADT: no IFDs at all)
    page = tf.pages[PYRAMID_LEVEL] if len(tf.pages) > PYRAMID_LEVEL else tf.pages[-1]
    arr = page.asarray()
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
        gray = crop.mean(axis=2)
        tissue_frac = (gray < 205).mean()
        if tissue_frac >= TISSUE_FRACTION_MIN:
            tiles.append(crop)
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
    print(f"{len(df)} valid TUMOR H&E slides across {df['Patient ID'].nunique()} patients")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    slide_vecs, patient_ids, gleason, fnames, n_tiles_used = [], [], [], [], []
    for i, row in df.iterrows():
        path = resolve_path(row["File Name"])
        if path is None:
            print(f"  [skip] file not found: {row['File Name']}")
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['File Name']}")
            continue
        feats = embed_tiles(model, preprocess, device, tiles)
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
    print(f"\nembedded {len(slide_vecs)} slides ({X.shape[1]}-dim), saved to {OUT_DIR}")

    # --- GroupKFold RidgeCV, patient-disjoint ---
    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof_pred = np.full(len(y), np.nan)
    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups)):
        probe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
        probe.fit(X[tr_idx], y[tr_idx])
        oof_pred[te_idx] = probe.predict(X[te_idx])
        print(f"fold {fold}: train={len(tr_idx)} test={len(te_idx)} "
              f"test_patients={sorted(set(groups[te_idx]))[:5]}...")

    print(f"\n{'='*80}\nPER-SLIDE (pooled out-of-fold, patient-disjoint)\n{'='*80}")
    rho, p = stats.spearmanr(oof_pred, y)
    print(f"n={len(y)} slides, Spearman(pred, true gleason_total) = {rho:+.3f}  p={p:.4g}")

    print(f"\n{'='*80}\nPATIENT-LEVEL (mean pred vs mean actual per patient)\n{'='*80}")
    df_eval = pd.DataFrame(dict(patient_id=groups, pred=oof_pred, true=y))
    per_patient = df_eval.groupby("patient_id").mean()
    rho_p, p_p = stats.spearmanr(per_patient["pred"], per_patient["true"])
    print(f"n={len(per_patient)} patients, Spearman(mean pred, mean true gleason_total) = "
          f"{rho_p:+.3f}  p={p_p:.4g}")
    per_patient.to_csv(os.path.join(OUT_DIR, "per_patient_results.csv"))


if __name__ == "__main__":
    main()
