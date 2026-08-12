"""Retry of the TCGA-PRAD SPOP/PTEN markers (pilot_conch_tcga_prad_multi.py) using TUMOR-FOCUSED
tile selection instead of plain random-tile averaging.

Motivation (2026-07-28 conversation): our SPOP result (slide AUROC=0.492, patient AUROC=0.515,
clean null) contradicts a published bioRxiv preprint (Schaumberg, Rubin, Fuchs) that reports
AUROC=0.86 predicting SPOP mutation from H&E, externally validated on MSK-IMPACT. The key
methodological difference: they "carefully selected tiles containing tumor tissue and abnormal
cells" (curated ROI) and trained an end-to-end CNN ensemble; we mean-pool 16 RANDOM tissue tiles
per slide (no tumor localization) into a frozen CONCH embedding + linear probe. This is the same
"random-tile dilution in large/heterogeneous specimens" weakness already flagged for marker (1)'s
TCGA-PRAD weakening (radical-prostatectomy specimens are multifocal; random tiles risk sampling
non-tumor or lower-grade regions). This script tests whether restricting to CONCH-embedding
tiles that our own NADT-trained Phenotype probe (marker 2, slide AUROC=0.824 on NADT) scores as
high tumor-probability recovers the SPOP (and possibly PTEN) signal.

Method:
  1. Fit a tumor-probability probe (StandardScaler+LogisticRegression) on NADT's cached
     Phenotype embeddings (resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/X_phenotype.npy, 463 slides, BENIGN/TUMOR).
     This probe was fit on SLIDE-level (already tile-averaged) embeddings, but since it's linear
     in CONCH's embedding space it can still score individual tile embeddings meaningfully.
  2. Re-embed TCGA-PRAD's 266 already-used slides with 64 random tissue tiles per slide instead
     of 16 (same tiling recipe as pilot_conch_tcga_prad_erg.py: 448px tiles, ~0.88um/px target,
     tissue_frac>=0.35), keeping PER-TILE embeddings (not immediately averaged).
  3. Build three slide-level embeddings per slide for a controlled comparison:
       - rand16: mean of the first 16 of the 64 tiles (~sanity check against the original cache)
       - rand64: mean of all 64 tiles (isolates the "more coverage" effect alone)
       - tumor_top16: mean of the 16 HIGHEST tumor-probability tiles out of the 64 (the actual
         tumor-focused hypothesis test)
  4. Re-run the same patient-disjoint 5-fold GroupKFold LogisticRegression probe for SPOP_MUTATION
     and PTEN_CNA loss on all three embeddings and compare AUROC.

Run with the CONCH-only venv on a free GPU (long job -- embeds ~17k tiles):
    CUDA_VISIBLE_DEVICES=1 HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_conch_tcga_prad_tumor_focused.py
"""
import json
import os
import re

import numpy as np
import pandas as pd
import tifffile
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from conch.open_clip_custom import create_model_from_pretrained

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
NADT_CACHE = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache")
TCGA_ROOT = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD")
MANIFEST = os.path.join(TCGA_ROOT, "manifest.csv")
SLIDE_DIR = os.path.join(TCGA_ROOT, "slides")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
TARGET_MPP = 0.88
TILE_SIZE = 448
TILES_PER_SLIDE = 64          # up from 16 -- gives the tumor-filter candidates to choose from
TOP_K_TUMOR = 16              # keep the same tile budget as the original cache for fairness
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 400
BATCH_SIZE = 16
SEED = 0


def fit_tumor_probe():
    X = np.load(os.path.join(NADT_CACHE, "X_phenotype.npy"))
    meta = pd.read_csv(os.path.join(NADT_CACHE, "meta_phenotype.csv"))
    probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    probe.fit(X, meta["label"].values)
    print(f"tumor probe fit on NADT phenotype cache: n={len(meta)}, "
          f"train AUROC={roc_auc_score(meta['label'].values, probe.predict_proba(X)[:, 1]):.3f}")
    return probe


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
        if int(unit) == 3:
            return (1.0 / px_per_unit) * 1e4
        return 25400.0 / px_per_unit
    except Exception:
        return None


def pick_level(tf, target_mpp=TARGET_MPP):
    """FIXED 2026-07-28: the original fallback (page 1 when no XResolution tag parses, which is
    EVERY TCGA-PRAD slide) silently used a non-tiled ~17um/px thumbnail instead of a real
    pyramid level -- see pilot_conch_tcga_prad_erg.py's docstring for the full story. Fix:
    derive mpp from AppMag + downsample ratio to page 0, restricted to tiled pages only."""
    page0 = tf.pages[0]
    appmag = get_appmag(page0)
    native_mpp = 10.0 / appmag if appmag else 0.25
    w0 = page0.shape[1]
    best_idx, best_diff = None, float("inf")
    for i, page in enumerate(tf.pages):
        if i == 0:
            continue
        if "TileOffsets" not in {t.name for t in page.tags}:
            continue
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


