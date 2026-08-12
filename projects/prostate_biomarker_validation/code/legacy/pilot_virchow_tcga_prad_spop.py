"""Independent-model re-test of the TCGA-PRAD SPOP mutation marker using Virchow (Paige AI)
instead of CONCH (Mahmood Lab), to check whether our SPOP null (pilot_conch_tcga_prad_multi.py:
slide AUROC=0.492, clean null) is a CONCH-specific limitation or a genuine absence of signal.

Motivation (2026-07-28 conversation): a bioRxiv preprint (Schaumberg, Rubin, Fuchs) reports
AUROC=0.86 for H&E->SPOP mutation using curated tumor tiles + an end-to-end CNN. We already
tested and rejected the "random-tile dilution" hypothesis (pilot_conch_tcga_prad_tumor_focused.py)
-- tumor-focused tile selection didn't help. The remaining open question is whether a frozen
CONCH embedding structurally lacks the capacity to represent SPOP-specific texture. Virchow is a
good independent check: trained by a different company (Paige) on a much larger, entirely
different slide corpus (1.5M+ slides) than CONCH (Mahmood Lab), so a convergent result (also
null) would be strong evidence the signal genuinely isn't recoverable this way, while a divergent
result (Virchow finds signal) would point at CONCH's embedding space specifically.

Embedding recipe follows Virchow's own model card usage (paige-ai/Virchow on HuggingFace):
  - 224x224 tiles (ViT-H/14, patch14, native training resolution), unlike CONCH's 448x448.
  - Target ~0.5um/px (~20x), Virchow's documented training magnification (vs CONCH's 0.88um/px).
  - Per-tile embedding = concat(CLS token, mean of 256 patch tokens) = 2560-dim (not just CLS).
  - mlp_layer=SwiGLUPacked, act_layer=SiLU required to load correctly (default timm config
    mismatches shapes otherwise -- discovered 2026-07-28).
Same 16-random-tissue-tiles-per-slide recipe as the ORIGINAL (non-tumor-focused) CONCH SPOP test,
for a direct apples-to-apples comparison against that specific number (slide AUROC=0.492).

Run with the CONCH venv (already has timm/torch; no new venv needed) on a free GPU:
    CUDA_VISIBLE_DEVICES=1 HF_HOME=~/.cache/huggingface-jhkim \
        resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_virchow_tcga_prad_spop.py
"""
import json
import os
import re

import numpy as np
import pandas as pd
import tifffile
import timm
import torch
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from timm.layers import SwiGLUPacked

ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
TCGA_ROOT = os.path.join(ROOT, "resources/data/shared/opendataset/TCGA-PRAD")
MANIFEST = os.path.join(TCGA_ROOT, "manifest.csv")
SLIDE_DIR = os.path.join(TCGA_ROOT, "slides")
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/virchow_tcga_prad_cache")
CBIOPORTAL_SAMPLE_JSON = os.path.join(
    ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json")
os.makedirs(OUT_DIR, exist_ok=True)

TARGET_MPP = 0.5           # Virchow's native training magnification (~20x)
TILE_SIZE = 224            # Virchow's native patch14 input resolution
TILES_PER_SLIDE = 16       # match the ORIGINAL (non-tumor-focused) CONCH SPOP test exactly
TISSUE_FRACTION_MIN = 0.35
MAX_GRID_ATTEMPTS = 200
BATCH_SIZE = 32
SEED = 0


def load_labels():
    df = pd.read_csv(MANIFEST)
    df = df[df["erg_status"].isin(["fusion", "none"])].copy()  # same 300-slide universe as before
    by_attr = {}
    for d in json.load(open(CBIOPORTAL_SAMPLE_JSON)):
        by_attr.setdefault(d["clinicalAttributeId"], {})[d["patientId"]] = d["value"]
    df["spop_mut"] = df["case_id"].map(by_attr["SPOP_MUTATION"]).astype(float)
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
def embed_tiles(model, transform, device, tiles):
    feats = []
    for i in range(0, len(tiles), BATCH_SIZE):
        batch = tiles[i:i + BATCH_SIZE]
        x = torch.stack([transform(Image.fromarray(t).convert("RGB")) for t in batch]).to(device)
        out = model.forward_features(x)          # (B, 257, 1280)
        cls_token = out[:, 0]                     # (B, 1280)
        patch_mean = out[:, 1:].mean(dim=1)        # (B, 1280)
        emb = torch.cat([cls_token, patch_mean], dim=-1)  # (B, 2560)
        feats.append(emb.cpu().numpy())
    return np.concatenate(feats, axis=0)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}")

    df = load_labels()
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
        tiles = sample_tissue_tiles(path, rng)
        if len(tiles) < 4:
            print(f"  [skip] too few tissue tiles ({len(tiles)}): {row['file_name']}")
            continue
        feats = embed_tiles(model, transform, device, tiles)  # (n_tiles, 2560)
        slide_vecs.append(feats.mean(axis=0))
        case_ids.append(row["case_id"])
        fnames.append(row["file_name"])
        n_tiles_used.append(len(tiles))
        if len(slide_vecs) % 20 == 0:
            print(f"  ... {len(slide_vecs)}/{len(df)} slides embedded")

    X = np.stack(slide_vecs)
    meta = pd.DataFrame(dict(file_name=fnames, case_id=case_ids, n_tiles=n_tiles_used))
    np.save(os.path.join(OUT_DIR, "X_spop.npy"), X)
    meta.to_csv(os.path.join(OUT_DIR, "meta_spop.csv"), index=False)
    print(f"\nembedded {len(slide_vecs)} slides ({X.shape[1]}-dim Virchow), cached to {OUT_DIR} "
          f"(saved BEFORE label merge so a labeling bug can't lose the GPU work again)")

    meta["spop_mut"] = meta["case_id"].map(dict(zip(df["case_id"], df["spop_mut"])))
    meta.to_csv(os.path.join(OUT_DIR, "meta_spop.csv"), index=False)

    mask = meta["spop_mut"].notna()
    y = meta.loc[mask, "spop_mut"].astype(int).values
    Xb = X[mask.values]
    groups = meta.loc[mask, "case_id"].values
    print(f"\nn={len(y)} slides (positive={y.sum()}, negative={(y==0).sum()})")

    n_splits = 5
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(Xb, y, groups):
        probe = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"))
        probe.fit(Xb[tr], y[tr])
        oof[te] = probe.predict_proba(Xb[te])[:, 1]

    auroc = roc_auc_score(y, oof)
    u, p = stats.mannwhitneyu(oof[y == 1], oof[y == 0], alternative="two-sided")
    print(f"\n{'='*80}\nRESULT: Virchow H&E -> SPOP mutation\n{'='*80}")
    print(f"slide-level (n={len(y)}): AUROC={auroc:.3f}  Mann-Whitney p={p:.4g}")

    df_eval = pd.DataFrame(dict(case_id=groups, pred=oof, true=y))
    per_patient = df_eval.groupby("case_id").mean()
    y_p = per_patient["true"].round().astype(int)
    if y_p.nunique() > 1 and y_p.sum() >= 5 and (y_p == 0).sum() >= 5:
        auroc_p = roc_auc_score(y_p, per_patient["pred"])
        print(f"patient-level (n={len(per_patient)}): AUROC={auroc_p:.3f}")
    per_patient.to_csv(os.path.join(OUT_DIR, "per_patient_spop_results.csv"))

    print(f"\nFor comparison, CONCH's result on the identical 16-random-tile recipe: "
          f"slide AUROC=0.492 (p=0.88, clean null)")


if __name__ == "__main__":
    main()
