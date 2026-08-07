"""Coordinate-audited LEOPARD-to-TCGA marker-7 stability cells."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored

from run_stability_tcga import ROOT, SLIDES, embed, load_encoder, sample

LEOPARD = ROOT / "opendataset/LEOPARD/training"
BCR = ROOT / "opendataset/TCGA-PRAD-BCR/bcr.csv"
FOLDS = ROOT / "models/stability_fold_assignments.csv"


def structured(event, time):
    return np.array(list(zip(event.astype(bool), time)), dtype=[("event", bool), ("time", float)])


def frames(encoder):
    source = pd.read_csv(ROOT / f"models/leopard_{encoder.lower()}_cache/meta.csv")
    source["file_name"] = source.case_id
    source["path"] = source.file_name.map(lambda x: str(LEOPARD / x))
    target = pd.read_csv(ROOT / "models/tcga_prad_conch_cache/meta.csv")[["file_name", "case_id"]]
    target["path"] = target.file_name.map(lambda x: str(SLIDES / x))
    target = target.merge(pd.read_csv(BCR), on="case_id", how="inner")
    return source, target


def embed_frame(frame, cohort, model, transform, encoder, device, output_size, seed, mpp,
                max_tiles, batch_size):
    vectors, kept, coordinates = [], [], []
    for _, row in frame.iterrows():
        tiles, coords = sample(Path(row.path), seed, mpp, output_size, max_tiles)
        if len(tiles) < max_tiles: continue
        vectors.append(embed(model, transform, encoder, device, tiles, batch_size)); kept.append(row)
        for level, level_mpp, x, y, window, tissue, rank in coords:
            coordinates.append({"cohort": cohort, "file_name": row.file_name,
                "case_id": row.case_id, "encoder": encoder, "sampling_seed": seed,
                "target_mpp": mpp, "pyramid_level": level, "level_mpp": level_mpp,
                "x": x, "y": y, "crop_size_native_px": window,
                "tissue_fraction": tissue, "tile_rank": rank})
        if len(vectors) % 20 == 0:
            print(f"marker7 {encoder} {cohort} s={seed} mpp={mpp}: {len(vectors)}/{len(frame)}", flush=True)
    return np.stack(vectors), pd.DataFrame(kept).reset_index(drop=True), pd.DataFrame(coordinates)


def evaluate(Xs, source, Xt, target, count, encoder, seed, mpp):
    source_pool = np.stack([x[:count].mean(0) for x in Xs])
    target_pool = np.stack([x[:count].mean(0) for x in Xt])
    # Multiple TCGA slides are pooled to patients before zero-shot application.
    target_features = pd.DataFrame(target_pool)
    target_features["case_id"] = target.case_id.values
    patient_X = target_features.groupby("case_id").mean()
    patient = target.drop_duplicates("case_id").set_index("case_id").loc[patient_X.index]
    scaler = StandardScaler().fit(source_pool)
    pca = PCA(n_components=8, random_state=0).fit(scaler.transform(source_pool))
    model = CoxPHSurvivalAnalysis(alpha=1.0).fit(
        pca.transform(scaler.transform(source_pool)),
        structured(source.event.to_numpy(), source.follow_up_years.to_numpy()))
    risk = model.predict(pca.transform(scaler.transform(patient_X.to_numpy())))
    event, time = patient.event.to_numpy(), patient.follow_up_y.to_numpy()
    value = concordance_index_censored(event.astype(bool), time, risk)[0]
    cell_id = f"marker7__{encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}"
    cell = {"cell_id": cell_id, "marker": "marker7", "encoder": encoder,
            "sampling_seed": seed, "tiles_per_slide": count, "target_mpp": mpp,
            "n_source_patients": len(source), "n_patients": len(patient),
            "n_events": int(event.sum()), "patient_metric": value, "status": "complete"}
    fold_map_df = pd.read_csv(FOLDS); fold_map_df = fold_map_df[fold_map_df.marker == "marker7"]
    fold_map = dict(zip(fold_map_df.case_id, fold_map_df.fold))
    rows = []
    for fold in range(5):
        mask = np.asarray([fold_map[c] == fold for c in patient.index])
        try: fold_value = concordance_index_censored(event[mask].astype(bool), time[mask], risk[mask])[0]
        except (ValueError, ZeroDivisionError): fold_value = np.nan
        rows.append({"cell_id": cell_id, "marker": "marker7", "encoder": encoder,
                     "sampling_seed": seed, "tiles_per_slide": count, "target_mpp": mpp,
                     "fold": fold, "n_patients": int(mask.sum()), "patient_metric": fold_value})
    return cell, rows


def args():
    p=argparse.ArgumentParser(); p.add_argument("--encoder",choices=["CONCH","Virchow"],required=True)
    p.add_argument("--seeds",nargs="+",type=int,required=True); p.add_argument("--mpps",nargs="+",type=float,required=True)
    p.add_argument("--tile-counts",nargs="+",type=int,default=[16,32,64]); p.add_argument("--max-source",type=int)
    p.add_argument("--max-target",type=int); p.add_argument("--output-tag",default="full"); p.add_argument("--batch-size",type=int,default=16)
    return p.parse_args()


def main():
    a=args(); model,transform,size=load_encoder(a.encoder,"cuda"); source,target=frames(a.encoder)
    if a.max_source: source=source.groupby("event",group_keys=False).sample(n=min(a.max_source//2,source.groupby("event").size().min()),random_state=0).reset_index(drop=True)
    if a.max_target: target=target.groupby("event",group_keys=False).sample(n=min(a.max_target//2,target.groupby("event").size().min()),random_state=0).reset_index(drop=True)
    out=ROOT/"models/stability_runs"/a.output_tag/f"marker7_{a.encoder.lower()}"; out.mkdir(parents=True,exist_ok=True)
    cell_path, fold_path = out/"cell_results.csv", out/"fold_results.csv"
    cells=pd.read_csv(cell_path).to_dict("records") if cell_path.exists() else []
    folds=pd.read_csv(fold_path).to_dict("records") if fold_path.exists() else []
    for seed in a.seeds:
      for mpp in a.mpps:
        expected={f"marker7__{a.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}" for count in a.tile_counts}
        complete={str(row["cell_id"]) for row in cells if row.get("status")=="complete"}
        cache_files=[out/f"coordinates_s{seed}_mpp{mpp:.2f}.csv",
                     out/f"source_tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",
                     out/f"target_tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",
                     out/f"source_meta_s{seed}_mpp{mpp:.2f}.csv",
                     out/f"target_meta_s{seed}_mpp{mpp:.2f}.csv"]
        if expected <= complete and all(path.exists() for path in cache_files):
          print(f"[resume] skip completed marker7 {a.encoder} seed={seed} mpp={mpp}",flush=True); continue
        cells=[row for row in cells if str(row.get("cell_id")) not in expected]
        folds=[row for row in folds if str(row.get("cell_id")) not in expected]
        Xs,ms,cs=embed_frame(source,"LEOPARD",model,transform,a.encoder,"cuda",size,seed,mpp,max(a.tile_counts),a.batch_size)
        Xt,mt,ct=embed_frame(target,"TCGA-PRAD",model,transform,a.encoder,"cuda",size,seed,mpp,max(a.tile_counts),a.batch_size)
        pd.concat([cs,ct]).to_csv(out/f"coordinates_s{seed}_mpp{mpp:.2f}.csv",index=False)
        np.save(out/f"source_tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",Xs); np.save(out/f"target_tile_embeddings_s{seed}_mpp{mpp:.2f}.npy",Xt)
        ms.to_csv(out/f"source_meta_s{seed}_mpp{mpp:.2f}.csv",index=False); mt.to_csv(out/f"target_meta_s{seed}_mpp{mpp:.2f}.csv",index=False)
        for count in a.tile_counts:
          try:
            cell,rows=evaluate(Xs,ms,Xt,mt,count,a.encoder,seed,mpp); cells.append(cell); folds.extend(rows)
          except Exception as exc:
            cells.append({"cell_id":f"marker7__{a.encoder.lower()}__s{seed}__t{count}__mpp{mpp:.2f}","marker":"marker7","encoder":a.encoder,"sampling_seed":seed,"tiles_per_slide":count,"target_mpp":mpp,"status":f"failed:{type(exc).__name__}:{exc}"})
        pd.DataFrame(cells).to_csv(cell_path,index=False); pd.DataFrame(folds).to_csv(fold_path,index=False)


if __name__=="__main__": main()
