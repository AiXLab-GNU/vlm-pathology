#!/usr/bin/env python3
"""Prepare and extract paired TCGA-PRAD whole-tissue FM6 pilot embeddings.

The tile manifest is outcome-blind. CONCH and Virchow consume the exact same decoded
level-0 RGB crop boundaries. Generated arrays/caches remain under resources/artifacts.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from PIL import Image


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm6_internal_development_pilot"
OUTPUTS = MILESTONE / "outputs"
LOCAL = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"
SOURCE = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/tcga_prad_current_gdc_bcr"
SLIDES = ROOT / "resources/data/shared/opendataset/TCGA-PRAD/slides"
HF_ROOT = Path.home() / ".cache/huggingface-jhkim/hub"
CONCH_CODE = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/CONCH"

SEED = 260816
FOV_UM = 394.24
MAX_TILES = 64
MIN_TILES = 16
DIMENSION = {"conch": 512, "virchow": 2560}
BATCH_SIZE = {"conch": 64, "virchow": 64}


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def stable_rng(token: str) -> np.random.Generator:
    raw = hashlib.sha256(f"{SEED}:{token}".encode()).digest()[:8]
    return np.random.default_rng(int.from_bytes(raw, "little"))


def native_mpp(page: tifffile.TiffPage) -> float:
    description = str(page.tags.get("ImageDescription").value) if page.tags.get("ImageDescription") else ""
    match = re.search(r"MPP\s*=\s*([\d.]+)", description, flags=re.I)
    if match:
        return float(match.group(1))
    xres, unit = page.tags.get("XResolution"), page.tags.get("ResolutionUnit")
    if xres and unit:
        numerator, denominator = xres.value
        pixels_per_unit = numerator / denominator
        if pixels_per_unit > 0:
            return (10000.0 if int(unit.value) == 3 else 25400.0) / pixels_per_unit
    match = re.search(r"AppMag\s*=\s*([\d.]+)", description, flags=re.I)
    if match:
        return 10.0 / float(match.group(1))
    raise RuntimeError("MPP unavailable")


def rgb3(value: np.ndarray) -> np.ndarray:
    if value.ndim == 2:
        return np.repeat(value[..., None], 3, axis=2).astype(np.uint8)
    if value.ndim != 3 or value.shape[2] < 3:
        raise RuntimeError(f"unexpected RGB shape {value.shape}")
    return value[..., :3].astype(np.uint8, copy=False)


def thumbnail_tissue_mask(rgb: np.ndarray) -> np.ndarray:
    value = rgb.astype(np.float32)
    maximum, minimum = value.max(axis=2), value.min(axis=2)
    saturation = (maximum - minimum) / np.maximum(maximum, 1.0)
    gray = 0.299 * value[..., 0] + 0.587 * value[..., 1] + 0.114 * value[..., 2]
    return ((gray < 225.0) & ((saturation > 0.025) | (gray < 180.0))).astype(np.uint8)


def integral_fraction(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> float:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(mask.shape[1], x1), min(mask.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(mask[y0:y1, x0:x1].mean())


def slide_candidates(path: Path, file_id: str, mpp_expected: float) -> tuple[list[dict[str, object]], dict[str, object]]:
    with tifffile.TiffFile(path) as tif:
        levels = tif.series[0].levels
        base = levels[0].pages[0]
        mpp_read = native_mpp(base)
        if abs(mpp_read - mpp_expected) > 0.01:
            raise RuntimeError(f"MPP discrepancy {mpp_read} vs {mpp_expected}")
        crop_px = int(round(FOV_UM / mpp_read))
        if crop_px < 128 or crop_px >= min(base.imagewidth, base.imagelength):
            raise RuntimeError(f"invalid physical crop {crop_px}px")
        thumb_page = levels[-1].pages[0]
        thumb = rgb3(thumb_page.asarray())
        mask = thumbnail_tissue_mask(thumb)
        scale_x = base.imagewidth / thumb.shape[1]
        scale_y = base.imagelength / thumb.shape[0]
        half_x = max(1, int(round(crop_px / scale_x / 2)))
        half_y = max(1, int(round(crop_px / scale_y / 2)))
        step_x = max(2, half_x)
        step_y = max(2, half_y)
        choices: list[tuple[int, int, float]] = []
        for cy in range(half_y, thumb.shape[0] - half_y, step_y):
            for cx in range(half_x, thumb.shape[1] - half_x, step_x):
                fraction = integral_fraction(mask, cx - half_x, cy - half_y, cx + half_x, cy + half_y)
                if fraction >= 0.35:
                    choices.append((cx, cy, fraction))
        if len(choices) < MIN_TILES:
            choices = []
            for cy in range(half_y, thumb.shape[0] - half_y, max(2, step_y // 2)):
                for cx in range(half_x, thumb.shape[1] - half_x, max(2, step_x // 2)):
                    fraction = integral_fraction(mask, cx - half_x, cy - half_y, cx + half_x, cy + half_y)
                    if fraction >= 0.15:
                        choices.append((cx, cy, fraction))
        rng = stable_rng(file_id)
        order = rng.permutation(len(choices)) if choices else np.array([], dtype=int)
        selected = [choices[index] for index in order[:MAX_TILES]]
        records: list[dict[str, object]] = []
        for rank, (cx, cy, fraction) in enumerate(selected):
            center_x = int(round((cx + 0.5) * scale_x))
            center_y = int(round((cy + 0.5) * scale_y))
            x0 = min(max(0, center_x - crop_px // 2), base.imagewidth - crop_px)
            y0 = min(max(0, center_y - crop_px // 2), base.imagelength - crop_px)
            records.append({
                "tile_rank": rank,
                "level0_x0": x0,
                "level0_y0": y0,
                "level0_x1": x0 + crop_px,
                "level0_y1": y0 + crop_px,
                "physical_fov_um": FOV_UM,
                "mpp": mpp_read,
                "thumbnail_tissue_fraction": fraction,
            })
        audit = {
            "file_id": file_id,
            "width_px": int(base.imagewidth),
            "height_px": int(base.imagelength),
            "mpp": mpp_read,
            "crop_px": crop_px,
            "thumbnail_width": int(thumb.shape[1]),
            "thumbnail_height": int(thumb.shape[0]),
            "candidate_count": len(choices),
            "selected_count": len(selected),
            "sampling_status": "PASS" if len(selected) >= MIN_TILES else "INSUFFICIENT_TISSUE",
        }
        return records, audit


def prepare() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    slides = pd.read_csv(SOURCE / "development_slides.csv")
    qc = pd.read_csv(SOURCE / "development_wsi_header_qc.csv")
    folds = pd.read_csv(SOURCE / "development_outer_folds.csv")
    subjects = pd.read_csv(SOURCE / "development_subjects.csv")
    if len(slides) != 437 or subjects.case_id.nunique() != 392 or int(subjects.bcr_event.sum()) != 80:
        raise RuntimeError("locked FM6 source universe changed")
    frame = slides.merge(qc[["file_id", "header_status", "thumbnail_decode_status", "mpp"]], on="file_id", validate="one_to_one")
    frame = frame.merge(folds[["case_id", "outer_fold"]], on="case_id", validate="many_to_one")
    if not (frame.local_complete.all() and frame.header_status.eq("PASS").all() and frame.thumbnail_decode_status.eq("PASS").all()):
        raise RuntimeError("one or more locked slides failed source/QC gates")
    rows: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    embedding_row = 0
    for number, source_row in enumerate(frame.sort_values(["case_id", "file_id"]).itertuples(index=False), 1):
        path = ROOT / source_row.local_relative_path
        candidates, audit = slide_candidates(path, source_row.file_id, float(source_row.mpp))
        audit.update({"case_id": source_row.case_id, "file_name": source_row.file_name})
        audits.append(audit)
        for candidate in candidates:
            tile_id = f"{source_row.file_id}:{int(candidate['tile_rank']):03d}"
            rows.append({
                "embedding_row": embedding_row,
                "tile_id": tile_id,
                "case_id": source_row.case_id,
                "file_id": source_row.file_id,
                "file_name": source_row.file_name,
                "local_relative_path": source_row.local_relative_path,
                "outer_fold": int(source_row.outer_fold),
                **candidate,
            })
            embedding_row += 1
        if number % 20 == 0 or number == len(frame):
            print(f"prepare {number}/{len(frame)} slides; {embedding_row} tiles", flush=True)
    manifest = pd.DataFrame(rows)
    audit_frame = pd.DataFrame(audits)
    if manifest.tile_id.duplicated().any() or not manifest.embedding_row.equals(pd.Series(np.arange(len(manifest)))):
        raise RuntimeError("tile identity/order failure")
    included_files = set(audit_frame.loc[audit_frame.sampling_status.eq("PASS"), "file_id"])
    manifest = manifest[manifest.file_id.isin(included_files)].copy().reset_index(drop=True)
    manifest["embedding_row"] = np.arange(len(manifest), dtype=int)
    manifest.to_csv(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv", index=False, lineterminator="\n")
    audit_frame.to_csv(OUTPUTS / "fm6_tcga_tile_sampling_qc.csv", index=False, lineterminator="\n")
    config = {
        "protocol": "fm6-tcga-whole-tissue-internal-development-pilot-protocol",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "physical_fov_um": FOV_UM,
        "max_tiles_per_slide": MAX_TILES,
        "min_tiles_per_slide": MIN_TILES,
        "source_subjects": len(subjects),
        "source_events": int(subjects.bcr_event.sum()),
        "source_slides": len(slides),
        "eligible_sampled_slides": int(manifest.file_id.nunique()),
        "eligible_tiles": len(manifest),
        "manifest_sha256": sha256_file(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv"),
        "claim_ceiling": "internal whole-tissue development evidence; not tumor-specific H1/H2",
    }
    (OUTPUTS / "fm6_tcga_tile_manifest_run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print(json.dumps(config, indent=2), flush=True)


def model_spec(encoder: str) -> dict[str, object]:
    if encoder == "conch":
        return {
            "model_id": "conch_ViT-B-16 / MahmoodLab/conch",
            "revision": "f9ca9f877171a28ade80228fb195ac5d79003357",
            "weights": HF_ROOT / "models--MahmoodLab--conch/snapshots/f9ca9f877171a28ade80228fb195ac5d79003357/pytorch_model.bin",
            "dimension": 512,
        }
    snapshot = HF_ROOT / "models--paige-ai--Virchow/snapshots/19eebc84ae33e79f1b2d866e6ff90ae50e522f9a"
    return {
        "model_id": "paige-ai/Virchow",
        "revision": "19eebc84ae33e79f1b2d866e6ff90ae50e522f9a",
        "weights": snapshot / "model.safetensors",
        "config": snapshot / "config.json",
        "dimension": 2560,
    }


def load_model(encoder: str, device: object) -> tuple[object, object]:
    import torch

    spec = model_spec(encoder)
    if not Path(spec["weights"]).exists():
        raise FileNotFoundError(spec["weights"])
    if encoder == "conch":
        if str(CONCH_CODE) not in sys.path:
            sys.path.insert(0, str(CONCH_CODE))
        from conch.open_clip_custom import create_model_from_pretrained

        model, transform = create_model_from_pretrained(
            "conch_ViT-B-16", checkpoint_path=str(spec["weights"]), device=device
        )
    else:
        import timm
        from timm.layers import SwiGLUPacked

        config = json.loads(Path(spec["config"]).read_text())
        model = timm.create_model(
            config["architecture"], pretrained=False,
            pretrained_cfg=config["pretrained_cfg"], checkpoint_path=str(spec["weights"]),
            mlp_layer=SwiGLUPacked, act_layer=torch.nn.SiLU, **config["model_args"],
        ).to(device)
        data_config = timm.data.resolve_data_config(model.pretrained_cfg, model=model)
        transform = timm.data.create_transform(**data_config, is_training=False)
    return model.eval(), transform


def embed_batch(encoder: str, model: object, batch: object) -> object:
    import torch

    if encoder == "conch":
        return model.encode_image(batch, proj_contrast=False, normalize=False)
    tokens = model.forward_features(batch)
    return torch.cat([tokens[:, 0], tokens[:, 1:].mean(dim=1)], dim=-1)


def read_tiled_rgb_region(page: tifffile.TiffPage, x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    if not page.is_tiled or page.planarconfig != 1 or page.samplesperpixel < 3:
        raise RuntimeError("requires contiguous tiled RGB level-0 H&E")
    tile_width, tile_height = int(page.tilewidth), int(page.tilelength)
    tiles_across = math.ceil(page.imagewidth / tile_width)
    crop = np.empty((y1 - y0, x1 - x0, 3), dtype=np.uint8)
    coverage = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    handle = page.parent.filehandle
    for tile_y in range(y0 // tile_height, (y1 - 1) // tile_height + 1):
        for tile_x in range(x0 // tile_width, (x1 - 1) // tile_width + 1):
            tile_index = tile_y * tiles_across + tile_x
            handle.seek(page.dataoffsets[tile_index])
            encoded = handle.read(page.databytecounts[tile_index])
            decoded = page.decode(encoded, tile_index, jpegtables=page.jpegtables)[0]
            if decoded is None:
                raise RuntimeError(f"failed TIFF tile {tile_index}")
            tile = decoded[0] if decoded.ndim == 4 else decoded
            global_x0, global_y0 = tile_x * tile_width, tile_y * tile_height
            ox0, oy0 = max(x0, global_x0), max(y0, global_y0)
            ox1, oy1 = min(x1, global_x0 + tile.shape[1]), min(y1, global_y0 + tile.shape[0])
            cy, cx = slice(oy0 - y0, oy1 - y0), slice(ox0 - x0, ox1 - x0)
            ty, tx = slice(oy0 - global_y0, oy1 - global_y0), slice(ox0 - global_x0, ox1 - global_x0)
            crop[cy, cx] = tile[ty, tx, :3]
            coverage[cy, cx] = True
    if not coverage.all():
        raise RuntimeError("crop not fully covered")
    return crop


def configure_device() -> object:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device required; run outside sandbox")
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch.device("cuda:0")


def transform_canonical_batch(encoder: str, crops: np.ndarray, device: object) -> object:
    import torch

    values = np.asarray(crops, dtype=np.uint8)
    if encoder == "virchow":
        def resize(crop: np.ndarray) -> np.ndarray:
            return np.asarray(
                Image.fromarray(crop, mode="RGB").resize((224, 224), Image.Resampling.BICUBIC),
                dtype=np.uint8,
            )

        with ThreadPoolExecutor(max_workers=min(16, len(values))) as pool:
            values = np.stack(list(pool.map(resize, values)))
        mean = (0.485, 0.456, 0.406)
        std = (0.229, 0.224, 0.225)
    else:
        mean = (0.48145466, 0.4578275, 0.40821073)
        std = (0.26862954, 0.26130258, 0.27577711)
    tensor = torch.from_numpy(np.ascontiguousarray(values)).permute(0, 3, 1, 2)
    tensor = tensor.to(device=device, dtype=torch.float32).div_(255.0)
    mean_tensor = torch.tensor(mean, device=device, dtype=torch.float32).view(1, 3, 1, 1)
    std_tensor = torch.tensor(std, device=device, dtype=torch.float32).view(1, 3, 1, 1)
    return tensor.sub_(mean_tensor).div_(std_tensor)


def read_part(part: pd.DataFrame) -> tuple[list[np.ndarray], list[str]]:
    path_values = part.local_relative_path.unique()
    if len(path_values) != 1:
        raise RuntimeError("one slide required per crop batch")
    crops, hashes = [], []
    with tifffile.TiffFile(ROOT / path_values[0]) as tif:
        page = tif.series[0].levels[0].pages[0]
        for row in part.itertuples(index=False):
            crop = read_tiled_rgb_region(page, row.level0_x0, row.level0_y0, row.level0_x1, row.level0_y1)
            crops.append(crop)
            hashes.append(hashlib.sha256(crop.tobytes(order="C")).hexdigest())
    return crops, hashes


def shared_crop_cache_path(file_id: str) -> Path:
    return LOCAL / "shared_canonical_crops" / f"{file_id}.npz"


def build_shared_canonical_crops(slide_rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    path_values = slide_rows.local_relative_path.unique()
    if len(path_values) != 1:
        raise RuntimeError("one slide required for canonical crop cache")
    crops, hashes = [], []
    with tifffile.TiffFile(ROOT / path_values[0]) as tif:
        page = tif.series[0].levels[0].pages[0]
        for row in slide_rows.itertuples(index=False):
            crop = read_tiled_rgb_region(
                page, row.level0_x0, row.level0_y0, row.level0_x1, row.level0_y1
            )
            hashes.append(hashlib.sha256(crop.tobytes(order="C")).hexdigest())
            canonical = Image.fromarray(crop, mode="RGB").resize(
                (448, 448), Image.Resampling.BICUBIC
            )
            crops.append(np.asarray(canonical, dtype=np.uint8))
    return np.stack(crops), np.asarray(hashes, dtype="U64")


def shared_canonical_crops(slide_rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    file_id = str(slide_rows.file_id.iloc[0])
    destination = shared_crop_cache_path(file_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def load() -> tuple[np.ndarray, np.ndarray]:
        with np.load(destination, allow_pickle=False) as cached:
            if not np.array_equal(cached["tile_id"].astype(str), slide_rows.tile_id.to_numpy(str)):
                raise RuntimeError(f"canonical crop tile order mismatch {file_id}")
            crops = cached["crop"]
            hashes = cached["level0_crop_sha256"]
        if crops.shape != (len(slide_rows), 448, 448, 3) or crops.dtype != np.uint8:
            raise RuntimeError(f"canonical crop shape/dtype mismatch {file_id}")
        return crops, hashes

    if destination.exists():
        return load()
    lock = destination.with_suffix(".lock")
    acquired = False
    while not acquired:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            acquired = True
        except FileExistsError:
            if destination.exists():
                return load()
            time.sleep(1)
    try:
        if destination.exists():
            return load()
        crops, hashes = build_shared_canonical_crops(slide_rows)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".npz", delete=False) as handle:
            temporary = Path(handle.name)
        np.savez(
            temporary,
            tile_id=slide_rows.tile_id.to_numpy(str),
            crop=crops,
            level0_crop_sha256=hashes,
        )
        os.replace(temporary, destination)
        return crops, hashes
    finally:
        lock.unlink(missing_ok=True)


def slide_cache_path(encoder: str, file_id: str) -> Path:
    return LOCAL / "slide_cache" / encoder / f"{file_id}.npz"


def prepare_crop_cache(shard_index: int = 0, num_shards: int = 1) -> None:
    manifest = pd.read_csv(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv")
    if not 0 <= shard_index < num_shards:
        raise ValueError("shard_index must be in [0, num_shards)")
    grouped = list(manifest.groupby("file_id", sort=False))
    grouped = [item for index, item in enumerate(grouped) if index % num_shards == shard_index]
    for complete, (_, slide_rows) in enumerate(grouped, 1):
        shared_canonical_crops(slide_rows)
        if complete % 10 == 0 or complete == len(grouped):
            print(
                f"canonical crop shard {shard_index + 1}/{num_shards}: {complete}/{len(grouped)} slides",
                flush=True,
            )


def extract(
    encoder: str,
    smoke_only: bool = False,
    shard_index: int = 0,
    num_shards: int = 1,
    assemble_after: bool = True,
) -> None:
    import torch

    manifest_path = OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    expected_hash = json.loads((OUTPUTS / "fm6_tcga_tile_manifest_run_config.json").read_text())["manifest_sha256"]
    if sha256_file(manifest_path) != expected_hash:
        raise RuntimeError("tile manifest hash changed")
    device = configure_device()
    model, transform = load_model(encoder, device)

    audit_slide = next(iter(manifest.groupby("file_id", sort=False)))[1]
    canonical_crops, _ = shared_canonical_crops(audit_slide)
    audit_count = min(BATCH_SIZE[encoder], len(audit_slide))
    crops = list(canonical_crops[:audit_count])
    tensor = transform_canonical_batch(encoder, np.stack(crops), device)
    with torch.inference_mode():
        first = embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if not np.array_equal(first, second) or first.shape != (audit_count, DIMENSION[encoder]):
        raise RuntimeError(f"{encoder} determinism/shape smoke failed")
    print(json.dumps({"encoder": encoder, "smoke_shape": list(first.shape), "exact_repeat": True}), flush=True)
    if smoke_only:
        return

    cache_root = LOCAL / "slide_cache" / encoder
    cache_root.mkdir(parents=True, exist_ok=True)
    if not 0 <= shard_index < num_shards:
        raise ValueError("shard_index must be in [0, num_shards)")
    grouped = list(manifest.groupby("file_id", sort=False))
    grouped = [item for index, item in enumerate(grouped) if index % num_shards == shard_index]
    complete = 0
    for file_id, slide_rows in grouped:
        destination = slide_cache_path(encoder, file_id)
        if destination.exists():
            with np.load(destination, allow_pickle=False) as cached:
                valid = (
                    cached["embedding"].shape == (len(slide_rows), DIMENSION[encoder])
                    and np.array_equal(cached["tile_id"].astype(str), slide_rows.tile_id.to_numpy(str))
                    and np.isfinite(cached["embedding"]).all()
                )
            if valid:
                complete += 1
                continue
        values = []
        canonical_crops, canonical_hashes = shared_canonical_crops(slide_rows)
        batch = BATCH_SIZE[encoder]
        for start in range(0, len(slide_rows), batch):
            part = slide_rows.iloc[start:start + batch]
            crops = list(canonical_crops[start:start + len(part)])
            tensor = transform_canonical_batch(encoder, np.stack(crops), device)
            with torch.inference_mode():
                output = embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
            values.append(output)
        embeddings = np.concatenate(values).astype(np.float32, copy=False)
        if embeddings.shape != (len(slide_rows), DIMENSION[encoder]) or not np.isfinite(embeddings).all():
            raise RuntimeError(f"invalid {encoder} embeddings for {file_id}")
        with tempfile.NamedTemporaryFile(dir=cache_root, suffix=".npz", delete=False) as handle:
            temporary = Path(handle.name)
        np.savez_compressed(
            temporary,
            tile_id=slide_rows.tile_id.to_numpy(str),
            embedding=embeddings,
            crop_sha256=canonical_hashes,
        )
        os.replace(temporary, destination)
        complete += 1
        if complete % 10 == 0 or complete == len(grouped):
            print(
                f"{encoder} shard {shard_index + 1}/{num_shards}: {complete}/{len(grouped)} slides",
                flush=True,
            )
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()
    if assemble_after:
        assemble(encoder)


def assemble(encoder: str) -> None:
    manifest = pd.read_csv(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv")
    array_path = LOCAL / f"fm6_tcga_{encoder}_tile_embeddings.npy"
    hash_path = LOCAL / f"fm6_tcga_{encoder}_crop_hashes.npy"
    embeddings = np.empty((len(manifest), DIMENSION[encoder]), dtype=np.float32)
    hashes = np.empty(len(manifest), dtype="U64")
    for file_id, rows in manifest.groupby("file_id", sort=False):
        path = slide_cache_path(encoder, file_id)
        if not path.exists():
            raise RuntimeError(f"missing {encoder} cache {file_id}")
        with np.load(path, allow_pickle=False) as cached:
            if not np.array_equal(cached["tile_id"].astype(str), rows.tile_id.to_numpy(str)):
                raise RuntimeError(f"tile order mismatch {file_id}")
            position = rows.embedding_row.to_numpy(int)
            embeddings[position] = cached["embedding"]
            hashes[position] = cached["crop_sha256"]
    np.save(array_path, embeddings, allow_pickle=False)
    np.save(hash_path, hashes, allow_pickle=False)
    spec = model_spec(encoder)
    row = {
        "encoder": encoder,
        "model_id": spec["model_id"],
        "model_revision": spec["revision"],
        "weights_sha256": sha256_file(Path(spec["weights"])),
        "rows": len(embeddings),
        "dimension": embeddings.shape[1],
        "dtype": str(embeddings.dtype),
        "nonfinite": int((~np.isfinite(embeddings)).sum()),
        "zero_norm_rows": int((np.linalg.norm(embeddings, axis=1) == 0).sum()),
        "embedding_sha256": sha256_file(array_path),
        "crop_hash_array_sha256": sha256_file(hash_path),
        "batch_size": BATCH_SIZE[encoder],
        "preprocessing": "shared canonical 448x448 RGB crop; vectorized official-equivalent encoder normalization",
        "determinism_exact": True,
        "status": "PASS",
    }
    qc_path = OUTPUTS / "fm6_tcga_embedding_technical_qc.csv"
    if qc_path.exists():
        qc = pd.read_csv(qc_path)
        qc = qc[qc.encoder.ne(encoder)]
        qc = pd.concat([qc, pd.DataFrame([row])], ignore_index=True)
    else:
        qc = pd.DataFrame([row])
    qc.sort_values("encoder").to_csv(qc_path, index=False, lineterminator="\n")
    print(json.dumps(row, indent=2), flush=True)
    other = "virchow" if encoder == "conch" else "conch"
    other_hash = LOCAL / f"fm6_tcga_{other}_crop_hashes.npy"
    if other_hash.exists():
        same = np.array_equal(hashes, np.load(other_hash, allow_pickle=False))
        paired = {
            "rows": len(hashes),
            "tile_ids_unique": bool(manifest.tile_id.is_unique),
            "row_order_locked": bool(manifest.embedding_row.equals(pd.Series(np.arange(len(manifest))))),
            "crop_hashes_identical_across_encoders": bool(same),
            "status": "PASS" if same else "FAIL",
        }
        (OUTPUTS / "fm6_tcga_paired_embedding_audit.json").write_text(json.dumps(paired, indent=2) + "\n")
        if not same:
            raise RuntimeError("paired crop hash mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("prepare")
    crop_parser = sub.add_parser("prepare-crops")
    crop_parser.add_argument("--shard-index", type=int, default=0)
    crop_parser.add_argument("--num-shards", type=int, default=1)
    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("--encoder", choices=["conch", "virchow"], required=True)
    extract_parser.add_argument("--smoke-only", action="store_true")
    extract_parser.add_argument("--shard-index", type=int, default=0)
    extract_parser.add_argument("--num-shards", type=int, default=1)
    extract_parser.add_argument("--no-assemble", action="store_true")
    assemble_parser = sub.add_parser("assemble")
    assemble_parser.add_argument("--encoder", choices=["conch", "virchow"], required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "prepare-crops":
        prepare_crop_cache(args.shard_index, args.num_shards)
    elif args.stage == "extract":
        extract(
            args.encoder,
            args.smoke_only,
            shard_index=args.shard_index,
            num_shards=args.num_shards,
            assemble_after=not args.no_assemble,
        )
    else:
        assemble(args.encoder)


if __name__ == "__main__":
    main()