def load_erg_manifest_labels():
    df = pd.read_csv(MANIFEST)
    df = df[df["erg_status"].isin(["fusion", "none"])].copy()
    return df.reset_index(drop=True)


def load_cbioportal_labels():
    data = json.load(open(CBIOPORTAL_SAMPLE_JSON))
    by_attr = {}
    for d in data:
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
    return by_attr


def test_binary_marker(X, y, groups, name):
    print(f"\n{'='*80}\n{name}\n{'='*80}")
    print(f"n={len(y)} slides (positive={y.sum()}, negative={(y==0).sum()})")
    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]

    auroc = roc_auc_score(y, oof)
    u, p = stats.mannwhitneyu(oof[y == 1], oof[y == 0], alternative="two-sided")
    print(f"slide-level (n={len(y)}): AUROC={auroc:.3f}  Mann-Whitney p={p:.4g}")

    df_eval = pd.DataFrame(dict(case_id=groups, pred=oof, true=y))
    per_patient = df_eval.groupby("case_id").mean()
    y_p = per_patient["true"].round().astype(int)
    if y_p.nunique() > 1 and y_p.sum() >= 5 and (y_p == 0).sum() >= 5:
        auroc_p = roc_auc_score(y_p, per_patient["pred"])
        print(f"patient-level (n={len(per_patient)}): AUROC={auroc_p:.3f}")
    return auroc


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}")

    tumor_probe = fit_tumor_probe()

    df = load_erg_manifest_labels()  # 300 labeled slides / 273 patients, same universe as before
    print(f"{len(df)} candidate slides across {df['case_id'].nunique()} patients")

    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    rng = np.random.default_rng(SEED)

    rand16_vecs, rand64_vecs, tumorfocus_vecs = [], [], []
    case_ids, fnames, n_tiles_used, mean_tumor_prob = [], [], [], []

    for i, row in df.iterrows():
        path = os.path.join(SLIDE_DIR, row["file_name"])
        if not os.path.exists(path):
            continue
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            continue
        feats = embed_tiles(model, preprocess, device, tiles)  # (n_tiles, 512)

        tumor_prob = tumor_probe.predict_proba(feats)[:, 1]  # per-tile tumor probability
        order = np.argsort(-tumor_prob)  # descending
        top_idx = order[:min(TOP_K_TUMOR, len(order))]

        rand16_vecs.append(feats[:min(16, len(feats))].mean(axis=0))
        rand64_vecs.append(feats.mean(axis=0))
        tumorfocus_vecs.append(feats[top_idx].mean(axis=0))

        case_ids.append(row["case_id"])
        fnames.append(row["file_name"])
        n_tiles_used.append(len(tiles))
        mean_tumor_prob.append(float(tumor_prob.mean()))

        if len(case_ids) % 20 == 0:
            print(f"  ... {len(case_ids)}/{len(df)} slides embedded "
                  f"(mean tumor-prob so far={np.mean(mean_tumor_prob):.3f})")

    X_rand16 = np.stack(rand16_vecs)
    X_rand64 = np.stack(rand64_vecs)
    X_tumorfocus = np.stack(tumorfocus_vecs)
    meta = pd.DataFrame(dict(file_name=fnames, case_id=case_ids, n_tiles=n_tiles_used,
                              mean_tumor_prob=mean_tumor_prob))

    np.save(os.path.join(OUT_DIR, "X_rand16_v2.npy"), X_rand16)
    np.save(os.path.join(OUT_DIR, "X_rand64.npy"), X_rand64)
    np.save(os.path.join(OUT_DIR, "X_tumorfocus_top16.npy"), X_tumorfocus)
    meta.to_csv(os.path.join(OUT_DIR, "meta_tumorfocus.csv"), index=False)
    print(f"\nembedded {len(case_ids)} slides, cached to {OUT_DIR}")

    # merge labels
    by_attr = load_cbioportal_labels()
    meta["pten_cna"] = meta["case_id"].map(by_attr["PTEN_CNA"])
    meta["pten_loss"] = meta["pten_cna"].isin(["hetloss", "homdel"]).astype(float)
    meta["spop_mut"] = meta["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)

    results = {}
    for label_col, label_name in [("spop_mut", "SPOP mutation"), ("pten_loss", "PTEN loss")]:
        mask = meta[label_col].notna()
        y = meta.loc[mask, label_col].astype(int).values
        groups = meta.loc[mask, "case_id"].values
        if y.sum() < 10 or (y == 0).sum() < 10:
            print(f"{label_name}: too few pos/neg, skipping")
            continue
        for tag, X in [("rand16_v2", X_rand16), ("rand64", X_rand64),
                       ("tumorfocus_top16", X_tumorfocus)]:
            auroc = test_binary_marker(X[mask.values], y, groups,
                                        f"H&E -> {label_name}  [{tag}]")
            results[(label_name, tag)] = auroc

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    for (label_name, tag), auroc in results.items():
        print(f"{label_name:15s} {tag:20s} slide AUROC={auroc:.3f}")


if __name__ == "__main__":
    main()
