"""Run coordinate-audited TCGA-PRAD stability cells for PTEN, SPOP, and AR.

One maximum-size tile set is sampled per encoder/seed/scale and tile-count cells use fixed
prefixes. Patient folds come only from stability_fold_assignments.csv. Outputs are incremental
CSV files so interrupted GPU runs can be resumed at the configuration level.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
import zarr
from PIL import Image
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[4]
SLIDES = ROOT / "resources/data/shared/opendataset/TCGA-PRAD/slides"
META = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_conch_cache/meta.csv"
CLINICAL = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pub_sample_clinical.json"
FOLDS = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv"


def stable_rng(seed: int, file_name: str) -> np.random.Generator:
    token = hashlib.sha256(f"{seed}:{file_name}".encode()).digest()[:8]
    return np.random.default_rng(int.from_bytes(token, "little"))


def labels() -> pd.DataFrame:
    frame = pd.read_csv(META)[["file_name", "case_id"]]
    by = {}
    for row in json.load(CLINICAL.open()):
        by.setdefault(row["clinicalAttributeId"], {})[row["patientId"]] = row["value"]
    frame["gleason_sum"] = frame.case_id.map(by["REVIEWED_GLEASON_SUM"]).astype(float)
    pten = frame.case_id.map(by["PTEN_CNA"])
    frame["pten"] = pten.isin(["hetloss", "homdel"]).astype(float)
    frame.loc[pten.isna(), "pten"] = np.nan
    frame["spop"] = frame.case_id.map(by["SPOP_MUTATION"]).astype(float)
    frame["ar"] = frame.case_id.map(by["AR_SCORE"]).astype(float)
    return frame


def native_mpp(page) -> float:
    xres = page.tags.get("XResolution")
    unit = page.tags.get("ResolutionUnit")
    if xres and unit:
        numerator, denominator = xres.value
        pixels_per_unit = numerator / denominator
        if pixels_per_unit > 0:
            # TIFF ResolutionUnit 3 is centimeter, 2 is inch.
            return (10000.0 if int(unit.value) == 3 else 25400.0) / pixels_per_unit
    tag = page.tags.get("ImageDescription")
    match = re.search(r"AppMag\s*=\s*([\d.]+)", tag.value if tag else "")
    return 10.0 / float(match.group(1)) if match else 0.25


def pick_level(tf, target_mpp: float):
    native = native_mpp(tf.pages[0])
    width0 = tf.pages[0].shape[1]
    candidates = [(0, native)]
    for idx, page in enumerate(tf.pages):
        if idx and "TileOffsets" in {tag.name for tag in page.tags}:
            candidates.append((idx, native * width0 / page.shape[1]))
    finer = [item for item in candidates if item[1] <= target_mpp + 1e-9]
    return max(finer, key=lambda item: item[1]) if finer else min(candidates, key=lambda item: item[1])


def sample(path: Path, seed: int, target_mpp: float, output_size: int, max_tiles: int):
    rng = stable_rng(seed, path.name)
    with tifffile.TiffFile(path) as tf:
        level, level_mpp = pick_level(tf, target_mpp)
        page = tf.pages[level]
        height, width = page.shape[:2]
        window = max(output_size, round(output_size * target_mpp / level_mpp))
        if height <= window or width <= window:
            return [], []
        store = page.aszarr()
        array = zarr.open(store, mode="r")
        tiles, coords = [], []
        attempts = 0
        while len(tiles) < max_tiles and attempts < max(500, max_tiles * 20):
            attempts += 1
            y = int(rng.integers(0, height - window))
            x = int(rng.integers(0, width - window))
            crop = np.asarray(array[y:y + window, x:x + window])
            if crop.ndim != 3:
                continue
            tissue = float((crop[..., :3].mean(axis=2) < 205).mean())
            if tissue < 0.35:
                continue
            resized = Image.fromarray(crop[..., :3]).resize((output_size, output_size), Image.BILINEAR)
            tiles.append(np.asarray(resized))
            coords.append((level, level_mpp, x, y, window, tissue, len(tiles) - 1))
        try:
            store.close()
        except AttributeError:
            pass
    return tiles, coords


def load_encoder(name: str, device: str):
    if name == "CONCH":
        from conch.open_clip_custom import create_model_from_pretrained
        model, transform = create_model_from_pretrained("conch_ViT-B-16", "hf_hub:MahmoodLab/conch")
        return model.to(device).eval(), transform, 448
    import timm
    from timm.layers import SwiGLUPacked
    model = timm.create_model("hf-hub:paige-ai/Virchow", pretrained=True,
                              mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU).to(device).eval()
    cfg = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
    return model, timm.data.create_transform(**cfg), 224


@torch.inference_mode()
def embed(model, transform, encoder: str, device: str, tiles, batch_size: int):
    result = []
    for start in range(0, len(tiles), batch_size):
        tensor = torch.stack([transform(Image.fromarray(x).convert("RGB"))
                              for x in tiles[start:start + batch_size]]).to(device)
        if encoder == "CONCH":
            value = model.encode_image(tensor, proj_contrast=False, normalize=False)
        else:
            tokens = model.forward_features(tensor)
            value = torch.cat([tokens[:, 0], tokens[:, 1:].mean(dim=1)], dim=-1)
        result.append(value.cpu().numpy())
    return np.concatenate(result)


def fixed_fold_oof(X, y, cases, fold_map, binary):
    folds = np.asarray([fold_map[c] for c in cases])
    pred = np.full(len(y), np.nan)
    for fold in range(5):
        train, test = folds != fold, folds == fold
        if binary:
            model = make_pipeline(StandardScaler(), LogisticRegression(
                max_iter=2000, C=1.0, class_weight="balanced"))
            model.fit(X[train], y[train].astype(int))
            pred[test] = model.predict_proba(X[test])[:, 1]
        else:
            model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25)))
            model.fit(X[train], y[train])
            pred[test] = model.predict(X[test])
    return pred, folds


def metric(y, pred, binary):
    return roc_auc_score(y.astype(int), pred) if binary else stats.spearmanr(y, pred).statistic


def evaluate(marker, X, meta, tile_count, encoder, seed, target_mpp):
    binary = marker in {"pten", "spop"}
    mask = meta[marker].notna().to_numpy()
    Xm, ym = X[mask], meta.loc[mask, marker].to_numpy(float)
    cases = meta.loc[mask, "case_id"].to_numpy()
    fold_df = pd.read_csv(FOLDS)
    fold_map = dict(zip(fold_df.loc[fold_df.marker == marker, "case_id"],
                        fold_df.loc[fold_df.marker == marker, "fold"]))
    pred, folds = fixed_fold_oof(Xm, ym, cases, fold_map, binary)
    slide_value = metric(ym, pred, binary)
    patient = pd.DataFrame({"case_id": cases, "target": ym, "pred": pred, "fold": folds}).groupby(
        "case_id", as_index=False).agg(target=("target", "mean"), pred=("pred", "mean"), fold=("fold", "first"))
    patient_value = metric(patient.target.to_numpy(), patient.pred.to_numpy(), binary)
    cell = {"cell_id": f"{marker}__{encoder.lower()}__s{seed}__t{tile_count}__mpp{target_mpp:.2f}",
            "marker": marker, "encoder": encoder, "sampling_seed": seed,
            "tiles_per_slide": tile_count, "target_mpp": target_mpp,
            "n_slides": len(ym), "n_patients": len(patient), "slide_metric": slide_value,
            "patient_metric": patient_value, "status": "complete"}
    fold_rows = []
    for fold, part in patient.groupby("fold"):
        try:
            value = metric(part.target.to_numpy(), part.pred.to_numpy(), binary)
        except ValueError:
            value = np.nan
        fold_rows.append({**{k: cell[k] for k in ["cell_id", "marker", "encoder", "sampling_seed",
                                                   "tiles_per_slide", "target_mpp"]},
                          "fold": fold, "n_patients": len(part), "patient_metric": value})
    return cell, fold_rows


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoder", choices=["CONCH", "Virchow"], required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--mpps", nargs="+", type=float, required=True)
    parser.add_argument("--tile-counts", nargs="+", type=int, default=[16, 32, 64])
    parser.add_argument("--max-slides", type=int)
    parser.add_argument("--output-tag", default="full")
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, transform, output_size = load_encoder(args.encoder, device)
    frame = labels()
    if args.max_slides and args.max_slides < len(frame):
        # Joint-label stratification avoids a smoke subset in which PTEN and rare SPOP labels
        # accidentally become exact complements. Guarantee at least five slides per observed
        # joint stratum, then fill proportionally from the remaining rows.
        frame = frame.copy()
        frame["_stratum"] = frame.pten.astype(int).astype(str) + "_" + frame.spop.astype(int).astype(str)
        base = frame.groupby("_stratum", group_keys=False).sample(
            n=min(5, frame.groupby("_stratum").size().min()), random_state=0)
        remaining = frame.drop(base.index)
        fill_n = args.max_slides - len(base)
        fill = remaining.sample(n=fill_n, random_state=1) if fill_n > 0 else remaining.iloc[:0]
        frame = pd.concat([base, fill]).sample(frac=1, random_state=2).drop(columns="_stratum").reset_index(drop=True)
    out = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs" / args.output_tag / args.encoder.lower()
    out.mkdir(parents=True, exist_ok=True)
    max_tiles = max(args.tile_counts)
    cell_path, fold_path = out / "cell_results.csv", out / "fold_results.csv"
    all_cells = pd.read_csv(cell_path).to_dict("records") if cell_path.exists() else []
    all_folds = pd.read_csv(fold_path).to_dict("records") if fold_path.exists() else []
    for seed in args.seeds:
        for mpp in args.mpps:
            expected = {f"{marker}__{args.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}"
                        for count in args.tile_counts for marker in ["pten", "spop", "ar"]}
            complete = {str(row["cell_id"]) for row in all_cells if row.get("status") == "complete"}
            cache_files = [out / f"coordinates_s{seed}_mpp{mpp:.2f}.csv",
                           out / f"tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",
                           out / f"meta_s{seed}_mpp{mpp:.2f}.csv"]
            if expected <= complete and all(path.exists() for path in cache_files):
                print(f"[resume] skip completed {args.encoder} seed={seed} mpp={mpp}", flush=True)
                continue
            all_cells = [row for row in all_cells if str(row.get("cell_id")) not in expected]
            all_folds = [row for row in all_folds if str(row.get("cell_id")) not in expected]
            vectors, kept, coord_rows = [], [], []
            for _, row in frame.iterrows():
                tiles, coords = sample(SLIDES / row.file_name, seed, mpp, output_size, max_tiles)
                if len(tiles) < max_tiles:
                    continue
                features = embed(model, transform, args.encoder, device, tiles, args.batch_size)
                vectors.append(features)
                kept.append(row)
                for level, level_mpp, x, y, window, tissue, rank in coords:
                    coord_rows.append({"file_name": row.file_name, "case_id": row.case_id,
                                       "encoder": args.encoder, "sampling_seed": seed,
                                       "target_mpp": mpp, "pyramid_level": level,
                                       "level_mpp": level_mpp, "x": x, "y": y,
                                       "crop_size_native_px": window, "tissue_fraction": tissue,
                                       "tile_rank": rank})
                if len(vectors) % 20 == 0:
                    print(f"{args.encoder} seed={seed} mpp={mpp}: {len(vectors)}/{len(frame)} slides", flush=True)
            meta = pd.DataFrame(kept).reset_index(drop=True)
            array = np.stack(vectors)
            pd.DataFrame(coord_rows).to_csv(out / f"coordinates_s{seed}_mpp{mpp:.2f}.csv", index=False)
            np.save(out / f"tile_embeddings_s{seed}_mpp{mpp:.2f}.npy", array)
            meta.to_csv(out / f"meta_s{seed}_mpp{mpp:.2f}.csv", index=False)
            for count in args.tile_counts:
                pooled = np.stack([value[:count].mean(axis=0) for value in array])
                for marker in ["pten", "spop", "ar"]:
                    try:
                        cell, folds = evaluate(marker, pooled, meta, count, args.encoder, seed, mpp)
                        all_cells.append(cell); all_folds.extend(folds)
                    except Exception as exc:
                        all_cells.append({"cell_id": f"{marker}__{args.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}",
                                          "marker": marker, "encoder": args.encoder,
                                          "sampling_seed": seed, "tiles_per_slide": count,
                                          "target_mpp": mpp, "status": f"failed:{type(exc).__name__}:{exc}"})
            pd.DataFrame(all_cells).to_csv(cell_path, index=False)
            pd.DataFrame(all_folds).to_csv(fold_path, index=False)
    print(pd.DataFrame(all_cells).to_string(index=False))


if __name__ == "__main__":
    main()
