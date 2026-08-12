"""Coordinate-audited NADT stability cells for Gleason and phenotype."""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from run_stability_tcga import ROOT, embed, load_encoder, sample

NADT = ROOT / "resources/data/shared/opendataset/NADT-Prostate_v1"
FOLDS = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv"


def load_frame():
    grade = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta.csv").rename(
        columns={"gleason_total": "gleason"})[["file_name", "patient_id", "gleason"]]
    phenotype = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/nadt_conch_cache/meta_phenotype.csv").rename(
        columns={"label": "phenotype"})[["file_name", "patient_id", "phenotype"]]
    frame = phenotype.merge(grade[["file_name", "gleason"]], on="file_name", how="left")
    paths = {Path(p).name: p for p in glob.glob(str(NADT / "*" / "*.tiff"))}
    frame["path"] = frame.file_name.map(paths)
    if frame.path.isna().any():
        raise FileNotFoundError(f"missing {frame.path.isna().sum()} NADT slides")
    return frame


def oof(X, y, cases, marker, binary):
    fold_df = pd.read_csv(FOLDS)
    mapping = dict(zip(fold_df.loc[fold_df.marker == marker, "case_id"].astype(str),
                       fold_df.loc[fold_df.marker == marker, "fold"]))
    folds = np.asarray([mapping[str(case)] for case in cases])
    pred = np.full(len(y), np.nan)
    for fold in range(5):
        train, test = folds != fold, folds == fold
        model = (make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=2000, C=1.0, class_weight="balanced")) if binary else
                 make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 6, 25))))
        model.fit(X[train], y[train].astype(int) if binary else y[train])
        pred[test] = model.predict_proba(X[test])[:, 1] if binary else model.predict(X[test])
    return pred, folds


def evaluate(marker, X, meta, count, encoder, seed, mpp):
    binary = marker == "phenotype"
    mask = meta[marker].notna().to_numpy()
    y = meta.loc[mask, marker].to_numpy(float)
    cases = meta.loc[mask, "patient_id"].astype(str).to_numpy()
    pred, folds = oof(X[mask], y, cases, marker, binary)
    calc = (lambda a, b: roc_auc_score(a.astype(int), b)) if binary else (
        lambda a, b: stats.spearmanr(a, b).statistic)
    patient = pd.DataFrame({"case": cases, "target": y, "pred": pred, "fold": folds}).groupby(
        "case", as_index=False).agg(target=("target", "mean"), pred=("pred", "mean"), fold=("fold", "first"))
    cell_id = f"{marker}__{encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}"
    cell = {"cell_id": cell_id, "marker": marker, "encoder": encoder,
            "sampling_seed": seed, "tiles_per_slide": count, "target_mpp": mpp,
            "n_slides": len(y), "n_patients": len(patient), "slide_metric": calc(y, pred),
            "patient_metric": calc(patient.target.to_numpy(), patient.pred.to_numpy()), "status": "complete"}
    rows = []
    for fold, part in patient.groupby("fold"):
        try: value = calc(part.target.to_numpy(), part.pred.to_numpy())
        except ValueError: value = np.nan
        rows.append({"cell_id": cell_id, "marker": marker, "encoder": encoder,
                     "sampling_seed": seed, "tiles_per_slide": count, "target_mpp": mpp,
                     "fold": fold, "n_patients": len(part), "patient_metric": value})
    return cell, rows


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--encoder", choices=["CONCH", "Virchow"], required=True)
    p.add_argument("--seeds", nargs="+", type=int, required=True)
    p.add_argument("--mpps", nargs="+", type=float, required=True)
    p.add_argument("--tile-counts", nargs="+", type=int, default=[16, 32, 64])
    p.add_argument("--max-slides", type=int)
    p.add_argument("--output-tag", default="full")
    p.add_argument("--batch-size", type=int, default=16)
    return p.parse_args()


def main():
    a = args(); device = "cuda"
    model, transform, output_size = load_encoder(a.encoder, device)
    frame = load_frame()
    if a.max_slides:
        frame = frame.groupby("phenotype", group_keys=False).sample(
            n=min(a.max_slides // 2, frame.groupby("phenotype").size().min()), random_state=0).reset_index(drop=True)
    out = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs" / a.output_tag / f"nadt_{a.encoder.lower()}"
    out.mkdir(parents=True, exist_ok=True)
    cell_path, fold_path = out / "cell_results.csv", out / "fold_results.csv"
    cells = pd.read_csv(cell_path).to_dict("records") if cell_path.exists() else []
    fold_rows = pd.read_csv(fold_path).to_dict("records") if fold_path.exists() else []
    for seed in a.seeds:
        for mpp in a.mpps:
            expected = {f"{marker}__{a.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}"
                        for count in a.tile_counts for marker in ["gleason", "phenotype"]}
            complete = {str(row["cell_id"]) for row in cells if row.get("status") == "complete"}
            cache_files = [out / f"coordinates_s{seed}_mpp{mpp:.2f}.csv",
                           out / f"tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",
                           out / f"meta_s{seed}_mpp{mpp:.2f}.csv"]
            if expected <= complete and all(path.exists() for path in cache_files):
                print(f"[resume] skip completed NADT {a.encoder} seed={seed} mpp={mpp}", flush=True)
                continue
            cells = [row for row in cells if str(row.get("cell_id")) not in expected]
            fold_rows = [row for row in fold_rows if str(row.get("cell_id")) not in expected]
            vectors, kept, coordinates = [], [], []
            for _, row in frame.iterrows():
                tiles, coords = sample(Path(row.path), seed, mpp, output_size, max(a.tile_counts))
                if len(tiles) < max(a.tile_counts): continue
                vectors.append(embed(model, transform, a.encoder, device, tiles, a.batch_size)); kept.append(row)
                for level, level_mpp, x, y, window, tissue, rank in coords:
                    coordinates.append({"file_name": row.file_name, "case_id": row.patient_id,
                        "encoder": a.encoder, "sampling_seed": seed, "target_mpp": mpp,
                        "pyramid_level": level, "level_mpp": level_mpp, "x": x, "y": y,
                        "crop_size_native_px": window, "tissue_fraction": tissue, "tile_rank": rank})
                if len(vectors) % 20 == 0: print(f"NADT {a.encoder} s={seed} mpp={mpp}: {len(vectors)}/{len(frame)}", flush=True)
            array, meta = np.stack(vectors), pd.DataFrame(kept).reset_index(drop=True)
            pd.DataFrame(coordinates).to_csv(out / f"coordinates_s{seed}_mpp{mpp:.2f}.csv", index=False)
            np.save(out / f"tile_embeddings_s{seed}_mpp{mpp:.2f}.npy", array)
            meta.to_csv(out / f"meta_s{seed}_mpp{mpp:.2f}.csv", index=False)
            for count in a.tile_counts:
                pooled = np.stack([v[:count].mean(0) for v in array])
                for marker in ["gleason", "phenotype"]:
                    try:
                        cell, folds = evaluate(marker, pooled, meta, count, a.encoder, seed, mpp)
                        cells.append(cell); fold_rows.extend(folds)
                    except Exception as exc:
                        cells.append({"cell_id": f"{marker}__{a.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}",
                                      "marker": marker, "encoder": a.encoder, "sampling_seed": seed,
                                      "tiles_per_slide": count, "target_mpp": mpp,
                                      "status": f"failed:{type(exc).__name__}:{exc}"})
            pd.DataFrame(cells).to_csv(cell_path, index=False)
            pd.DataFrame(fold_rows).to_csv(fold_path, index=False)


if __name__ == "__main__": main()
