#!/usr/bin/env python3
"""Prepare and extract QFM-owned PANDA grading embeddings.

Tile coordinates are selected from slide RGB tissue only. Outcome labels and annotation
masks are attached after coordinate selection and therefore cannot influence sampling.
Radboud masks provide GP3/GP4/GP5 truth; Karolinska masks provide cancer-only truth.
All large generated products remain under resources/artifacts.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from PIL import Image
from sklearn.metrics import cohen_kappa_score, roc_auc_score
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm8_grading_criterion_qualification"
OUTPUTS = MILESTONE / "outputs"
ARTIFACTS = (
    ROOT
    / "resources/artifacts/quantitative_foundation_model_validation"
    / "fm8_grading_criterion_qualification"
)
PANDA_ROOT = ROOT / "resources/data/shared/opendataset/PANDA_extracted"
PANDA_LABELS = PANDA_ROOT / "train.csv"
PANDA_IMAGES = PANDA_ROOT / "train_images"
PANDA_MASKS = PANDA_ROOT / "train_label_masks"
SICAP_ROOT = ROOT / "resources/data/shared/opendataset/SICAPv2/SICAPv2"
PAR_ROOT = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/par_s_biad2323"
PAR_LABELS = PAR_ROOT / "slide_labels.tsv"
PAR_WSI = PAR_ROOT / "hamamatsu"
PAR_LOCAL_AUDIT = PAR_ROOT / "hamamatsu_local_audit.json"
FM6_RUNNER_PATH = (
    PROJECT
    / "milestones/fm6_internal_development_pilot/run_fm6_tcga_internal_pilot.py"
)

SEED = 260901
FOV_UM = 394.24
MAX_TILES = 64
MIN_TILES = 16
DIMENSION = {"conch": 512, "virchow": 2560}
BATCH_SIZE = {"conch": 64, "virchow": 64}
EXPECTED_SLIDES = 10616
HEAD_HIDDEN = 256
HEAD_BATCH_SIZE = 16
HEAD_LEARNING_RATE = 1e-4
HEAD_WEIGHT_DECAY = 1e-4
HEAD_MAX_EPOCHS = 30
BOOTSTRAPS = 2000
HEAD_ARCHITECTURES = ("gated_mil", "mean_linear")


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FM6_RUNNER = load_module("fm8_grading_fm6_embedding_runtime", FM6_RUNNER_PATH)
FM6_RUNNER.SEED = SEED
FM6_RUNNER.FOV_UM = FOV_UM
FM6_RUNNER.MAX_TILES = MAX_TILES
FM6_RUNNER.MIN_TILES = MIN_TILES


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_npz(path: Path, **arrays: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def panda_labels() -> pd.DataFrame:
    frame = pd.read_csv(PANDA_LABELS, dtype={"image_id": str, "gleason_score": str})
    required = {"image_id", "data_provider", "isup_grade", "gleason_score"}
    if len(frame) != EXPECTED_SLIDES or not required.issubset(frame.columns):
        raise RuntimeError("PANDA label universe changed")
    if frame.image_id.duplicated().any() or frame[list(required)].isna().any().any():
        raise RuntimeError("PANDA label identity/integrity failure")
    providers = set(frame.data_provider.astype(str))
    if providers != {"karolinska", "radboud"}:
        raise RuntimeError(f"unexpected PANDA providers: {sorted(providers)}")
    return frame.sort_values("image_id").reset_index(drop=True)


def parse_gleason(value: str) -> tuple[int, int]:
    normalized = str(value).strip().lower()
    if normalized == "negative":
        return 0, 0
    pieces = normalized.split("+")
    if len(pieces) != 2 or any(not piece.isdigit() for piece in pieces):
        raise ValueError(f"invalid Gleason score: {value}")
    return int(pieces[0]), int(pieces[1])


def isup_from_patterns(primary: int, secondary: int) -> int:
    mapping = {
        (0, 0): 0,
        (3, 3): 1,
        (3, 4): 2,
        (4, 3): 3,
        (4, 4): 4,
        (3, 5): 4,
        (5, 3): 4,
        (4, 5): 5,
        (5, 4): 5,
        (5, 5): 5,
    }
    try:
        return mapping[(int(primary), int(secondary))]
    except KeyError as error:
        raise ValueError(f"unsupported Gleason pattern pair: {primary}+{secondary}") from error


def preparation_cache(image_id: str) -> Path:
    return ARTIFACTS / "panda_preparation_cache" / f"{image_id}.npz"


def embedding_cache(encoder: str, image_id: str) -> Path:
    return ARTIFACTS / "panda_embedding_cache" / encoder / f"{image_id}.npz"


def preparation_cache_valid(path: Path, image_id: str) -> bool:
    if not path.is_file():
        return False
    try:
        with np.load(path, allow_pickle=False) as cached:
            return bool(
                str(cached["image_id"].item()) == image_id
                and "mask_available" in cached
                and len(cached["tile_rank"]) == len(cached["level0_x0"])
                and len(cached["tile_rank"]) <= MAX_TILES
                and np.array_equal(cached["tile_rank"], np.arange(len(cached["tile_rank"])))
            )
    except (OSError, KeyError, ValueError):
        return False


def mask_fractions(mask_path: Path, candidates: list[dict[str, object]], provider: str) -> dict[str, np.ndarray]:
    fields = {
        "mask_background_fraction": [],
        "benign_or_stroma_fraction": [],
        "cancer_fraction": [],
        "gp3_fraction": [],
        "gp4_fraction": [],
        "gp5_fraction": [],
    }
    with tifffile.TiffFile(mask_path) as tif:
        page = tif.series[0].levels[0].pages[0]
        for row in candidates:
            rgb = FM6_RUNNER.read_tiled_rgb_region(
                page,
                int(row["level0_x0"]),
                int(row["level0_y0"]),
                int(row["level0_x1"]),
                int(row["level0_y1"]),
            )
            code = rgb[..., 0]
            fields["mask_background_fraction"].append(float(np.mean(code == 0)))
            fields["benign_or_stroma_fraction"].append(float(np.mean(code == 1)))
            if provider == "radboud":
                gp3 = float(np.mean(code == 2))
                gp4 = float(np.mean(code == 3))
                gp5 = float(np.mean(code == 4))
                fields["gp3_fraction"].append(gp3)
                fields["gp4_fraction"].append(gp4)
                fields["gp5_fraction"].append(gp5)
                fields["cancer_fraction"].append(gp3 + gp4 + gp5)
            elif provider == "karolinska":
                fields["cancer_fraction"].append(float(np.mean(code == 2)))
                fields["gp3_fraction"].append(np.nan)
                fields["gp4_fraction"].append(np.nan)
                fields["gp5_fraction"].append(np.nan)
            else:
                raise ValueError(provider)
    return {name: np.asarray(values, dtype=np.float32) for name, values in fields.items()}


def prepare_panda(shard_index: int, shard_count: int, limit: int | None) -> None:
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    frame = panda_labels()
    selected = frame.iloc[[index % shard_count == shard_index for index in range(len(frame))]]
    if limit is not None:
        selected = selected.head(limit)
    started = time.time()
    complete = 0
    reused = 0
    insufficient = 0
    for row in selected.itertuples(index=False):
        image_id = str(row.image_id)
        destination = preparation_cache(image_id)
        if preparation_cache_valid(destination, image_id):
            reused += 1
            complete += 1
            continue
        image_path = PANDA_IMAGES / f"{image_id}.tiff"
        mask_path = PANDA_MASKS / f"{image_id}_mask.tiff"
        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        # Sampling is completed from RGB tissue before labels or masks are attached.
        with tifffile.TiffFile(image_path) as tif:
            mpp = float(FM6_RUNNER.native_mpp(tif.series[0].levels[0].pages[0]))
        candidates, audit = FM6_RUNNER.slide_candidates(image_path, image_id, mpp)
        if audit["sampling_status"] != "PASS":
            insufficient += 1
        if mask_path.is_file():
            annotation = mask_fractions(mask_path, candidates, str(row.data_provider))
        else:
            annotation = {
                name: np.full(len(candidates), np.nan, dtype=np.float32)
                for name in (
                    "mask_background_fraction",
                    "benign_or_stroma_fraction",
                    "cancer_fraction",
                    "gp3_fraction",
                    "gp4_fraction",
                    "gp5_fraction",
                )
            }
        primary, secondary = parse_gleason(str(row.gleason_score))
        arrays: dict[str, object] = {
            "image_id": np.asarray(image_id),
            "data_provider": np.asarray(str(row.data_provider)),
            "isup_grade": np.asarray(int(row.isup_grade), dtype=np.int8),
            "gleason_primary": np.asarray(primary, dtype=np.int8),
            "gleason_secondary": np.asarray(secondary, dtype=np.int8),
            "mpp": np.asarray(mpp, dtype=np.float64),
            "sampling_status": np.asarray(str(audit["sampling_status"])),
            "mask_available": np.asarray(mask_path.is_file()),
            "candidate_count": np.asarray(int(audit["candidate_count"]), dtype=np.int32),
        }
        for key in (
            "tile_rank",
            "level0_x0",
            "level0_y0",
            "level0_x1",
            "level0_y1",
            "thumbnail_tissue_fraction",
        ):
            dtype = np.float32 if key == "thumbnail_tissue_fraction" else np.int32
            arrays[key] = np.asarray([candidate[key] for candidate in candidates], dtype=dtype)
        arrays.update(annotation)
        atomic_npz(destination, **arrays)
        complete += 1
        if complete % 25 == 0 or complete == len(selected):
            print(
                f"PANDA prepare shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(selected)} slides (reused={reused}, insufficient={insufficient})",
                flush=True,
            )
    run = {
        "stage": "prepare-panda",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "physical_fov_um": FOV_UM,
        "max_tiles_per_slide": MAX_TILES,
        "min_tiles_per_slide": MIN_TILES,
        "sampling_inputs": "decoded RGB tissue only; labels and masks attached after coordinate selection",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "requested_slides": len(selected),
        "completed_slides": complete,
        "reused_slides": reused,
        "insufficient_tissue_slides": insufficient,
        "runtime_seconds": round(time.time() - started, 6),
    }
    run_path = ARTIFACTS / "run_records" / f"prepare_panda_{shard_index:03d}_of_{shard_count:03d}.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cache_rows(image_id: str) -> list[dict[str, object]]:
    path = preparation_cache(image_id)
    if not preparation_cache_valid(path, image_id):
        raise RuntimeError(f"missing or invalid PANDA preparation cache: {image_id}")
    with np.load(path, allow_pickle=False) as cached:
        n = len(cached["tile_rank"])
        scalar = {
            "image_id": str(cached["image_id"].item()),
            "data_provider": str(cached["data_provider"].item()),
            "isup_grade": int(cached["isup_grade"].item()),
            "gleason_primary": int(cached["gleason_primary"].item()),
            "gleason_secondary": int(cached["gleason_secondary"].item()),
            "mpp": float(cached["mpp"].item()),
            "sampling_status": str(cached["sampling_status"].item()),
            "mask_available": bool(cached["mask_available"].item()),
        }
        vector_fields = (
            "tile_rank",
            "level0_x0",
            "level0_y0",
            "level0_x1",
            "level0_y1",
            "thumbnail_tissue_fraction",
            "mask_background_fraction",
            "benign_or_stroma_fraction",
            "cancer_fraction",
            "gp3_fraction",
            "gp4_fraction",
            "gp5_fraction",
        )
        return [
            {
                **scalar,
                "tile_id": f"{image_id}:{index:03d}",
                **{field: cached[field][index].item() for field in vector_fields},
            }
            for index in range(n)
        ]


def preparation_sampling_status(image_id: str) -> str:
    path = preparation_cache(image_id)
    if not preparation_cache_valid(path, image_id):
        return "MISSING"
    with np.load(path, allow_pickle=False) as cached:
        return str(cached["sampling_status"].item())


def assemble_panda_manifest() -> None:
    frame = panda_labels()
    missing = [image_id for image_id in frame.image_id if not preparation_cache_valid(preparation_cache(image_id), image_id)]
    if missing:
        raise RuntimeError(f"PANDA preparation incomplete: {len(missing)} missing; first={missing[0]}")
    rows: list[dict[str, object]] = []
    for index, image_id in enumerate(frame.image_id, 1):
        rows.extend(cache_rows(image_id))
        if index % 500 == 0 or index == len(frame):
            print(f"assemble PANDA manifest {index}/{len(frame)} slides", flush=True)
    manifest = pd.DataFrame(rows)
    manifest.insert(0, "embedding_row", np.arange(len(manifest), dtype=np.int64))
    if manifest.tile_id.duplicated().any():
        raise RuntimeError("duplicate PANDA tile identity")
    destination = ARTIFACTS / "fm8_panda_tile_manifest.csv.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(
        destination,
        index=False,
        compression={"method": "gzip", "mtime": 0},
        lineterminator="\n",
    )
    summary = pd.DataFrame(
        [
            {
                "cohort": "PANDA_PUBLIC_DEVELOPMENT",
                "source_slides": len(frame),
                "eligible_slides": int(manifest.loc[manifest.sampling_status.eq("PASS"), "image_id"].nunique()),
                "excluded_insufficient_tissue_slides": int(
                    len(frame) - manifest.image_id.nunique()
                ),
                "tiles": len(manifest),
                "tiles_per_slide_min": int(manifest.groupby("image_id").size().min()),
                "tiles_per_slide_median": float(manifest.groupby("image_id").size().median()),
                "tiles_per_slide_max": int(manifest.groupby("image_id").size().max()),
                "radboud_pattern_truth_tiles": int(
                    (manifest.data_provider.eq("radboud") & manifest.mask_available).sum()
                ),
                "karolinska_pattern_truth_tiles": 0,
                "slides_without_masks": int(
                    manifest.loc[~manifest.mask_available, "image_id"].nunique()
                ),
                "sampling_outcome_blind": True,
                "manifest_sha256": sha256_file(destination),
            }
        ]
    )
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUTS / "fm8_panda_tile_preparation_summary.csv", index=False, lineterminator="\n")


def load_prepared_slide(image_id: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rows = pd.DataFrame(cache_rows(image_id))
    image_path = PANDA_IMAGES / f"{image_id}.tiff"
    crops: list[np.ndarray] = []
    hashes: list[str] = []
    with tifffile.TiffFile(image_path) as tif:
        page = tif.series[0].levels[0].pages[0]
        for row in rows.itertuples(index=False):
            rgb = FM6_RUNNER.read_tiled_rgb_region(
                page, row.level0_x0, row.level0_y0, row.level0_x1, row.level0_y1
            )
            hashes.append(hashlib.sha256(rgb.tobytes(order="C")).hexdigest())
            canonical = Image.fromarray(rgb, mode="RGB").resize((448, 448), Image.Resampling.BICUBIC)
            crops.append(np.asarray(canonical, dtype=np.uint8))
    return rows, np.stack(crops), np.asarray(hashes, dtype="U64")


def embedding_cache_valid(path: Path, image_id: str, encoder: str, tile_ids: np.ndarray) -> bool:
    if not path.is_file():
        return False
    try:
        with np.load(path, allow_pickle=False) as cached:
            return bool(
                str(cached["image_id"].item()) == image_id
                and str(cached["encoder"].item()) == encoder
                and cached["embedding"].shape == (len(tile_ids), DIMENSION[encoder])
                and np.array_equal(cached["tile_id"].astype(str), tile_ids.astype(str))
                and np.isfinite(cached["embedding"]).all()
            )
    except (OSError, KeyError, ValueError):
        return False


def extract_panda(encoder: str, shard_index: int, shard_count: int, limit: int | None, smoke_only: bool) -> None:
    import torch

    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    frame = panda_labels()
    selected = frame.iloc[[index % shard_count == shard_index for index in range(len(frame))]]
    selected = selected[
        selected.image_id.map(lambda value: preparation_sampling_status(value) == "PASS")
    ]
    if limit is not None:
        selected = selected.head(limit)
    if selected.empty:
        raise RuntimeError("no prepared PANDA slides selected")
    device = FM6_RUNNER.configure_device()
    model, _ = FM6_RUNNER.load_model(encoder, device)
    first_id = str(selected.image_id.iloc[0])
    first_rows, first_crops, _ = load_prepared_slide(first_id)
    smoke = first_crops[: min(4, len(first_crops))]
    tensor = FM6_RUNNER.transform_canonical_batch(encoder, smoke, device)
    with torch.inference_mode():
        first = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if first.shape != (len(smoke), DIMENSION[encoder]) or not np.array_equal(first, second):
        raise RuntimeError(f"{encoder} deterministic smoke failure")
    print(json.dumps({"encoder": encoder, "smoke_shape": list(first.shape), "exact_repeat": True}), flush=True)
    if smoke_only:
        return

    complete = 0
    reused = 0
    started = time.time()
    for image_id in selected.image_id.astype(str):
        rows = pd.DataFrame(cache_rows(image_id))
        tile_ids = rows.tile_id.to_numpy(str)
        destination = embedding_cache(encoder, image_id)
        if embedding_cache_valid(destination, image_id, encoder, tile_ids):
            reused += 1
            complete += 1
            continue
        rows, crops, crop_hashes = load_prepared_slide(image_id)
        values: list[np.ndarray] = []
        for start in range(0, len(crops), BATCH_SIZE[encoder]):
            batch = FM6_RUNNER.transform_canonical_batch(
                encoder, crops[start : start + BATCH_SIZE[encoder]], device
            )
            with torch.inference_mode():
                values.append(
                    FM6_RUNNER.embed_batch(encoder, model, batch).detach().cpu().float().numpy()
                )
        embedding = np.concatenate(values).astype(np.float32, copy=False)
        if embedding.shape != (len(rows), DIMENSION[encoder]) or not np.isfinite(embedding).all():
            raise RuntimeError(f"invalid {encoder} embedding: {image_id}")
        atomic_npz(
            destination,
            image_id=np.asarray(image_id),
            encoder=np.asarray(encoder),
            tile_id=rows.tile_id.to_numpy(str),
            decoded_rgb_sha256=crop_hashes,
            embedding=embedding,
        )
        complete += 1
        if complete % 10 == 0 or complete == len(selected):
            print(
                f"PANDA {encoder} shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(selected)} slides (reused={reused})",
                flush=True,
            )
    run = {
        "stage": "extract-panda",
        "encoder": encoder,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "completed_slides": complete,
        "reused_slides": reused,
        "runtime_seconds": round(time.time() - started, 6),
    }
    run_path = ARTIFACTS / "run_records" / f"extract_panda_{encoder}_{shard_index:03d}_of_{shard_count:03d}.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()


def extract_panda_paired(shard_index: int, shard_count: int, limit: int | None) -> None:
    """Decode each canonical crop once and populate both frozen-encoder caches."""
    import torch

    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    frame = panda_labels()
    selected = frame.iloc[[index % shard_count == shard_index for index in range(len(frame))]]
    selected = selected[selected.image_id.map(lambda value: preparation_sampling_status(value) == "PASS")]
    if limit is not None:
        selected = selected.head(limit)
    if selected.empty:
        raise RuntimeError("no prepared PANDA slides selected")
    device = FM6_RUNNER.configure_device()
    models = {encoder: FM6_RUNNER.load_model(encoder, device)[0] for encoder in ("conch", "virchow")}
    first_id = str(selected.image_id.iloc[0])
    _, smoke_crops, _ = load_prepared_slide(first_id)
    for encoder, model in models.items():
        tensor = FM6_RUNNER.transform_canonical_batch(encoder, smoke_crops[:4], device)
        with torch.inference_mode():
            first = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
            second = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        if first.shape != (4, DIMENSION[encoder]) or not np.array_equal(first, second):
            raise RuntimeError(f"paired {encoder} deterministic smoke failure")
    print(json.dumps({"paired_encoders": ["conch", "virchow"], "exact_repeat": True}), flush=True)

    complete = 0
    reused_both = 0
    started = time.time()
    for image_id in selected.image_id.astype(str):
        source_rows = pd.DataFrame(cache_rows(image_id))
        tile_ids = source_rows.tile_id.to_numpy(str)
        valid = {
            encoder: embedding_cache_valid(
                embedding_cache(encoder, image_id), image_id, encoder, tile_ids
            )
            for encoder in models
        }
        if all(valid.values()):
            with np.load(embedding_cache("conch", image_id), allow_pickle=False) as conch_cache:
                conch_hashes = conch_cache["decoded_rgb_sha256"].astype(str)
            with np.load(embedding_cache("virchow", image_id), allow_pickle=False) as virchow_cache:
                virchow_hashes = virchow_cache["decoded_rgb_sha256"].astype(str)
            if not np.array_equal(conch_hashes, virchow_hashes):
                raise RuntimeError(f"existing paired crop mismatch: {image_id}")
            reused_both += 1
            complete += 1
            continue

        rows, crops, crop_hashes = load_prepared_slide(image_id)
        for encoder, model in models.items():
            if valid[encoder]:
                with np.load(embedding_cache(encoder, image_id), allow_pickle=False) as cached:
                    if not np.array_equal(crop_hashes, cached["decoded_rgb_sha256"].astype(str)):
                        raise RuntimeError(f"existing/current crop mismatch: {encoder} {image_id}")
                continue
            values: list[np.ndarray] = []
            for start in range(0, len(crops), BATCH_SIZE[encoder]):
                batch = FM6_RUNNER.transform_canonical_batch(
                    encoder, crops[start : start + BATCH_SIZE[encoder]], device
                )
                with torch.inference_mode():
                    values.append(
                        FM6_RUNNER.embed_batch(encoder, model, batch).detach().cpu().float().numpy()
                    )
            embedding = np.concatenate(values).astype(np.float32, copy=False)
            if embedding.shape != (len(rows), DIMENSION[encoder]) or not np.isfinite(embedding).all():
                raise RuntimeError(f"invalid paired {encoder} embedding: {image_id}")
            atomic_npz(
                embedding_cache(encoder, image_id),
                image_id=np.asarray(image_id),
                encoder=np.asarray(encoder),
                tile_id=rows.tile_id.to_numpy(str),
                decoded_rgb_sha256=crop_hashes,
                embedding=embedding,
            )
        complete += 1
        if complete % 10 == 0 or complete == len(selected):
            print(
                f"PANDA paired shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(selected)} slides (reused_both={reused_both})",
                flush=True,
            )
    run = {
        "stage": "extract-panda-paired",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "completed_slides": complete,
        "reused_both": reused_both,
        "single_decode_for_both_encoders": True,
        "runtime_seconds": round(time.time() - started, 6),
    }
    path = ARTIFACTS / "run_records" / f"extract_panda_paired_{shard_index:03d}_of_{shard_count:03d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    del models, tensor
    gc.collect()
    torch.cuda.empty_cache()


def assemble_panda_embeddings(encoder: str) -> None:
    frame = panda_labels()
    eligible_ids = [
        image_id
        for image_id in frame.image_id.astype(str)
        if preparation_sampling_status(image_id) == "PASS"
    ]
    bag_path = ARTIFACTS / f"fm8_panda_{encoder}_tile_bags.npy"
    bag_mask_path = ARTIFACTS / f"fm8_panda_{encoder}_tile_bag_mask.npy"
    bag = np.lib.format.open_memmap(
        bag_path,
        mode="w+",
        dtype=np.float32,
        shape=(len(eligible_ids), MAX_TILES, DIMENSION[encoder]),
    )
    bag[:] = 0.0
    bag_mask = np.lib.format.open_memmap(
        bag_mask_path,
        mode="w+",
        dtype=np.bool_,
        shape=(len(eligible_ids), MAX_TILES),
    )
    bag_mask[:] = False
    slide_vectors: list[np.ndarray] = []
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for image_id in frame.image_id.astype(str):
        if preparation_sampling_status(image_id) != "PASS":
            continue
        preparation = pd.DataFrame(cache_rows(image_id))
        tile_ids = preparation.tile_id.to_numpy(str)
        path = embedding_cache(encoder, image_id)
        if not embedding_cache_valid(path, image_id, encoder, tile_ids):
            missing.append(image_id)
            continue
        with np.load(path, allow_pickle=False) as cached:
            embedding = cached["embedding"].astype(np.float64)
            hashes = cached["decoded_rgb_sha256"].astype(str)
        if len(embedding) > MAX_TILES:
            raise RuntimeError(f"PANDA tile cap exceeded: {image_id}")
        bag[len(rows), : len(embedding)] = embedding.astype(np.float32)
        bag_mask[len(rows), : len(embedding)] = True
        other = "virchow" if encoder == "conch" else "conch"
        other_path = embedding_cache(other, image_id)
        paired_hash = "NOT_EVALUABLE"
        if embedding_cache_valid(other_path, image_id, other, tile_ids):
            with np.load(other_path, allow_pickle=False) as cached:
                paired_hash = "PASS" if np.array_equal(hashes, cached["decoded_rgb_sha256"].astype(str)) else "FAIL"
            if paired_hash == "FAIL":
                raise RuntimeError(f"cross-encoder decoded crop mismatch: {image_id}")
        slide_vectors.append(embedding.mean(axis=0).astype(np.float32))
        source = preparation.iloc[0]
        rows.append(
            {
                "embedding_row": len(rows),
                "image_id": image_id,
                "data_provider": source.data_provider,
                "isup_grade": int(source.isup_grade),
                "gleason_primary": int(source.gleason_primary),
                "gleason_secondary": int(source.gleason_secondary),
                "n_tiles": len(preparation),
                "paired_crop_hash_status": paired_hash,
            }
        )
    if missing:
        raise RuntimeError(f"PANDA {encoder} embeddings incomplete: {len(missing)} missing; first={missing[0]}")
    values = np.stack(slide_vectors)
    row_frame = pd.DataFrame(rows)
    if values.shape != (len(rows), DIMENSION[encoder]) or not np.isfinite(values).all():
        raise RuntimeError(f"invalid assembled PANDA {encoder} slide embeddings")
    array_path = ARTIFACTS / f"fm8_panda_{encoder}_slide_embeddings.npy"
    row_path = ARTIFACTS / f"fm8_panda_{encoder}_slide_rows.csv"
    np.save(array_path, values, allow_pickle=False)
    row_frame.to_csv(row_path, index=False, lineterminator="\n")
    bag.flush()
    bag_mask.flush()
    del bag, bag_mask
    spec = FM6_RUNNER.model_spec(encoder)
    qc = pd.DataFrame(
        [
            {
                "cohort": "PANDA_PUBLIC_DEVELOPMENT",
                "encoder": encoder,
                "model_id": spec["model_id"],
                "model_revision": spec["revision"],
                "weights_sha256": sha256_file(Path(spec["weights"])),
                "slides": len(values),
                "dimension": values.shape[1],
                "nonfinite": int((~np.isfinite(values)).sum()),
                "embedding_sha256": sha256_file(array_path),
                "row_manifest_sha256": sha256_file(row_path),
                "tile_bag_sha256": sha256_file(bag_path),
                "tile_bag_mask_sha256": sha256_file(bag_mask_path),
                "paired_crop_hash_failures": int(row_frame.paired_crop_hash_status.eq("FAIL").sum()),
                "status": "PASS",
            }
        ]
    )
    qc_path = OUTPUTS / "fm8_panda_embedding_technical_qc.csv"
    if qc_path.exists():
        prior = pd.read_csv(qc_path)
        qc = pd.concat([prior[prior.encoder.ne(encoder)], qc], ignore_index=True)
    qc.sort_values("encoder").to_csv(qc_path, index=False, lineterminator="\n")


def sicap_test_manifest() -> pd.DataFrame:
    patch = pd.read_excel(SICAP_ROOT / "partition/Test/Test.xlsx")
    slide = pd.read_excel(SICAP_ROOT / "wsi_labels.xlsx")
    required_patch = {"image_name", "NC", "G3", "G4", "G5", "G4C"}
    required_slide = {"slide_id", "patient_id", "Gleason_primary", "Gleason_secondary"}
    if not required_patch.issubset(patch.columns) or not required_slide.issubset(slide.columns):
        raise RuntimeError("SICAPv2 official Test schema changed")
    patch = patch.copy()
    patch["slide_id"] = patch.image_name.str.extract(r"^([^_]+)")[0]
    frame = patch.merge(slide[list(required_slide)], on="slide_id", how="left", validate="many_to_one")
    if len(frame) != 2122 or frame.slide_id.nunique() != 31 or frame.patient_id.nunique() != 21:
        raise RuntimeError("SICAPv2 official Test identity universe changed")
    if frame[list(required_slide)].isna().any().any() or frame.image_name.duplicated().any():
        raise RuntimeError("SICAPv2 official Test label/identity failure")
    frame["isup_grade"] = [
        isup_from_patterns(primary, secondary)
        for primary, secondary in zip(frame.Gleason_primary, frame.Gleason_secondary)
    ]
    frame.insert(0, "embedding_row", np.arange(len(frame), dtype=np.int64))
    return frame.sort_values("embedding_row").reset_index(drop=True)


def extract_sicap(encoder: str, smoke_only: bool) -> None:
    import torch

    manifest = sicap_test_manifest()
    device = FM6_RUNNER.configure_device()
    model, _ = FM6_RUNNER.load_model(encoder, device)

    def load_rgb(image_name: str) -> tuple[np.ndarray, str]:
        path = SICAP_ROOT / "images" / image_name
        with Image.open(path) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        digest = hashlib.sha256(rgb.tobytes(order="C")).hexdigest()
        canonical = np.asarray(
            Image.fromarray(rgb, mode="RGB").resize((448, 448), Image.Resampling.BICUBIC),
            dtype=np.uint8,
        )
        return canonical, digest

    smoke = np.stack([load_rgb(name)[0] for name in manifest.image_name.iloc[:4]])
    tensor = FM6_RUNNER.transform_canonical_batch(encoder, smoke, device)
    with torch.inference_mode():
        first = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if first.shape != (4, DIMENSION[encoder]) or not np.array_equal(first, second):
        raise RuntimeError(f"{encoder} SICAP deterministic smoke failure")
    print(json.dumps({"cohort": "SICAPV2_OFFICIAL_TEST", "encoder": encoder, "exact_repeat": True}), flush=True)
    if smoke_only:
        return

    values: list[np.ndarray] = []
    hashes: list[str] = []
    started = time.time()
    for start in range(0, len(manifest), BATCH_SIZE[encoder]):
        part = manifest.iloc[start : start + BATCH_SIZE[encoder]]
        loaded = [load_rgb(name) for name in part.image_name]
        crops = np.stack([item[0] for item in loaded])
        hashes.extend(item[1] for item in loaded)
        tensor = FM6_RUNNER.transform_canonical_batch(encoder, crops, device)
        with torch.inference_mode():
            values.append(
                FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
            )
        print(f"SICAP {encoder}: {min(start + len(part), len(manifest))}/{len(manifest)} patches", flush=True)
    embedding = np.concatenate(values).astype(np.float32, copy=False)
    hash_array = np.asarray(hashes, dtype="U64")
    if embedding.shape != (len(manifest), DIMENSION[encoder]) or not np.isfinite(embedding).all():
        raise RuntimeError(f"invalid SICAP {encoder} embeddings")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    embedding_path = ARTIFACTS / f"fm8_sicap_{encoder}_patch_embeddings.npy"
    hash_path = ARTIFACTS / f"fm8_sicap_{encoder}_crop_hashes.npy"
    manifest_path = ARTIFACTS / "fm8_sicap_test_patch_manifest.csv"
    np.save(embedding_path, embedding, allow_pickle=False)
    np.save(hash_path, hash_array, allow_pickle=False)
    manifest.to_csv(manifest_path, index=False, lineterminator="\n")
    other = "virchow" if encoder == "conch" else "conch"
    other_hash_path = ARTIFACTS / f"fm8_sicap_{other}_crop_hashes.npy"
    paired = "NOT_EVALUABLE"
    if other_hash_path.is_file():
        paired = "PASS" if np.array_equal(hash_array, np.load(other_hash_path, allow_pickle=False)) else "FAIL"
        if paired == "FAIL":
            raise RuntimeError("SICAP cross-encoder decoded crop mismatch")
    spec = FM6_RUNNER.model_spec(encoder)
    row = pd.DataFrame(
        [
            {
                "cohort": "SICAPV2_OFFICIAL_TEST",
                "encoder": encoder,
                "model_id": spec["model_id"],
                "model_revision": spec["revision"],
                "weights_sha256": sha256_file(Path(spec["weights"])),
                "patients": int(manifest.patient_id.nunique()),
                "slides": int(manifest.slide_id.nunique()),
                "patches": len(manifest),
                "dimension": embedding.shape[1],
                "embedding_sha256": sha256_file(embedding_path),
                "crop_hash_sha256": sha256_file(hash_path),
                "paired_crop_hash_status": paired,
                "runtime_seconds": round(time.time() - started, 6),
                "status": "PASS",
            }
        ]
    )
    qc_path = OUTPUTS / "fm8_sicap_embedding_technical_qc.csv"
    if qc_path.exists():
        prior = pd.read_csv(qc_path)
        row = pd.concat([prior[prior.encoder.ne(encoder)], row], ignore_index=True)
    row.sort_values("encoder").to_csv(qc_path, index=False, lineterminator="\n")
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()


def audit_sicap_pairing() -> None:
    conch_path = ARTIFACTS / "fm8_sicap_conch_crop_hashes.npy"
    virchow_path = ARTIFACTS / "fm8_sicap_virchow_crop_hashes.npy"
    if not conch_path.is_file() or not virchow_path.is_file():
        raise FileNotFoundError("both SICAP encoder crop-hash arrays are required")
    conch = np.load(conch_path, allow_pickle=False)
    virchow = np.load(virchow_path, allow_pickle=False)
    same = bool(np.array_equal(conch, virchow))
    qc_path = OUTPUTS / "fm8_sicap_embedding_technical_qc.csv"
    qc = pd.read_csv(qc_path)
    if set(qc.encoder) != {"conch", "virchow"}:
        raise RuntimeError("SICAP paired QC encoder universe failure")
    qc["paired_crop_hash_status"] = "PASS" if same else "FAIL"
    qc.sort_values("encoder").to_csv(qc_path, index=False, lineterminator="\n")
    audit = {
        "cohort": "SICAPV2_OFFICIAL_TEST",
        "rows": len(conch),
        "decoded_crop_hashes_identical_across_encoders": same,
        "status": "PASS" if same else "FAIL",
    }
    (OUTPUTS / "fm8_sicap_paired_embedding_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not same:
        raise RuntimeError("SICAP paired crop hashes differ")


def ordinal_probabilities(logits: np.ndarray) -> np.ndarray:
    """Convert five all-threshold logits into monotone ISUP 0--5 probabilities."""
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 5:
        raise ValueError(f"expected (n, 5) logits, observed {values.shape}")
    tail = 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))
    tail = np.minimum.accumulate(tail, axis=1)
    probability = np.empty((len(tail), 6), dtype=np.float64)
    probability[:, 0] = 1.0 - tail[:, 0]
    probability[:, 1:5] = tail[:, :4] - tail[:, 1:5]
    probability[:, 5] = tail[:, 4]
    probability = np.clip(probability, 0.0, 1.0)
    probability /= probability.sum(axis=1, keepdims=True)
    return probability


def grading_metrics(truth: np.ndarray, prediction: np.ndarray, probability: np.ndarray) -> dict[str, float | int]:
    y = np.asarray(truth, dtype=int)
    pred = np.asarray(prediction, dtype=int)
    if y.shape != pred.shape or probability.shape != (len(y), 6):
        raise ValueError("grading metric input shape mismatch")
    cancer = y > 0
    cancer_qwk = float("nan")
    if cancer.sum() >= 2 and len(np.unique(y[cancer])) >= 2 and len(np.unique(pred[cancer])) >= 2:
        cancer_qwk = float(cohen_kappa_score(y[cancer], pred[cancer], weights="quadratic"))
    result: dict[str, float | int] = {
        "n": len(y),
        "n_cancer": int(cancer.sum()),
        "cancer_only_qwk": cancer_qwk,
        "cancer_only_mae": float(np.mean(np.abs(pred[cancer] - y[cancer]))) if cancer.any() else float("nan"),
        "cancer_only_exact": float(np.mean(pred[cancer] == y[cancer])) if cancer.any() else float("nan"),
        "cancer_only_within_one": float(np.mean(np.abs(pred[cancer] - y[cancer]) <= 1)) if cancer.any() else float("nan"),
        "cancer_only_severe_error": float(np.mean(np.abs(pred[cancer] - y[cancer]) >= 2)) if cancer.any() else float("nan"),
    }
    one_hot = np.eye(6, dtype=np.float64)[y]
    expected_grade = probability @ np.arange(6, dtype=np.float64)
    result["ordinal_multiclass_brier"] = float(np.mean(np.sum((probability - one_hot) ** 2, axis=1)))
    result["ordinal_log_loss"] = float(
        np.mean(-np.log(np.clip(probability[np.arange(len(y)), y], 1e-12, 1.0)))
    )
    result["ordinal_expected_grade_mae"] = float(np.mean(np.abs(expected_grade - y)))
    cancer_probability = 1.0 - probability[:, 0]
    result["cancer_detection_auroc"] = (
        float(roc_auc_score(cancer.astype(int), cancer_probability))
        if len(np.unique(cancer)) == 2
        else float("nan")
    )
    detected = cancer_probability >= 0.5
    result["cancer_detection_sensitivity"] = float(np.mean(detected[cancer])) if cancer.any() else float("nan")
    result["cancer_detection_specificity"] = float(np.mean(~detected[~cancer])) if (~cancer).any() else float("nan")
    for grade in range(1, 6):
        selected = y == grade
        result[f"grade_{grade}_recall"] = float(np.mean(pred[selected] == grade)) if selected.any() else float("nan")
    recalls = [result[f"grade_{grade}_recall"] for grade in range(1, 6)]
    result["cancer_only_macro_recall"] = float(np.nanmean(recalls))
    return result


def confusion_rows(
    truth: np.ndarray,
    prediction: np.ndarray,
    cohort: str,
    encoder: str,
    reference: str,
) -> list[dict[str, object]]:
    y = np.asarray(truth, dtype=int)
    pred = np.asarray(prediction, dtype=int)
    if y.shape != pred.shape:
        raise ValueError("confusion input shape mismatch")
    return [
        {
            "cohort": cohort,
            "encoder": encoder,
            "reference": reference,
            "truth_isup": truth_grade,
            "predicted_isup": predicted_grade,
            "n": int(np.sum((y == truth_grade) & (pred == predicted_grade))),
        }
        for truth_grade in range(6)
        for predicted_grade in range(6)
    ]


def build_ordinal_mil(dimension: int) -> object:
    import torch

    class GatedOrdinalMIL(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.norm = torch.nn.LayerNorm(dimension)
            self.attention_v = torch.nn.Linear(dimension, HEAD_HIDDEN)
            self.attention_u = torch.nn.Linear(dimension, HEAD_HIDDEN)
            self.attention_w = torch.nn.Linear(HEAD_HIDDEN, 1, bias=False)
            self.ordinal = torch.nn.Linear(dimension, 5)

        def forward(self, bag: object, mask: object) -> object:
            normalized = self.norm(bag)
            attention = self.attention_w(
                torch.tanh(self.attention_v(normalized))
                * torch.sigmoid(self.attention_u(normalized))
            ).squeeze(-1)
            attention = attention.masked_fill(~mask, -torch.inf)
            weight = torch.softmax(attention, dim=1)
            pooled = torch.sum(weight.unsqueeze(-1) * normalized, dim=1)
            return self.ordinal(pooled)

    return GatedOrdinalMIL()


def build_mean_ordinal_linear(
    dimension: int,
    center: np.ndarray | None = None,
    scale: np.ndarray | None = None,
) -> object:
    import torch

    feature_center = np.zeros(dimension, dtype=np.float32) if center is None else np.asarray(center, dtype=np.float32)
    feature_scale = np.ones(dimension, dtype=np.float32) if scale is None else np.asarray(scale, dtype=np.float32)
    if feature_center.shape != (dimension,) or feature_scale.shape != (dimension,):
        raise ValueError("mean-linear feature standardization shape mismatch")

    class MeanOrdinalLinear(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.register_buffer("feature_center", torch.from_numpy(feature_center.copy()))
            self.register_buffer("feature_scale", torch.from_numpy(feature_scale.copy()))
            self.ordinal = torch.nn.Linear(dimension, 5)

        def forward(self, bag: object, mask: object) -> object:
            weight = mask.to(dtype=bag.dtype).unsqueeze(-1)
            pooled = torch.sum(bag * weight, dim=1) / torch.clamp(weight.sum(dim=1), min=1.0)
            standardized = (pooled - self.feature_center) / self.feature_scale
            return self.ordinal(standardized)

    return MeanOrdinalLinear()


def architecture_output_token(architecture: str) -> str:
    if architecture not in HEAD_ARCHITECTURES:
        raise ValueError(f"unknown grading architecture: {architecture}")
    return "" if architecture == "gated_mil" else "_mean_linear"


def head_checkpoint_path(encoder: str, architecture: str) -> Path:
    architecture_output_token(architecture)
    name = (
        f"fm8_panda_{encoder}_ordinal_mil_head.pt"
        if architecture == "gated_mil"
        else f"fm8_panda_{encoder}_mean_linear_ordinal_head.pt"
    )
    return ARTIFACTS / name


def mean_linear_inputs(
    slide_embedding: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if slide_embedding.ndim != 2:
        raise ValueError("mean-linear inputs require a two-dimensional slide embedding array")
    return slide_embedding[:, None, :], np.ones((len(slide_embedding), 1), dtype=bool)


def configure_training_device(seed: int) -> object:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device required; run outside sandbox")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


def train_epoch(
    model: object,
    bag: np.ndarray,
    bag_mask: np.ndarray,
    labels: np.ndarray,
    indices: np.ndarray,
    optimizer: object,
    loss_function: object,
    device: object,
    epoch_seed: int,
) -> float:
    import torch

    model.train()
    generator = np.random.default_rng(epoch_seed)
    order = generator.permutation(indices)
    losses: list[float] = []
    for start in range(0, len(order), HEAD_BATCH_SIZE):
        selected = order[start : start + HEAD_BATCH_SIZE]
        x = torch.from_numpy(np.asarray(bag[selected], dtype=np.float32)).to(device)
        mask = torch.from_numpy(np.asarray(bag_mask[selected], dtype=bool)).to(device)
        y = torch.from_numpy((labels[selected, None] > np.arange(5)[None, :]).astype(np.float32)).to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x, mask)
        loss = loss_function(logits, y)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    return float(np.mean(losses))


def predict_bags(model: object, bag: np.ndarray, bag_mask: np.ndarray, indices: np.ndarray, device: object) -> np.ndarray:
    import torch

    model.eval()
    values: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, len(indices), HEAD_BATCH_SIZE):
            selected = indices[start : start + HEAD_BATCH_SIZE]
            x = torch.from_numpy(np.asarray(bag[selected], dtype=np.float32)).to(device)
            mask = torch.from_numpy(np.asarray(bag_mask[selected], dtype=bool)).to(device)
            values.append(model(x, mask).detach().cpu().float().numpy())
    return np.concatenate(values)


def threshold_pos_weight(labels: np.ndarray, device: object) -> object:
    import torch

    target = labels[:, None] > np.arange(5)[None, :]
    positive = target.sum(axis=0)
    negative = len(target) - positive
    weight = np.clip(negative / np.maximum(positive, 1), 0.25, 4.0).astype(np.float32)
    return torch.from_numpy(weight).to(device)


def state_dict_sha256(state_dict: dict[str, object]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state_dict):
        array = state_dict[name].detach().cpu().numpy()
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("utf-8"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def train_grading_head(encoder: str, architecture: str) -> None:
    import torch

    bag_path = ARTIFACTS / f"fm8_panda_{encoder}_tile_bags.npy"
    mask_path = ARTIFACTS / f"fm8_panda_{encoder}_tile_bag_mask.npy"
    row_path = ARTIFACTS / f"fm8_panda_{encoder}_slide_rows.csv"
    slide_embedding_path = ARTIFACTS / f"fm8_panda_{encoder}_slide_embeddings.npy"
    for path in (bag_path, mask_path, row_path, slide_embedding_path):
        if not path.is_file():
            raise FileNotFoundError(f"assemble PANDA embeddings first: {path}")
    bag = np.load(bag_path, mmap_mode="r", allow_pickle=False)
    bag_mask = np.load(mask_path, mmap_mode="r", allow_pickle=False)
    rows = pd.read_csv(row_path, dtype={"image_id": str})
    labels = rows.isup_grade.to_numpy(int)
    if bag.shape != (len(rows), MAX_TILES, DIMENSION[encoder]) or bag_mask.shape != (len(rows), MAX_TILES):
        raise RuntimeError("PANDA grading bag identity/shape failure")
    strata = rows.data_provider.astype(str) + "_" + rows.isup_grade.astype(str)
    all_indices = np.arange(len(rows), dtype=int)
    development, validation = train_test_split(
        all_indices, test_size=0.2, random_state=SEED, stratify=strata
    )
    if architecture == "mean_linear":
        slide_embedding = np.load(slide_embedding_path, mmap_mode="r", allow_pickle=False)
        if slide_embedding.shape != (len(rows), DIMENSION[encoder]):
            raise RuntimeError("PANDA slide-mean embedding identity/shape failure")
        training_bag, training_mask = mean_linear_inputs(slide_embedding)
        development_center = np.asarray(slide_embedding[development], dtype=np.float64).mean(axis=0)
        development_scale = np.asarray(slide_embedding[development], dtype=np.float64).std(axis=0)
        development_scale = np.maximum(development_scale, 1e-6)
        model = build_mean_ordinal_linear(
            DIMENSION[encoder], development_center, development_scale
        )
    elif architecture == "gated_mil":
        training_bag, training_mask = bag, bag_mask
        model = build_ordinal_mil(DIMENSION[encoder])
    else:
        raise ValueError(f"unknown grading architecture: {architecture}")
    device = configure_training_device(SEED)
    model = model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=HEAD_LEARNING_RATE, weight_decay=HEAD_WEIGHT_DECAY
    )
    loss_function = torch.nn.BCEWithLogitsLoss(
        pos_weight=threshold_pos_weight(labels[development], device)
    )
    epoch_rows: list[dict[str, object]] = []
    best_epoch = 1
    best_qwk = -np.inf
    best_state: dict[str, object] | None = None
    started = time.time()
    for epoch in range(1, HEAD_MAX_EPOCHS + 1):
        loss = train_epoch(
            model,
            training_bag,
            training_mask,
            labels,
            development,
            optimizer,
            loss_function,
            device,
            SEED + epoch,
        )
        logits = predict_bags(model, training_bag, training_mask, validation, device)
        probability = ordinal_probabilities(logits)
        prediction = probability.argmax(axis=1)
        metrics = grading_metrics(labels[validation], prediction, probability)
        qwk = float(metrics["cancer_only_qwk"])
        epoch_rows.append(
            {
                "encoder": encoder,
                "architecture": architecture,
                "epoch": epoch,
                "loss": loss,
                **metrics,
            }
        )
        if np.isfinite(qwk) and qwk > best_qwk:
            best_qwk = qwk
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone() for name, value in model.state_dict().items()
            }
        print(
            f"PANDA {encoder} {architecture} head epoch {epoch}/{HEAD_MAX_EPOCHS}: "
            f"loss={loss:.6f} qwk={qwk:.6f}",
            flush=True,
        )

    # External data have not been scored. Refit from scratch on all PANDA slides for the selected epoch.
    refit_seed = SEED + 1000
    device = configure_training_device(refit_seed)
    if architecture == "mean_linear":
        final_center = np.asarray(slide_embedding, dtype=np.float64).mean(axis=0)
        final_scale = np.asarray(slide_embedding, dtype=np.float64).std(axis=0)
        final_scale = np.maximum(final_scale, 1e-6)
        final_model = build_mean_ordinal_linear(
            DIMENSION[encoder], final_center, final_scale
        ).to(device)
    else:
        final_model = build_ordinal_mil(DIMENSION[encoder]).to(device)
    final_optimizer = torch.optim.AdamW(
        final_model.parameters(), lr=HEAD_LEARNING_RATE, weight_decay=HEAD_WEIGHT_DECAY
    )
    final_loss = torch.nn.BCEWithLogitsLoss(pos_weight=threshold_pos_weight(labels, device))
    for epoch in range(1, best_epoch + 1):
        train_epoch(
            final_model,
            training_bag,
            training_mask,
            labels,
            all_indices,
            final_optimizer,
            final_loss,
            device,
            refit_seed + epoch,
        )
    if best_state is None:
        raise RuntimeError("PANDA development head selection produced no finite QWK")
    model.load_state_dict(best_state)
    validation_logits = predict_bags(model, training_bag, training_mask, validation, device)
    validation_probability = ordinal_probabilities(validation_logits)
    validation_prediction = validation_probability.argmax(axis=1)
    prediction_rows = rows.iloc[validation].copy()
    prediction_rows["truth_isup"] = labels[validation]
    prediction_rows["predicted_isup"] = validation_prediction
    for grade in range(6):
        prediction_rows[f"probability_isup_{grade}"] = validation_probability[:, grade]
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    token = architecture_output_token(architecture)
    pd.DataFrame(epoch_rows).to_csv(
        OUTPUTS / f"fm8_panda_{encoder}{token}_grading_head_epoch_diagnostics.csv",
        index=False,
        lineterminator="\n",
    )
    prediction_rows.to_csv(
        OUTPUTS / f"fm8_panda_{encoder}{token}_grading_development_predictions.csv",
        index=False,
        lineterminator="\n",
    )
    pd.DataFrame(
        confusion_rows(
            labels[validation],
            validation_prediction,
            "PANDA_PUBLIC_DEVELOPMENT_SPLIT",
            encoder,
            "panda_isup",
        )
    ).to_csv(
        OUTPUTS / f"fm8_panda_{encoder}{token}_grading_development_confusion.csv",
        index=False,
        lineterminator="\n",
    )
    checkpoint_path = head_checkpoint_path(encoder, architecture)
    torch.save(
        {
            "state_dict": final_model.state_dict(),
            "encoder": encoder,
            "architecture": architecture,
            "dimension": DIMENSION[encoder],
            "hidden": HEAD_HIDDEN,
            "selected_epoch": best_epoch,
            "seed": SEED,
            "refit_seed": refit_seed,
        },
        checkpoint_path,
    )
    config = {
        "protocol": "fm8-grading-criterion-qualification-protocol",
        "encoder": encoder,
        "architecture": architecture,
        "architecture_detail": (
            "frozen encoder; LayerNorm; 256-unit gated attention; five all-threshold logits"
            if architecture == "gated_mil"
            else "frozen encoder; mean pooling; PANDA-fit feature standardization; linear five all-threshold logits"
        ),
        "seed": SEED,
        "refit_seed": refit_seed,
        "batch_size_slides": HEAD_BATCH_SIZE,
        "learning_rate": HEAD_LEARNING_RATE,
        "weight_decay": HEAD_WEIGHT_DECAY,
        "maximum_epochs": HEAD_MAX_EPOCHS,
        "selected_epoch": best_epoch,
        "selection_metric": "PANDA development cancer-only QWK",
        "panda_slides": len(rows),
        "development_slides": len(development),
        "validation_slides": len(validation),
        "external_results_seen_for_selection": False,
        "checkpoint_state_sha256": state_dict_sha256(final_model.state_dict()),
        "tile_bag_sha256": sha256_file(bag_path),
        "tile_bag_mask_sha256": sha256_file(mask_path),
        "slide_embedding_sha256": sha256_file(slide_embedding_path),
        "row_manifest_sha256": sha256_file(row_path),
        "runtime_seconds": round(time.time() - started, 6),
        "volatile_fields": ["runtime_seconds"],
    }
    (OUTPUTS / f"fm8_panda_{encoder}{token}_grading_head_run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_locked_head(
    encoder: str, architecture: str, device: object
) -> tuple[object, dict[str, object]]:
    import torch

    path = head_checkpoint_path(encoder, architecture)
    if not path.is_file():
        raise FileNotFoundError(path)
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if (
        checkpoint["encoder"] != encoder
        or checkpoint.get("architecture", "gated_mil") != architecture
        or int(checkpoint["dimension"]) != DIMENSION[encoder]
    ):
        raise RuntimeError("grading head identity mismatch")
    model = (
        build_ordinal_mil(DIMENSION[encoder])
        if architecture == "gated_mil"
        else build_mean_ordinal_linear(DIMENSION[encoder])
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    return model.eval(), checkpoint


def evaluate_sicap_grading(encoder: str, architecture: str) -> None:
    manifest = sicap_test_manifest()
    embedding_path = ARTIFACTS / f"fm8_sicap_{encoder}_patch_embeddings.npy"
    if not embedding_path.is_file():
        raise FileNotFoundError(embedding_path)
    embedding = np.load(embedding_path, mmap_mode="r", allow_pickle=False)
    slide_groups = list(manifest.groupby("slide_id", sort=True))
    bags = np.zeros((len(slide_groups), MAX_TILES, DIMENSION[encoder]), dtype=np.float32)
    masks = np.zeros((len(slide_groups), MAX_TILES), dtype=bool)
    slide_rows: list[dict[str, object]] = []
    for index, (slide_id, group) in enumerate(slide_groups):
        positions = group.embedding_row.to_numpy(int)
        if len(positions) > MAX_TILES:
            rng = np.random.default_rng(
                int.from_bytes(hashlib.sha256(f"{SEED}:{slide_id}".encode()).digest()[:8], "little")
            )
            positions = positions[rng.permutation(len(positions))[:MAX_TILES]]
        bags[index, : len(positions)] = embedding[positions]
        masks[index, : len(positions)] = True
        source = group.iloc[0]
        slide_rows.append(
            {
                "slide_id": slide_id,
                "patient_id": str(source.patient_id),
                "truth_isup": int(source.isup_grade),
                "gleason_primary": int(source.Gleason_primary),
                "gleason_secondary": int(source.Gleason_secondary),
                "available_patches": len(group),
                "used_patches": len(positions),
            }
        )
    rows = pd.DataFrame(slide_rows)
    device = configure_training_device(SEED)
    model, checkpoint = load_locked_head(encoder, architecture, device)
    evaluation_bag, evaluation_mask = (
        mean_linear_inputs(np.sum(bags, axis=1) / np.maximum(masks.sum(axis=1, keepdims=True), 1))
        if architecture == "mean_linear"
        else (bags, masks)
    )
    logits = predict_bags(
        model, evaluation_bag, evaluation_mask, np.arange(len(rows)), device
    )
    probability = ordinal_probabilities(logits)
    prediction = probability.argmax(axis=1)
    rows["predicted_isup"] = prediction
    for grade in range(6):
        rows[f"probability_isup_{grade}"] = probability[:, grade]
    metrics = grading_metrics(rows.truth_isup.to_numpy(int), prediction, probability)

    rng = np.random.default_rng(SEED + (0 if encoder == "conch" else 1))
    patients = rows.patient_id.unique()
    bootstrap: list[float] = []
    undefined = 0
    for _ in range(BOOTSTRAPS):
        sampled = rng.choice(patients, size=len(patients), replace=True)
        positions = np.concatenate([np.flatnonzero(rows.patient_id.to_numpy() == patient) for patient in sampled])
        truth = rows.truth_isup.to_numpy(int)[positions]
        pred = prediction[positions]
        cancer = truth > 0
        if cancer.sum() < 2 or len(np.unique(truth[cancer])) < 2 or len(np.unique(pred[cancer])) < 2:
            undefined += 1
            continue
        bootstrap.append(float(cohen_kappa_score(truth[cancer], pred[cancer], weights="quadratic")))
    metrics.update(
        {
            "cohort": "SICAPV2_OFFICIAL_TEST_PRIOR_OPEN_QUALIFICATION",
            "encoder": encoder,
            "architecture": architecture,
            "patients": int(rows.patient_id.nunique()),
            "slides": len(rows),
            "bootstrap_replicates": BOOTSTRAPS,
            "bootstrap_defined": len(bootstrap),
            "bootstrap_undefined": undefined,
            "cancer_only_qwk_ci_low": float(np.quantile(bootstrap, 0.025)) if bootstrap else float("nan"),
            "cancer_only_qwk_ci_high": float(np.quantile(bootstrap, 0.975)) if bootstrap else float("nan"),
            "head_selected_epoch": int(checkpoint["selected_epoch"]),
            "target_cohort_tuning": "NONE",
        }
    )
    token = architecture_output_token(architecture)
    rows.to_csv(
        OUTPUTS / f"fm8_sicap_{encoder}{token}_grading_predictions.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame([metrics]).to_csv(
        OUTPUTS / f"fm8_sicap_{encoder}{token}_grading_metrics.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame(
        confusion_rows(
            rows.truth_isup.to_numpy(int),
            prediction,
            "SICAPV2_OFFICIAL_TEST_PRIOR_OPEN_QUALIFICATION",
            encoder,
            "derived_slide_isup",
        )
    ).to_csv(
        OUTPUTS / f"fm8_sicap_{encoder}{token}_grading_confusion.csv",
        index=False,
        lineterminator="\n",
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)


def par_labels() -> pd.DataFrame:
    frame = pd.read_csv(PAR_LABELS, sep="\t", dtype={"slide_id": str})
    required = {
        "slide_id",
        "gleason_r1",
        "gleason_r2",
        "gleason_r3",
        "isup_1",
        "isup_r2",
        "isup_r3",
        "num_raters",
    }
    if len(frame) != 339 or not required.issubset(frame.columns) or frame.slide_id.duplicated().any():
        raise RuntimeError("PAR label identity/schema changed")
    frame = frame.copy()
    frame["slide_id"] = frame.slide_id.str.upper()
    frame["patient_id"] = frame.slide_id.str.extract(r"^C(\d{3})")[0].map(lambda value: f"C{value}")
    frame["file_name"] = frame.slide_id.str.lower() + "_hamamatsu.ndpi"
    if frame.patient_id.nunique() != 185 or frame.patient_id.isna().any():
        raise RuntimeError("PAR patient identity contract changed")
    return frame.sort_values("slide_id").reset_index(drop=True)


def par_preparation_cache(slide_id: str) -> Path:
    return ARTIFACTS / "par_preparation_cache" / f"{slide_id}.npz"


def par_embedding_cache(encoder: str, slide_id: str) -> Path:
    return ARTIFACTS / "par_embedding_cache" / encoder / f"{slide_id}.npz"


def par_preparation_valid(slide_id: str) -> bool:
    path = par_preparation_cache(slide_id)
    if not path.is_file():
        return False
    try:
        with np.load(path, allow_pickle=False) as cached:
            return bool(
                str(cached["slide_id"].item()) == slide_id
                and str(cached["sampling_status"].item()) == "PASS"
                and 0 < len(cached["tile_rank"]) <= MAX_TILES
                and np.array_equal(cached["tile_rank"], np.arange(len(cached["tile_rank"])))
            )
    except (OSError, KeyError, ValueError):
        return False


def prepare_par(shard_index: int, shard_count: int, available_only: bool, limit: int | None) -> None:
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    frame = par_labels()
    selected = frame.iloc[[index % shard_count == shard_index for index in range(len(frame))]]
    if available_only:
        selected = selected[selected.file_name.map(lambda name: (PAR_WSI / name).is_file())]
    elif not selected.file_name.map(lambda name: (PAR_WSI / name).is_file()).all():
        raise RuntimeError("PAR primary-scanner payload is incomplete")
    if limit is not None:
        selected = selected.head(limit)
    complete = 0
    reused = 0
    started = time.time()
    for row in selected.itertuples(index=False):
        slide_id = str(row.slide_id)
        if par_preparation_valid(slide_id):
            complete += 1
            reused += 1
            continue
        wsi = PAR_WSI / str(row.file_name)
        with tifffile.TiffFile(wsi) as tif:
            mpp = float(FM6_RUNNER.native_mpp(tif.series[0].levels[0].pages[0]))
        # Coordinate selection receives only RGB WSI and a source identity token.
        candidates, audit = FM6_RUNNER.slide_candidates(wsi, slide_id, mpp)
        if audit["sampling_status"] != "PASS":
            raise RuntimeError(f"PAR insufficient tissue: {slide_id}")
        arrays: dict[str, object] = {
            "slide_id": np.asarray(slide_id),
            "patient_id": np.asarray(str(row.patient_id)),
            "file_name": np.asarray(str(row.file_name)),
            "mpp": np.asarray(mpp, dtype=np.float64),
            "sampling_status": np.asarray(str(audit["sampling_status"])),
            "isup_r1": np.asarray(float(row.isup_1), dtype=np.float32),
            "isup_r2": np.asarray(float(row.isup_r2), dtype=np.float32),
            "isup_r3": np.asarray(float(row.isup_r3), dtype=np.float32),
            "gleason_r1": np.asarray(str(row.gleason_r1)),
            "gleason_r2": np.asarray(str(row.gleason_r2)),
            "gleason_r3": np.asarray(str(row.gleason_r3)),
        }
        for key in (
            "tile_rank",
            "level0_x0",
            "level0_y0",
            "level0_x1",
            "level0_y1",
            "thumbnail_tissue_fraction",
        ):
            dtype = np.float32 if key == "thumbnail_tissue_fraction" else np.int32
            arrays[key] = np.asarray([candidate[key] for candidate in candidates], dtype=dtype)
        atomic_npz(par_preparation_cache(slide_id), **arrays)
        complete += 1
        if complete % 5 == 0 or complete == len(selected):
            print(
                f"PAR prepare shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(selected)} available slides (reused={reused})",
                flush=True,
            )
    run = {
        "stage": "prepare-par",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "available_only": available_only,
        "selected_slides": len(selected),
        "completed_slides": complete,
        "reused_slides": reused,
        "runtime_seconds": round(time.time() - started, 6),
        "confirmatory_ready": PAR_LOCAL_AUDIT.is_file() and complete == len(frame),
    }
    path = ARTIFACTS / "run_records" / f"prepare_par_{shard_index:03d}_of_{shard_count:03d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def par_cache_rows(slide_id: str) -> pd.DataFrame:
    if not par_preparation_valid(slide_id):
        raise RuntimeError(f"missing PAR preparation cache: {slide_id}")
    with np.load(par_preparation_cache(slide_id), allow_pickle=False) as cached:
        n = len(cached["tile_rank"])
        rows = pd.DataFrame(
            {
                "tile_id": [f"{slide_id}:{index:03d}" for index in range(n)],
                "slide_id": slide_id,
                "patient_id": str(cached["patient_id"].item()),
                "file_name": str(cached["file_name"].item()),
                "tile_rank": cached["tile_rank"],
                "level0_x0": cached["level0_x0"],
                "level0_y0": cached["level0_y0"],
                "level0_x1": cached["level0_x1"],
                "level0_y1": cached["level0_y1"],
            }
        )
    return rows


def openslide_version() -> str:
    import openslide

    return f"python={openslide.__version__};library={openslide.__library_version__}"


def load_par_slide(slide_id: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    import openslide

    rows = par_cache_rows(slide_id)
    crops: list[np.ndarray] = []
    hashes: list[str] = []
    path = PAR_WSI / str(rows.file_name.iloc[0])
    slide = openslide.OpenSlide(str(path))
    try:
        with tifffile.TiffFile(path) as tif:
            expected_dimensions = (
                int(tif.series[0].levels[0].shape[1]),
                int(tif.series[0].levels[0].shape[0]),
            )
        if slide.dimensions != expected_dimensions:
            raise RuntimeError(
                f"PAR OpenSlide/tifffile dimension mismatch: {slide.dimensions} != {expected_dimensions}"
            )
        for row in rows.itertuples(index=False):
            width = int(row.level0_x1 - row.level0_x0)
            height = int(row.level0_y1 - row.level0_y0)
            if (
                width <= 0
                or height <= 0
                or row.level0_x0 < 0
                or row.level0_y0 < 0
                or row.level0_x1 > slide.dimensions[0]
                or row.level0_y1 > slide.dimensions[1]
            ):
                raise RuntimeError(f"PAR crop outside level-0 bounds: {slide_id}/{row.tile_id}")
            rgb = np.asarray(
                slide.read_region(
                    (int(row.level0_x0), int(row.level0_y0)), 0, (width, height)
                ).convert("RGB"),
                dtype=np.uint8,
            )
            hashes.append(hashlib.sha256(rgb.tobytes(order="C")).hexdigest())
            canonical = Image.fromarray(rgb, mode="RGB").resize((448, 448), Image.Resampling.BICUBIC)
            crops.append(np.asarray(canonical, dtype=np.uint8))
    finally:
        slide.close()
    return rows, np.stack(crops), np.asarray(hashes, dtype="U64")


def par_embedding_valid(path: Path, slide_id: str, encoder: str, tile_ids: np.ndarray) -> bool:
    if not path.is_file():
        return False
    try:
        with np.load(path, allow_pickle=False) as cached:
            return bool(
                str(cached["slide_id"].item()) == slide_id
                and str(cached["encoder"].item()) == encoder
                and str(cached["decoder"].item()) == "openslide"
                and cached["embedding"].shape == (len(tile_ids), DIMENSION[encoder])
                and np.array_equal(cached["tile_id"].astype(str), tile_ids.astype(str))
                and np.isfinite(cached["embedding"]).all()
            )
    except (OSError, KeyError, ValueError):
        return False


def extract_par(encoder: str, shard_index: int, shard_count: int, available_only: bool) -> None:
    import torch

    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    frame = par_labels()
    selected = frame.iloc[[index % shard_count == shard_index for index in range(len(frame))]]
    selected = selected[selected.slide_id.map(par_preparation_valid)]
    if not available_only and len(selected) != len(frame.iloc[shard_index::shard_count]):
        raise RuntimeError("PAR preparation is incomplete")
    if selected.empty:
        raise RuntimeError("no prepared PAR slides selected")
    device = FM6_RUNNER.configure_device()
    model, _ = FM6_RUNNER.load_model(encoder, device)
    first_rows, first_crops, _ = load_par_slide(str(selected.slide_id.iloc[0]))
    tensor = FM6_RUNNER.transform_canonical_batch(encoder, first_crops[:4], device)
    with torch.inference_mode():
        first = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = FM6_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if not np.array_equal(first, second):
        raise RuntimeError(f"PAR {encoder} deterministic smoke failure")
    for complete, slide_id in enumerate(selected.slide_id.astype(str), 1):
        rows = par_cache_rows(slide_id)
        tile_ids = rows.tile_id.to_numpy(str)
        destination = par_embedding_cache(encoder, slide_id)
        if not par_embedding_valid(destination, slide_id, encoder, tile_ids):
            rows, crops, hashes = load_par_slide(slide_id)
            values: list[np.ndarray] = []
            for start in range(0, len(crops), BATCH_SIZE[encoder]):
                batch = FM6_RUNNER.transform_canonical_batch(
                    encoder, crops[start : start + BATCH_SIZE[encoder]], device
                )
                with torch.inference_mode():
                    values.append(
                        FM6_RUNNER.embed_batch(encoder, model, batch).detach().cpu().float().numpy()
                    )
            embedding = np.concatenate(values).astype(np.float32, copy=False)
            atomic_npz(
                destination,
                slide_id=np.asarray(slide_id),
                encoder=np.asarray(encoder),
                decoder=np.asarray("openslide"),
                openslide_version=np.asarray(openslide_version()),
                tile_id=rows.tile_id.to_numpy(str),
                decoded_rgb_sha256=hashes,
                embedding=embedding,
            )
        if complete % 5 == 0 or complete == len(selected):
            print(
                f"PAR {encoder} shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(selected)} prepared slides",
                flush=True,
            )
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()


def assemble_par_embeddings(encoder: str) -> None:
    frame = par_labels()
    if not PAR_LOCAL_AUDIT.is_file():
        raise RuntimeError("PAR local payload audit is incomplete")
    bags = np.zeros((len(frame), MAX_TILES, DIMENSION[encoder]), dtype=np.float32)
    masks = np.zeros((len(frame), MAX_TILES), dtype=bool)
    for index, row in enumerate(frame.itertuples(index=False)):
        slide_id = str(row.slide_id)
        source = par_cache_rows(slide_id)
        path = par_embedding_cache(encoder, slide_id)
        if not par_embedding_valid(path, slide_id, encoder, source.tile_id.to_numpy(str)):
            raise RuntimeError(f"missing PAR {encoder} embedding: {slide_id}")
        with np.load(path, allow_pickle=False) as cached:
            embedding = cached["embedding"]
            hashes = cached["decoded_rgb_sha256"].astype(str)
        bags[index, : len(embedding)] = embedding
        masks[index, : len(embedding)] = True
        other = "virchow" if encoder == "conch" else "conch"
        other_path = par_embedding_cache(other, slide_id)
        if par_embedding_valid(other_path, slide_id, other, source.tile_id.to_numpy(str)):
            with np.load(other_path, allow_pickle=False) as cached:
                if not np.array_equal(hashes, cached["decoded_rgb_sha256"].astype(str)):
                    raise RuntimeError(f"PAR paired crop mismatch: {slide_id}")
    bag_path = ARTIFACTS / f"fm8_par_{encoder}_tile_bags.npy"
    mask_path = ARTIFACTS / f"fm8_par_{encoder}_tile_bag_mask.npy"
    row_path = ARTIFACTS / f"fm8_par_{encoder}_slide_rows.csv"
    np.save(bag_path, bags, allow_pickle=False)
    np.save(mask_path, masks, allow_pickle=False)
    frame.to_csv(row_path, index=False, lineterminator="\n")
    pd.DataFrame(
        [
            {
                "cohort": "PAR_S_BIAD2323_HAMAMATSU",
                "encoder": encoder,
                "patients": int(frame.patient_id.nunique()),
                "slides": len(frame),
                "tile_bag_sha256": sha256_file(bag_path),
                "tile_bag_mask_sha256": sha256_file(mask_path),
                "row_manifest_sha256": sha256_file(row_path),
                "status": "PASS",
            }
        ]
    ).to_csv(OUTPUTS / f"fm8_par_{encoder}_embedding_technical_qc.csv", index=False, lineterminator="\n")


def patient_qwk_interval(rows: pd.DataFrame, truth_column: str, prediction_column: str, seed: int) -> tuple[float, float, int]:
    rng = np.random.default_rng(seed)
    patients = rows.patient_id.unique()
    values: list[float] = []
    undefined = 0
    for _ in range(BOOTSTRAPS):
        sampled = rng.choice(patients, size=len(patients), replace=True)
        positions = np.concatenate([np.flatnonzero(rows.patient_id.to_numpy() == patient) for patient in sampled])
        truth = rows[truth_column].to_numpy(int)[positions]
        pred = rows[prediction_column].to_numpy(int)[positions]
        cancer = truth > 0
        if cancer.sum() < 2 or len(np.unique(truth[cancer])) < 2 or len(np.unique(pred[cancer])) < 2:
            undefined += 1
            continue
        values.append(float(cohen_kappa_score(truth[cancer], pred[cancer], weights="quadratic")))
    if not values:
        return float("nan"), float("nan"), undefined
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975)), undefined


def evaluate_par_grading(encoder: str, architecture: str) -> None:
    bag_path = ARTIFACTS / f"fm8_par_{encoder}_tile_bags.npy"
    mask_path = ARTIFACTS / f"fm8_par_{encoder}_tile_bag_mask.npy"
    row_path = ARTIFACTS / f"fm8_par_{encoder}_slide_rows.csv"
    bag = np.load(bag_path, mmap_mode="r", allow_pickle=False)
    masks = np.load(mask_path, mmap_mode="r", allow_pickle=False)
    rows = pd.read_csv(row_path, dtype={"slide_id": str, "patient_id": str})
    device = configure_training_device(SEED)
    model, checkpoint = load_locked_head(encoder, architecture, device)
    evaluation_bag, evaluation_mask = (
        mean_linear_inputs(
            np.sum(bag, axis=1) / np.maximum(masks.sum(axis=1, keepdims=True), 1)
        )
        if architecture == "mean_linear"
        else (bag, masks)
    )
    logits = predict_bags(
        model, evaluation_bag, evaluation_mask, np.arange(len(rows)), device
    )
    probability = ordinal_probabilities(logits)
    rows["predicted_isup"] = probability.argmax(axis=1)
    for grade in range(6):
        rows[f"probability_isup_{grade}"] = probability[:, grade]
    metric_rows: list[dict[str, object]] = []
    all_confusion_rows: list[dict[str, object]] = []
    adequate: list[bool] = []
    above_chance: list[bool] = []
    for reader, truth_column in (("reader_1", "isup_1"), ("reader_2", "isup_r2"), ("reader_3_uropathologist", "isup_r3")):
        selected = rows.dropna(subset=[truth_column]).copy()
        truth = selected[truth_column].to_numpy(int)
        pred = selected.predicted_isup.to_numpy(int)
        selected_probability = probability[selected.index.to_numpy(int)]
        metrics = grading_metrics(truth, pred, selected_probability)
        low, high, undefined = patient_qwk_interval(
            selected, truth_column, "predicted_isup", SEED + len(metric_rows)
        )
        is_above = bool(np.isfinite(low) and low > 0)
        is_adequate = bool(
            float(metrics["cancer_only_qwk"]) >= 0.60
            and float(metrics["cancer_only_within_one"]) >= 0.90
            and float(metrics["cancer_only_severe_error"]) <= 0.05
        )
        metric_rows.append(
            {
                "cohort": "PAR_S_BIAD2323_HAMAMATSU_CONFIRMATORY",
                "encoder": encoder,
                "architecture": architecture,
                "reader": reader,
                "patients": int(selected.patient_id.nunique()),
                "slides": len(selected),
                **metrics,
                "cancer_only_qwk_ci_low": low,
                "cancer_only_qwk_ci_high": high,
                "bootstrap_undefined": undefined,
                "above_chance": is_above,
                "adequate_point_metrics": is_adequate,
                "head_selected_epoch": int(checkpoint["selected_epoch"]),
                "target_cohort_tuning": "NONE",
            }
        )
        all_confusion_rows.extend(
            confusion_rows(
                truth,
                pred,
                "PAR_S_BIAD2323_HAMAMATSU_CONFIRMATORY",
                encoder,
                reader,
            )
        )
        if reader in {"reader_1", "reader_2"}:
            adequate.append(is_adequate)
            above_chance.append(is_above)
    token = architecture_output_token(architecture)
    rows.to_csv(OUTPUTS / f"fm8_par_{encoder}{token}_grading_predictions.csv", index=False, lineterminator="\n")
    pd.DataFrame(metric_rows).to_csv(
        OUTPUTS / f"fm8_par_{encoder}{token}_grading_metrics.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame(all_confusion_rows).to_csv(
        OUTPUTS / f"fm8_par_{encoder}{token}_grading_confusion.csv", index=False, lineterminator="\n"
    )
    decision = {
        "encoder": encoder,
        "architecture": architecture,
        "above_chance_co_primary_readers": bool(all(above_chance)),
        "adequate_for_functional_testing": bool(all(above_chance) and all(adequate)),
        "residual_entry_allowed": False,
    }
    gate_path = (
        OUTPUTS / f"fm8_par_{encoder}_grading_accuracy_gate.json"
        if architecture == "gated_mil"
        else OUTPUTS / f"fm8_par_{encoder}_mean_linear_grading_accuracy_check.json"
    )
    gate_path.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, sort_keys=True), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="stage", required=True)
    prepare = sub.add_parser("prepare-panda")
    prepare.add_argument("--shard-index", type=int, default=0)
    prepare.add_argument("--shard-count", type=int, default=1)
    prepare.add_argument("--limit", type=int)
    sub.add_parser("assemble-panda-manifest")
    extract = sub.add_parser("extract-panda")
    extract.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    extract.add_argument("--shard-index", type=int, default=0)
    extract.add_argument("--shard-count", type=int, default=1)
    extract.add_argument("--limit", type=int)
    extract.add_argument("--smoke-only", action="store_true")
    paired_extract = sub.add_parser("extract-panda-paired")
    paired_extract.add_argument("--shard-index", type=int, default=0)
    paired_extract.add_argument("--shard-count", type=int, default=1)
    paired_extract.add_argument("--limit", type=int)
    assemble = sub.add_parser("assemble-panda-embeddings")
    assemble.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    sicap = sub.add_parser("extract-sicap")
    sicap.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    sicap.add_argument("--smoke-only", action="store_true")
    sub.add_parser("audit-sicap-pairing")
    head = sub.add_parser("train-grading-head")
    head.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    head.add_argument("--architecture", choices=HEAD_ARCHITECTURES, default="gated_mil")
    evaluate_sicap = sub.add_parser("evaluate-sicap-grading")
    evaluate_sicap.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    evaluate_sicap.add_argument("--architecture", choices=HEAD_ARCHITECTURES, default="gated_mil")
    prepare_par_parser = sub.add_parser("prepare-par")
    prepare_par_parser.add_argument("--shard-index", type=int, default=0)
    prepare_par_parser.add_argument("--shard-count", type=int, default=1)
    prepare_par_parser.add_argument("--available-only", action="store_true")
    prepare_par_parser.add_argument("--limit", type=int)
    extract_par_parser = sub.add_parser("extract-par")
    extract_par_parser.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    extract_par_parser.add_argument("--shard-index", type=int, default=0)
    extract_par_parser.add_argument("--shard-count", type=int, default=1)
    extract_par_parser.add_argument("--available-only", action="store_true")
    assemble_par_parser = sub.add_parser("assemble-par-embeddings")
    assemble_par_parser.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    evaluate_par_parser = sub.add_parser("evaluate-par-grading")
    evaluate_par_parser.add_argument("--encoder", choices=sorted(DIMENSION), required=True)
    evaluate_par_parser.add_argument("--architecture", choices=HEAD_ARCHITECTURES, default="gated_mil")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "prepare-panda":
        prepare_panda(args.shard_index, args.shard_count, args.limit)
    elif args.stage == "assemble-panda-manifest":
        assemble_panda_manifest()
    elif args.stage == "extract-panda":
        extract_panda(
            args.encoder, args.shard_index, args.shard_count, args.limit, args.smoke_only
        )
    elif args.stage == "extract-panda-paired":
        extract_panda_paired(args.shard_index, args.shard_count, args.limit)
    elif args.stage == "assemble-panda-embeddings":
        assemble_panda_embeddings(args.encoder)
    elif args.stage == "extract-sicap":
        extract_sicap(args.encoder, args.smoke_only)
    elif args.stage == "audit-sicap-pairing":
        audit_sicap_pairing()
    elif args.stage == "train-grading-head":
        train_grading_head(args.encoder, args.architecture)
    elif args.stage == "evaluate-sicap-grading":
        evaluate_sicap_grading(args.encoder, args.architecture)
    elif args.stage == "prepare-par":
        prepare_par(args.shard_index, args.shard_count, args.available_only, args.limit)
    elif args.stage == "extract-par":
        extract_par(args.encoder, args.shard_index, args.shard_count, args.available_only)
    elif args.stage == "assemble-par-embeddings":
        assemble_par_embeddings(args.encoder)
    elif args.stage == "evaluate-par-grading":
        evaluate_par_grading(args.encoder, args.architecture)
    else:
        raise AssertionError(args.stage)


if __name__ == "__main__":
    main()
