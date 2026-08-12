"""Rank PRECISE tumor-adjacent regions as *PNI candidates* for pathology review.

This script does not create PNI ground truth. PRECISE has no nerve/PNI annotation. It uses
the expert tumor/stroma mask only to restrict the search, then combines three frozen-CONCH
signals:

1. zero-shot PNI-vs-no-PNI text similarity;
2. similarity to the seven visually clearest datasets-02 PNI exemplars versus the 17
   automatically sampled controls; and
3. zero-shot nerve-presence similarity.

Outputs retain slide coordinates, mask fractions, all component scores, and review crops.
Run a small smoke pilot on a free GPU, for example:

    CUDA_VISIBLE_DEVICES=1 HF_HOME=/path/to/huggingface-cache \
      resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python projects/precise_pni_candidate_triage/code/candidate_visualization/pilot_precise_pni_candidates.py \
      --limit-images 3 --max-candidates-per-image 600 --top-k-per-image 12

The output is candidate ranking only; a pathologist must assign the final PNI label.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
import torch.nn.functional as F
import zarr
from PIL import Image, ImageDraw
from conch.open_clip_custom import create_model_from_pretrained, get_tokenizer, tokenize
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[4]
PRECISE_DIR = ROOT / "resources/data/shared/opendataset/PRECISE/extracted/data"
PARTICIPANTS_CSV = ROOT / "resources/data/shared/opendataset/PRECISE/participants.csv"
PNI_CROPS_DIR = ROOT / "resources/data/shared/song-datasets/_previews/pni_crops"
DEFAULT_OUT = ROOT / "resources/data/shared/opendataset/PRECISE/pni_candidate_pilot"

MODEL_CFG = "conch_ViT-B-16"
HF_HUB_ID = "hf_hub:MahmoodLab/conch"
TILE_SIZE = 448

# pni_N follows the report's region order for each slide. These seven were described as
# visually clear/possible PNI in the report's final summary.
CLEAR_PNI_EXEMPLARS = {
    "1008803_pni_1.png",
    "1008804_pni_1.png",
    "1008804_pni_3.png",
    "1008804_pni_8.png",
    "1008806_pni_2.png",
    "1008806_pni_3.png",
    "1008806_pni_4.png",
}

TEXT_PROMPTS = {
    "pni": [
        "H&E histopathology of prostate adenocarcinoma showing perineural invasion, with cancer glands surrounding a nerve",
        "prostate cancer cells tracking within or around a peripheral nerve sheath on H&E",
        "a peripheral nerve encircled or invaded by prostate adenocarcinoma",
    ],
    "no_pni": [
        "H&E histopathology of prostate adenocarcinoma without perineural invasion",
        "prostate cancer glands in stroma with no nerve involvement",
        "ordinary prostate adenocarcinoma tissue without a visible nerve",
    ],
    "nerve": [
        "a peripheral nerve fascicle visible in prostate H&E histopathology",
        "cross section of a peripheral nerve in prostate stroma on H&E",
    ],
    "no_nerve": [
        "prostate glands and stroma without a visible nerve on H&E",
        "prostate adenocarcinoma tissue containing no peripheral nerve",
    ],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit-images", type=int, default=3,
                   help="Number of malignant PRECISE images; 0 means all malignant images")
    p.add_argument("--window-um", type=float, default=300.0)
    p.add_argument("--stride-um", type=float, default=150.0)
    p.add_argument("--max-candidates-per-image", type=int, default=600)
    p.add_argument("--top-k-per-image", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--min-tumor-fraction", type=float, default=0.02)
    p.add_argument("--min-rgb-tissue-fraction", type=float, default=0.65,
                   help="Reject mostly-white fragment-edge windows before CONCH scoring")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return p.parse_args()


def find_malignant_images(limit: int) -> list[tuple[str, Path, Path]]:
    participants = pd.read_csv(PARTICIPANTS_CSV)
    malignant = participants.loc[
        participants["SLIDE_DIAGNOSIS"].astype(str).str.lower() == "malignant"
    ].copy()
    malignant["isup_numeric"] = pd.to_numeric(
        malignant["ISUP_Grade_Group_"], errors="coerce"
    ).fillna(-1)
    # Discovery pilot: review high-grade malignant cases first, without treating grade as a
    # PNI label. Alphabetical image ID is only a deterministic tie-breaker.
    malignant = malignant.sort_values(
        ["isup_numeric", "IMAGE_NAME"], ascending=[False, True]
    )
    found = []
    for image_id in malignant["IMAGE_NAME"]:
        sub, ses = image_id.rsplit("_", 1)
        he_dir = PRECISE_DIR / sub / ses / "wsi_h-e"
        main = he_dir / f"{image_id}_h-e.ome.tif"
        mask = he_dir / f"{image_id}_h-e_mask.ome.tif"
        if main.exists() and mask.exists():
            found.append((image_id, main, mask))
    return found[:limit] if limit else found


def native_mpp(tiff: tifffile.TiffFile) -> float:
    m = re.search(r'PhysicalSizeX="([\d.]+)"', tiff.ome_metadata or "")
    return float(m.group(1)) if m else 0.243284


def enumerate_mask_candidates(mask: np.ndarray, mpp: float, window_um: float,
                              stride_um: float, maximum: int,
                              min_tumor_fraction: float) -> list[dict]:
    """Find coarse tumor-containing windows, favoring mixed tumor/stroma boundaries."""
    h, w = mask.shape[:2]
    window_px = max(1, round(window_um / mpp))
    stride_px = max(1, round(stride_um / mpp))
    sample_step = max(1, round(4.0 / mpp))  # fractions from an approximately 4-um grid
    rows = []
    for y0 in range(0, h - window_px + 1, stride_px):
        for x0 in range(0, w - window_px + 1, stride_px):
            coarse = mask[y0:y0 + window_px:sample_step,
                          x0:x0 + window_px:sample_step]
            tumor = float(np.mean(coarse == 1))
            stroma = float(np.mean(coarse == 7))
            labeled = float(np.mean(coarse != 0))
            # PRECISE annotations are sparse. Require real tumor signal but allow unlabeled
            # surroundings, where an unannotated nerve may occur.
            if tumor < min_tumor_fraction or labeled < 0.05:
                continue
            boundary_priority = 2.0 * min(tumor, max(stroma, 0.02)) + 0.35 * stroma + 0.1 * labeled
            rows.append({
                "x0": x0, "y0": y0, "window_px": window_px,
                "tumor_fraction": tumor, "stroma_fraction": stroma,
                "labeled_fraction": labeled, "mask_priority": boundary_priority,
            })
    rows.sort(key=lambda r: r["mask_priority"], reverse=True)
    return rows[:maximum]


@torch.inference_mode()
def encode_images(model, preprocess, device: str, images: list[Image.Image]) -> torch.Tensor:
    batch = torch.stack([preprocess(im.convert("RGB")) for im in images]).to(device)
    return model.encode_image(batch, proj_contrast=True, normalize=True)


@torch.inference_mode()
def prompt_centroids(model, device: str) -> dict[str, torch.Tensor]:
    tokenizer = get_tokenizer()
    result = {}
    for label, prompts in TEXT_PROMPTS.items():
        tokens = tokenize(texts=prompts, tokenizer=tokenizer).to(device)
        f = F.normalize(model.encode_text(tokens), dim=-1)
        result[label] = F.normalize(f.mean(dim=0), dim=0)
    return result


@torch.inference_mode()
def exemplar_centroids(model, preprocess, device: str) -> tuple[torch.Tensor, torch.Tensor, pd.DataFrame]:
    manifest = json.loads((PNI_CROPS_DIR / "manifest.json").read_text())
    images = [Image.open(item["path"]).convert("RGB") for item in manifest]
    f = encode_images(model, preprocess, device, images)
    clear_idx = [i for i, item in enumerate(manifest) if Path(item["path"]).name in CLEAR_PNI_EXEMPLARS]
    control_idx = [i for i, item in enumerate(manifest) if item["label"] == "control"]
    positive = F.normalize(f[clear_idx].mean(dim=0), dim=0)
    control = F.normalize(f[control_idx].mean(dim=0), dim=0)
    scores = (f @ positive - f @ control).cpu().numpy()
    validation = pd.DataFrame({
        "file": [Path(x["path"]).name for x in manifest],
        "source_label": [x["label"] for x in manifest],
        "clear_pni": [Path(x["path"]).name in CLEAR_PNI_EXEMPLARS for x in manifest],
        "prototype_score": scores,
    })
    return positive, control, validation


def rank_scores(df: pd.DataFrame) -> pd.DataFrame:
    # Percentile ranks are robust to incomparable raw score scales and domain shift.
    df = df.copy()
    for col in ["prototype_score", "text_pni_score", "nerve_score"]:
        df[f"{col}_pct"] = df[col].rank(pct=True, method="average")
    df["combined_score"] = (
        0.50 * df["prototype_score_pct"]
        + 0.35 * df["text_pni_score_pct"]
        + 0.15 * df["nerve_score_pct"]
    )
    df["global_rank"] = df["combined_score"].rank(ascending=False, method="first").astype(int)
    df["image_rank"] = df.groupby("image_id")["combined_score"].rank(
        ascending=False, method="first"
    ).astype(int)
    return df.sort_values(["global_rank"])


def extract_crop(z, row: pd.Series | dict) -> Image.Image:
    y0, x0, size = int(row["y0"]), int(row["x0"]), int(row["window_px"])
    arr = np.asarray(z[y0:y0 + size, x0:x0 + size])
    return Image.fromarray(arr).resize((TILE_SIZE, TILE_SIZE), Image.Resampling.BILINEAR)


def rgb_tissue_fraction(image: Image.Image) -> float:
    """Approximate non-white H&E coverage; used only to reject fragment-edge background."""
    a = np.asarray(image.resize((224, 224)), dtype=np.float32)
    mean = a.mean(axis=2)
    chroma = a.max(axis=2) - a.min(axis=2)
    tissue = (mean < 238.0) & ((chroma > 8.0) | (mean < 205.0))
    return float(tissue.mean())


def save_review_outputs(df: pd.DataFrame, image_paths: dict[str, Path], out_dir: Path,
                        top_k: int) -> pd.DataFrame:
    crop_dir = out_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    # Greedy spatial de-duplication: the 50%-overlap scan otherwise returns the same lesion
    # in adjacent windows. Keep centers at least 0.75 window widths apart for review.
    selected_parts = []
    for image_id, group in df.groupby("image_id", sort=True):
        kept = []
        for idx, row in group.sort_values("combined_score", ascending=False).iterrows():
            cx = float(row.x0 + row.window_px / 2)
            cy = float(row.y0 + row.window_px / 2)
            min_distance = 0.75 * float(row.window_px)
            if any((cx - kx) ** 2 + (cy - ky) ** 2 < min_distance ** 2
                   for kx, ky in kept):
                continue
            kept.append((cx, cy))
            item = row.to_frame().T
            item.index = [idx]
            item["review_rank"] = len(kept)
            selected_parts.append(item)
            if len(kept) >= top_k:
                break
    selected = pd.concat(selected_parts).sort_values(["image_id", "review_rank"])
    selected["review_rank"] = selected["review_rank"].astype(int)
    selected["crop_path"] = ""
    for image_id, group in selected.groupby("image_id", sort=True):
        with tifffile.TiffFile(image_paths[image_id]) as t:
            z = zarr.open(t.pages[0].aszarr(), mode="r")
            montage_tiles = []
            for idx, row in group.iterrows():
                crop = extract_crop(z, row)
                name = (f"{image_id}_review{int(row.review_rank):02d}_rawrank{int(row.image_rank):03d}_"
                        f"x{int(row.x0)}_y{int(row.y0)}.png")
                path = crop_dir / name
                crop.save(path)
                selected.loc[idx, "crop_path"] = str(path)
                thumb = crop.resize((280, 280))
                panel = Image.new("RGB", (280, 306), "white")
                panel.paste(thumb, (0, 26))
                ImageDraw.Draw(panel).text(
                    (4, 5), (f"review {int(row.review_rank)} raw {int(row.image_rank)}  "
                             f"score {row.combined_score:.3f}"), fill="black"
                )
                montage_tiles.append(panel)
            cols = 4
            rows = (len(montage_tiles) + cols - 1) // cols
            montage = Image.new("RGB", (cols * 280, rows * 306), "white")
            for i, panel in enumerate(montage_tiles):
                montage.paste(panel, ((i % cols) * 280, (i // cols) * 306))
            montage.save(out_dir / f"{image_id}_top{len(montage_tiles)}_montage.jpg", quality=92)
    return selected


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}", flush=True)
    model, preprocess = create_model_from_pretrained(MODEL_CFG, HF_HUB_ID)
    model = model.to(device).eval()
    prompts = prompt_centroids(model, device)
    positive_proto, control_proto, source_validation = exemplar_centroids(
        model, preprocess, device
    )
    source_validation.to_csv(args.output_dir / "source_exemplar_scores.csv", index=False)
    y_all = (source_validation["source_label"] == "pni").astype(int)
    y_clear = source_validation["clear_pni"].astype(int)
    print(f"source prototype AUC: all annotated-vs-control={roc_auc_score(y_all, source_validation.prototype_score):.3f}; "
          f"clear7-vs-rest={roc_auc_score(y_clear, source_validation.prototype_score):.3f}", flush=True)

    image_items = find_malignant_images(args.limit_images)
    print(f"scanning {len(image_items)} malignant PRECISE images", flush=True)
    rows = []
    image_paths = {}
    for image_id, main_path, mask_path in image_items:
        image_paths[image_id] = main_path
        with tifffile.TiffFile(mask_path) as mt:
            mask = mt.pages[0].asarray()
        with tifffile.TiffFile(main_path) as it:
            mpp = native_mpp(it)
            z = zarr.open(it.pages[0].aszarr(), mode="r")
            candidates = enumerate_mask_candidates(
                mask, mpp, args.window_um, args.stride_um, args.max_candidates_per_image,
                args.min_tumor_fraction,
            )
            print(f"  {image_id}: {len(candidates)} mask-filtered windows", flush=True)
            for start in range(0, len(candidates), args.batch_size):
                batch_rows = candidates[start:start + args.batch_size]
                crops = [extract_crop(z, r) for r in batch_rows]
                tissue_fractions = [rgb_tissue_fraction(crop) for crop in crops]
                keep = [i for i, frac in enumerate(tissue_fractions)
                        if frac >= args.min_rgb_tissue_fraction]
                if not keep:
                    continue
                batch_rows = [batch_rows[i] for i in keep]
                crops = [crops[i] for i in keep]
                tissue_fractions = [tissue_fractions[i] for i in keep]
                f = encode_images(model, preprocess, device, crops)
                proto = (f @ positive_proto - f @ control_proto).cpu().numpy()
                pni_text = (f @ prompts["pni"] - f @ prompts["no_pni"]).cpu().numpy()
                nerve = (f @ prompts["nerve"] - f @ prompts["no_nerve"]).cpu().numpy()
                for r, tf, ps, ts, ns in zip(
                    batch_rows, tissue_fractions, proto, pni_text, nerve
                ):
                    rows.append({
                        "image_id": image_id, "mpp": mpp, "window_um": args.window_um,
                        **r, "rgb_tissue_fraction": tf,
                        "prototype_score": float(ps), "text_pni_score": float(ts),
                        "nerve_score": float(ns),
                    })

    if not rows:
        raise RuntimeError("No candidate windows passed the PRECISE mask filter")
    ranked = rank_scores(pd.DataFrame(rows))
    ranked.to_csv(args.output_dir / "all_candidate_scores.csv", index=False)
    selected = save_review_outputs(ranked, image_paths, args.output_dir, args.top_k_per_image)
    selected.to_csv(args.output_dir / "top_candidates_for_review.csv", index=False)
    config = {
        "status": "candidate ranking only; not PNI ground truth or diagnosis",
        "model": MODEL_CFG, "checkpoint": HF_HUB_ID,
        "images": [x[0] for x in image_items],
        "window_um": args.window_um, "stride_um": args.stride_um,
        "max_candidates_per_image": args.max_candidates_per_image,
        "top_k_per_image": args.top_k_per_image,
        "min_tumor_fraction": args.min_tumor_fraction,
        "min_rgb_tissue_fraction": args.min_rgb_tissue_fraction,
        "score_weights": {"prototype": 0.50, "text_pni": 0.35, "nerve": 0.15},
        "clear_pni_exemplars": sorted(CLEAR_PNI_EXEMPLARS),
        "text_prompts": TEXT_PROMPTS,
    }
    (args.output_dir / "run_config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"saved {len(ranked)} scored windows and {len(selected)} review crops to {args.output_dir}")


if __name__ == "__main__":
    main()
