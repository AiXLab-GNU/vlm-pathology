#!/usr/bin/env python3
"""Run embargo-controlled CHIMERA external FM6 failure decomposition.

All generated products are local artifacts. This entry point never writes outcome-derived
content into the tracked project tree.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from PIL import Image
from scipy import stats
from sklearn.linear_model import Ridge


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm6_chimera_external_functional_validation"
ARTIFACTS = (
    ROOT
    / "resources/artifacts/quantitative_foundation_model_validation"
    / "fm6_chimera_external_functional_validation"
)
LOCAL_DATA = (
    ROOT
    / "resources/data/quantitative_foundation_model_validation/local-data/chimera_task1"
)
SOURCE_INVENTORY = LOCAL_DATA / "source_inventory.csv"
CLINICAL = LOCAL_DATA / "normalized_clinical.csv"
DATASET_MANIFEST = ROOT / "resources/data/manifests/chimera_task1.yaml"
INTERNAL_MILESTONE = PROJECT / "milestones/fm6_internal_development_pilot"
INTERNAL_OUTPUTS = INTERNAL_MILESTONE / "outputs"
INTERNAL_ARTIFACTS = (
    ROOT
    / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"
)


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


INTERNAL_RUNNER = load_module(
    "fm6_internal_runner_chimera", INTERNAL_MILESTONE / "run_fm6_tcga_internal_pilot.py"
)
INTERNAL_ANALYSIS = load_module(
    "fm6_internal_analysis_chimera",
    INTERNAL_MILESTONE / "analyze_fm6_tcga_internal_pilot.py",
)
SITE_ANALYSIS = load_module(
    "fm6_site_analysis_chimera",
    PROJECT
    / "milestones/fm6_site_heldout_functional_validation"
    / "run_fm6_site_heldout_functional_xai.py",
)

SEED = 260820
FOV_UM = 394.24
MAX_TILES = 64
MIN_TILES = 16
TISSUE_FRACTION_PRIMARY = 0.35
TISSUE_FRACTION_FALLBACK = 0.15
DIMENSION = {"conch": 512, "virchow": 2560}
BATCH_SIZE = {"conch": 64, "virchow": 64}
EXPECTED_SUBJECTS = 95
EXPECTED_EVENTS = 27
EXPECTED_WSI = 190
EXPECTED_MASKS = 190
EXPECTED_CONCORDANT_ISUP = 92
EXPECTED_TILES = EXPECTED_WSI * MAX_TILES
RANDOM_CONTROLS = 100
BOOTSTRAPS = 2000
RIDGE_ALPHA = 1000.0
COX_ALPHA = 1000.0
PCA_COMPONENTS = 64
EMBARGO_STATUS = "EMBARGO_ACTIVE_NO_WRITTEN_CLEARANCE"
PUBLICATION_GATE_CHECKED_ON = "2026-08-21"
PUBLICATION_GATE_URLS = [
    "https://chimera.grand-challenge.org/dataset-download/",
    "https://chimera.grand-challenge.org/challenge-rules/",
]
PUBLICATION_GATE_RULE = (
    "results from CHIMERA public training data may not be published until both the "
    "CHIMERA challenge journal paper and baseline journal paper are published"
)
EXPECTED_INPUT_SHA256 = {
    "chimera_task1.yaml": "c87cb4fe1962eaee6fe95ec121032fe44ed9b5cea7ce5bfa1c73d50c8be9268f",
    "source_inventory.csv": "06cd367f8c28a47c8da55ed3198c81a5ba8effb1b971eef97e8809ec18eabca0",
    "normalized_clinical.csv": "95e62aa7c0a70d065fbaa3bf9d688f7f7d2c7fc0b27635cb190331ad042773bb",
    "development_subjects.csv": "c36bfc442f6f33aaa6887eb6882c62f8984561e2336a35b6ab30eab370e1d814",
    "fm6_tcga_whole_tissue_tile_manifest.csv": "d4fe8ba50ec0e129ebcc7e5b529b4d26bb724de89f8869bb06648716ab4a9c04",
    "fm6_tcga_embedding_technical_qc.csv": "8dd0bb6c2917b7367532a968ace70ad88a3e6cc8e7bb4aa4d816e042ce24e3bd",
    "fm6_tcga_conch_tile_embeddings.npy": "99c6d5f3bc59070a7c2e74f3c6f3adc3f7f8db5cf6d8837465bde955953e9d2d",
    "fm6_tcga_virchow_tile_embeddings.npy": "4e23555436084c1154dbfdd94df86ddff556617fa41864615fb505f438f17ca7",
}

CAUSE_STATES = {
    "INTEGRITY_FAILURE_NO_SCIENTIFIC_INTERPRETATION": 0,
    "ISUP_NOT_RECOVERABLE_EXTERNAL_REPRESENTATION_SHIFT": 1,
    "ISUP_RECOVERABLE_BCR_HEAD_NOT_TRANSPORTED": 2,
    "FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION": 3,
    "BCR_HEAD_TRANSPORTED_FUNCTIONAL_ERASURE_NOT_QUALIFIED": 4,
    "QUALIFIED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT": 5,
}


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def stable_rng(token: str) -> np.random.Generator:
    raw = hashlib.sha256(f"{SEED}:{token}".encode()).digest()[:8]
    return np.random.default_rng(int.from_bytes(raw, "little"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def source_paths() -> dict[str, Path]:
    return {
        "chimera_task1.yaml": DATASET_MANIFEST,
        "source_inventory.csv": SOURCE_INVENTORY,
        "normalized_clinical.csv": CLINICAL,
        "development_subjects.csv": (
            ROOT
            / "resources/data/quantitative_foundation_model_validation/local-data"
            / "tcga_prad_current_gdc_bcr/development_subjects.csv"
        ),
        "fm6_tcga_whole_tissue_tile_manifest.csv": (
            INTERNAL_OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv"
        ),
        "fm6_tcga_embedding_technical_qc.csv": (
            INTERNAL_OUTPUTS / "fm6_tcga_embedding_technical_qc.csv"
        ),
        "fm6_tcga_conch_tile_embeddings.npy": (
            INTERNAL_ARTIFACTS / "fm6_tcga_conch_tile_embeddings.npy"
        ),
        "fm6_tcga_virchow_tile_embeddings.npy": (
            INTERNAL_ARTIFACTS / "fm6_tcga_virchow_tile_embeddings.npy"
        ),
    }


def verify_locked_inputs() -> dict[str, str]:
    observed = {name: sha256_file(path) for name, path in source_paths().items()}
    if observed != EXPECTED_INPUT_SHA256:
        raise RuntimeError(f"locked input hash mismatch: {observed}")
    paired = json.loads(
        (INTERNAL_OUTPUTS / "fm6_tcga_paired_embedding_audit.json").read_text()
    )
    if paired.get("status") != "PASS" or not paired.get(
        "crop_hashes_identical_across_encoders"
    ):
        raise RuntimeError("TCGA paired embedding audit is not locked PASS")
    return observed


def _boolean(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def source_membership(full_hash: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    verify_locked_inputs()
    inventory = pd.read_csv(SOURCE_INVENTORY, dtype={"remote_key": str})
    clinical = pd.read_csv(CLINICAL, dtype={"subject_id": str})
    if len(inventory) != EXPECTED_SUBJECTS + EXPECTED_WSI + EXPECTED_MASKS:
        raise RuntimeError("CHIMERA inventory row universe changed")
    if inventory.remote_key.duplicated().any() or inventory.local_relative_path.duplicated().any():
        raise RuntimeError("duplicate CHIMERA source object")
    if len(clinical) != EXPECTED_SUBJECTS or clinical.subject_id.nunique() != EXPECTED_SUBJECTS:
        raise RuntimeError("CHIMERA clinical subject universe changed")
    if int(clinical.bcr_event.sum()) != EXPECTED_EVENTS:
        raise RuntimeError("CHIMERA BCR event universe changed")
    if int(clinical.isup_gleason_consistency.eq("concordant").sum()) != EXPECTED_CONCORDANT_ISUP:
        raise RuntimeError("CHIMERA ISUP discrepancy universe changed")

    role_counts = inventory.role.value_counts().to_dict()
    expected_roles = {
        "clinical_json": EXPECTED_SUBJECTS,
        "prostatectomy_wsi": EXPECTED_WSI,
        "tissue_mask": EXPECTED_MASKS,
    }
    if role_counts != expected_roles:
        raise RuntimeError(f"CHIMERA role counts changed: {role_counts}")

    rows: list[dict[str, object]] = []
    for row in inventory.itertuples(index=False):
        path = ROOT / str(row.local_relative_path)
        if not _boolean(row.local_complete) or not path.is_file():
            raise FileNotFoundError(f"incomplete CHIMERA object: {row.remote_key}")
        if path.stat().st_size != int(row.remote_size):
            raise RuntimeError(f"CHIMERA object size mismatch: {row.remote_key}")
        if len(str(row.sha256)) != 64:
            raise RuntimeError(f"CHIMERA source hash missing: {row.remote_key}")
        if full_hash and sha256_file(path) != str(row.sha256):
            raise RuntimeError(f"CHIMERA object SHA-256 mismatch: {row.remote_key}")
        if row.role in {"prostatectomy_wsi", "tissue_mask"}:
            remote = Path(str(row.remote_key))
            subject_id = remote.parent.name
            stem = remote.name.removesuffix(".tif").removesuffix("_tissue")
            rows.append(
                {
                    "subject_id": subject_id,
                    "slide_id": stem,
                    "role": row.role,
                    "local_relative_path": str(row.local_relative_path),
                    "bytes": int(row.remote_size),
                    "sha256": str(row.sha256),
                }
            )
    image = pd.DataFrame(rows)
    if image.duplicated(["slide_id", "role"]).any():
        raise RuntimeError("duplicate CHIMERA slide role")
    wide = image.pivot(index=["subject_id", "slide_id"], columns="role", values="local_relative_path")
    if len(wide) != EXPECTED_WSI or wide.isna().any().any():
        raise RuntimeError("missing CHIMERA WSI/mask pair")
    if set(wide.index.get_level_values("subject_id")) != set(clinical.subject_id):
        raise RuntimeError("CHIMERA patient-slide linkage mismatch")
    slides = wide.reset_index().sort_values(["subject_id", "slide_id"], kind="stable")
    slides = slides.reset_index(drop=True)
    return slides, clinical.sort_values("subject_id", kind="stable").reset_index(drop=True)


def verify_source(full_hash: bool) -> dict[str, object]:
    started = time.time()
    slides, clinical = source_membership(full_hash=full_hash)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "PASS",
        "verified_at_utc": utc_now(),
        "full_object_sha256_verified": full_hash,
        "subjects": len(clinical),
        "events": int(clinical.bcr_event.sum()),
        "wsi": len(slides),
        "masks": len(slides),
        "source_payload_bytes": int(pd.read_csv(SOURCE_INVENTORY).remote_size.sum()),
        "inventory_sha256": sha256_file(SOURCE_INVENTORY),
        "clinical_sha256": sha256_file(CLINICAL),
        "runtime_seconds": round(time.time() - started, 6),
        "volatile_fields": ["verified_at_utc", "runtime_seconds"],
    }
    (ARTIFACTS / "source_verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def mask_fraction(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> float:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(mask.shape[1], x1), min(mask.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((mask[y0:y1, x0:x1] > 0).mean())


def candidate_coordinates(
    mask: np.ndarray,
    base_width: int,
    base_height: int,
    crop_px: int,
    threshold: float,
    step_divisor: int,
) -> list[tuple[int, int, float]]:
    scale_x = base_width / mask.shape[1]
    scale_y = base_height / mask.shape[0]
    half_x = max(1, int(round(crop_px / scale_x / 2)))
    half_y = max(1, int(round(crop_px / scale_y / 2)))
    step_x = max(1, (2 * half_x) // step_divisor)
    step_y = max(1, (2 * half_y) // step_divisor)
    choices = []
    for cy in range(half_y, mask.shape[0] - half_y, step_y):
        for cx in range(half_x, mask.shape[1] - half_x, step_x):
            fraction = mask_fraction(
                mask, cx - half_x, cy - half_y, cx + half_x, cy + half_y
            )
            if fraction >= threshold:
                choices.append((cx, cy, fraction))
    return choices


def prepare_slide(source: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    image = ROOT / str(source.prostatectomy_wsi)
    mask_path = ROOT / str(source.tissue_mask)
    with tifffile.TiffFile(image) as tif, tifffile.TiffFile(mask_path) as mask_tif:
        base = tif.series[0].levels[0].pages[0]
        mask_page = mask_tif.series[0].levels[0].pages[0]
        mpp = INTERNAL_RUNNER.native_mpp(base)
        crop_px = int(round(FOV_UM / mpp))
        mask = np.asarray(mask_page.asarray())
        choices = candidate_coordinates(
            mask,
            int(base.imagewidth),
            int(base.imagelength),
            crop_px,
            TISSUE_FRACTION_PRIMARY,
            1,
        )
        selection_rule = "leopard_primary"
        if len(choices) < MIN_TILES:
            choices = candidate_coordinates(
                mask,
                int(base.imagewidth),
                int(base.imagelength),
                crop_px,
                TISSUE_FRACTION_FALLBACK,
                2,
            )
            selection_rule = "leopard_fallback"
        rng = stable_rng(str(source.slide_id))
        order = rng.permutation(len(choices)) if choices else np.asarray([], dtype=int)
        selected = [choices[index] for index in order[:MAX_TILES]]
        scale_x = base.imagewidth / mask.shape[1]
        scale_y = base.imagelength / mask.shape[0]
        records = []
        for rank, (cx, cy, fraction) in enumerate(selected):
            center_x = int(round((cx + 0.5) * scale_x))
            center_y = int(round((cy + 0.5) * scale_y))
            x0 = min(max(0, center_x - crop_px // 2), base.imagewidth - crop_px)
            y0 = min(max(0, center_y - crop_px // 2), base.imagelength - crop_px)
            records.append(
                {
                    "subject_id": str(source.subject_id),
                    "slide_id": str(source.slide_id),
                    "tile_rank": rank,
                    "tile_id": f"{source.slide_id}:{rank:03d}",
                    "wsi_local_relative_path": str(source.prostatectomy_wsi),
                    "mask_local_relative_path": str(source.tissue_mask),
                    "level0_x0": x0,
                    "level0_y0": y0,
                    "level0_x1": x0 + crop_px,
                    "level0_y1": y0 + crop_px,
                    "physical_fov_um": FOV_UM,
                    "mpp": mpp,
                    "mask_tissue_fraction": fraction,
                }
            )
        audit = {
            "subject_id": str(source.subject_id),
            "slide_id": str(source.slide_id),
            "width_px": int(base.imagewidth),
            "height_px": int(base.imagelength),
            "mpp": mpp,
            "crop_px": crop_px,
            "mask_width": int(mask.shape[1]),
            "mask_height": int(mask.shape[0]),
            "candidate_count": len(choices),
            "selected_count": len(selected),
            "selection_rule": selection_rule,
            "sampling_status": "PASS" if len(selected) == MAX_TILES else "FAIL_NOT_64",
        }
        return records, audit


def prepare() -> dict[str, object]:
    started = time.time()
    slides, clinical = source_membership(full_hash=False)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    embedding_row = 0
    for number, source in enumerate(slides.itertuples(index=False), 1):
        records, audit = prepare_slide(source)
        audits.append(audit)
        for record in records:
            rows.append({"embedding_row": embedding_row, **record})
            embedding_row += 1
        if number % 10 == 0 or number == len(slides):
            print(f"prepare CHIMERA {number}/{len(slides)}; {embedding_row} crops", flush=True)
    manifest = pd.DataFrame(rows)
    sampling = pd.DataFrame(audits)
    if not sampling.sampling_status.eq("PASS").all():
        failed = sampling.loc[~sampling.sampling_status.eq("PASS"), "slide_id"].tolist()
        raise RuntimeError(f"CHIMERA WSI did not yield exactly 64 crops: {failed}")
    if len(manifest) != EXPECTED_TILES or manifest.tile_id.duplicated().any():
        raise RuntimeError("CHIMERA crop membership failure")
    if not manifest.embedding_row.equals(pd.Series(np.arange(len(manifest)))):
        raise RuntimeError("CHIMERA crop row-order failure")
    if manifest.groupby("slide_id").size().ne(MAX_TILES).any():
        raise RuntimeError("CHIMERA per-slide crop count failure")
    if set(manifest.subject_id.astype(str)) != set(clinical.subject_id.astype(str)):
        raise RuntimeError("CHIMERA prepared subject linkage failure")
    manifest_path = ARTIFACTS / "fm6_chimera_tile_manifest.csv"
    sampling_path = ARTIFACTS / "fm6_chimera_sampling_qc.csv"
    manifest.to_csv(manifest_path, index=False, lineterminator="\n")
    sampling.to_csv(sampling_path, index=False, lineterminator="\n")
    lock = {
        "protocol": "fm6-chimera-external-functional-xai-protocol",
        "created_at_utc": utc_now(),
        "seed": SEED,
        "physical_fov_um": FOV_UM,
        "max_tiles_per_wsi": MAX_TILES,
        "min_tiles_per_wsi": MIN_TILES,
        "subjects": len(clinical),
        "events": int(clinical.bcr_event.sum()),
        "wsi": len(slides),
        "masks": len(slides),
        "crops": len(manifest),
        "primary_aggregation": "crop_mean_then_equal_weight_slide_mean_per_patient",
        "publication_status": EMBARGO_STATUS,
        "publication_gate_checked_on": PUBLICATION_GATE_CHECKED_ON,
        "publication_gate_urls": PUBLICATION_GATE_URLS,
        "publication_gate_rule": PUBLICATION_GATE_RULE,
        "target_cohort_tuning": "PROHIBITED",
        "input_sha256": verify_locked_inputs(),
        "tile_manifest_sha256": sha256_file(manifest_path),
        "sampling_qc_sha256": sha256_file(sampling_path),
        "runtime_seconds": round(time.time() - started, 6),
        "volatile_fields": ["created_at_utc", "runtime_seconds"],
    }
    (ARTIFACTS / "fm6_chimera_preparation_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return lock


def verify_preparation() -> tuple[pd.DataFrame, dict[str, object]]:
    lock_path = ARTIFACTS / "fm6_chimera_preparation_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    manifest_path = ARTIFACTS / "fm6_chimera_tile_manifest.csv"
    sampling_path = ARTIFACTS / "fm6_chimera_sampling_qc.csv"
    if sha256_file(manifest_path) != lock["tile_manifest_sha256"]:
        raise RuntimeError("CHIMERA tile manifest changed after preparation")
    if sha256_file(sampling_path) != lock["sampling_qc_sha256"]:
        raise RuntimeError("CHIMERA sampling QC changed after preparation")
    observed_inputs = verify_locked_inputs()
    if any(observed_inputs.get(name) != value for name, value in lock["input_sha256"].items()):
        raise RuntimeError("CHIMERA/TCGA locked inputs changed after preparation")
    manifest = pd.read_csv(manifest_path, dtype={"subject_id": str, "slide_id": str})
    if len(manifest) != EXPECTED_TILES:
        raise RuntimeError("CHIMERA prepared crop universe changed")
    return manifest, lock


def shared_crop_cache_path(slide_id: str) -> Path:
    return ARTIFACTS / "shared_canonical_crops" / f"{slide_id}.npz"


def build_shared_canonical_crops(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    paths = rows.wsi_local_relative_path.unique()
    if len(paths) != 1:
        raise RuntimeError("one CHIMERA WSI required per crop cache")
    crops: list[np.ndarray] = []
    hashes: list[str] = []
    with tifffile.TiffFile(ROOT / str(paths[0])) as tif:
        base = tif.series[0].levels[0].pages[0]
        for row in rows.itertuples(index=False):
            crop = INTERNAL_RUNNER.read_tiled_rgb_region(
                base, row.level0_x0, row.level0_y0, row.level0_x1, row.level0_y1
            )
            hashes.append(hashlib.sha256(crop.tobytes(order="C")).hexdigest())
            canonical = Image.fromarray(crop, mode="RGB").resize(
                (448, 448), Image.Resampling.BICUBIC
            )
            crops.append(np.asarray(canonical, dtype=np.uint8))
    return np.stack(crops), np.asarray(hashes, dtype="U64")


def shared_canonical_crops(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    slide_id = str(rows.slide_id.iloc[0])
    destination = shared_crop_cache_path(slide_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def load() -> tuple[np.ndarray, np.ndarray]:
        with np.load(destination, allow_pickle=False) as cached:
            tile_id = cached["tile_id"].astype(str)
            crops = cached["crop"]
            hashes = cached["decoded_rgb_sha256"].astype(str)
        if not np.array_equal(tile_id, rows.tile_id.to_numpy(str)):
            raise RuntimeError(f"shared crop order mismatch: {slide_id}")
        if crops.shape != (len(rows), 448, 448, 3) or crops.dtype != np.uint8:
            raise RuntimeError(f"shared crop shape/dtype mismatch: {slide_id}")
        return crops, hashes

    if destination.exists():
        return load()
    crops, hashes = build_shared_canonical_crops(rows)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    np.savez(
        temporary,
        tile_id=rows.tile_id.to_numpy(str),
        crop=crops,
        decoded_rgb_sha256=hashes,
    )
    os.replace(temporary, destination)
    return load()


def prepare_crops(shard_index: int, shard_count: int) -> None:
    manifest, _ = verify_preparation()
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    grouped = list(manifest.groupby("slide_id", sort=False))
    grouped = [pair for index, pair in enumerate(grouped) if index % shard_count == shard_index]
    for complete, (_, rows) in enumerate(grouped, 1):
        shared_canonical_crops(rows)
        if complete % 10 == 0 or complete == len(grouped):
            print(
                f"canonical crops shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(grouped)}",
                flush=True,
            )


def slide_cache_path(encoder: str, slide_id: str) -> Path:
    return ARTIFACTS / "slide_cache" / encoder / f"{slide_id}.npz"


def extract(encoder: str, smoke_only: bool, shard_index: int, shard_count: int) -> None:
    import torch

    manifest, _ = verify_preparation()
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    device = INTERNAL_RUNNER.configure_device()
    model, _ = INTERNAL_RUNNER.load_model(encoder, device)
    first_rows = next(iter(manifest.groupby("slide_id", sort=False)))[1]
    first_crops, _ = shared_canonical_crops(first_rows)
    smoke = first_crops[: min(4, len(first_crops))]
    tensor = INTERNAL_RUNNER.transform_canonical_batch(encoder, smoke, device)
    with torch.inference_mode():
        first = INTERNAL_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = INTERNAL_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if not np.array_equal(first, second) or first.shape != (len(smoke), DIMENSION[encoder]):
        raise RuntimeError(f"{encoder} CHIMERA deterministic smoke failed")
    print(json.dumps({"encoder": encoder, "shape": list(first.shape), "exact_repeat": True}))
    if smoke_only:
        return

    cache_root = ARTIFACTS / "slide_cache" / encoder
    cache_root.mkdir(parents=True, exist_ok=True)
    grouped = list(manifest.groupby("slide_id", sort=False))
    grouped = [pair for index, pair in enumerate(grouped) if index % shard_count == shard_index]
    for complete, (slide_id, rows) in enumerate(grouped, 1):
        destination = slide_cache_path(encoder, str(slide_id))
        valid = False
        if destination.exists():
            with np.load(destination, allow_pickle=False) as cached:
                valid = bool(
                    cached["embedding"].shape == (len(rows), DIMENSION[encoder])
                    and np.array_equal(cached["tile_id"].astype(str), rows.tile_id.to_numpy(str))
                    and np.isfinite(cached["embedding"]).all()
                )
        if not valid:
            crops, hashes = shared_canonical_crops(rows)
            values = []
            for start in range(0, len(rows), BATCH_SIZE[encoder]):
                batch = crops[start : start + BATCH_SIZE[encoder]]
                tensor = INTERNAL_RUNNER.transform_canonical_batch(encoder, batch, device)
                with torch.inference_mode():
                    values.append(
                        INTERNAL_RUNNER.embed_batch(encoder, model, tensor)
                        .detach()
                        .cpu()
                        .float()
                        .numpy()
                    )
            embeddings = np.concatenate(values).astype(np.float32, copy=False)
            if embeddings.shape != (len(rows), DIMENSION[encoder]) or not np.isfinite(embeddings).all():
                raise RuntimeError(f"invalid {encoder} CHIMERA embeddings: {slide_id}")
            with tempfile.NamedTemporaryFile(dir=cache_root, suffix=".npz", delete=False) as handle:
                temporary = Path(handle.name)
            np.savez_compressed(
                temporary,
                tile_id=rows.tile_id.to_numpy(str),
                embedding=embeddings,
                decoded_rgb_sha256=hashes,
            )
            os.replace(temporary, destination)
        if complete % 10 == 0 or complete == len(grouped):
            print(
                f"{encoder} shard {shard_index + 1}/{shard_count}: "
                f"{complete}/{len(grouped)}",
                flush=True,
            )
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()


def assemble(encoder: str) -> None:
    manifest, _ = verify_preparation()
    embeddings = np.empty((len(manifest), DIMENSION[encoder]), dtype=np.float32)
    hashes = np.empty(len(manifest), dtype="U64")
    for slide_id, rows in manifest.groupby("slide_id", sort=False):
        path = slide_cache_path(encoder, str(slide_id))
        if not path.exists():
            raise RuntimeError(f"missing {encoder} CHIMERA cache: {slide_id}")
        with np.load(path, allow_pickle=False) as cached:
            if not np.array_equal(cached["tile_id"].astype(str), rows.tile_id.to_numpy(str)):
                raise RuntimeError(f"{encoder} CHIMERA tile order mismatch: {slide_id}")
            position = rows.embedding_row.to_numpy(int)
            embeddings[position] = cached["embedding"]
            hashes[position] = cached["decoded_rgb_sha256"]
    if not np.isfinite(embeddings).all():
        raise RuntimeError(f"nonfinite assembled {encoder} CHIMERA embedding")
    np.save(ARTIFACTS / f"fm6_chimera_{encoder}_tile_embeddings.npy", embeddings, allow_pickle=False)
    np.save(ARTIFACTS / f"fm6_chimera_{encoder}_crop_hashes.npy", hashes, allow_pickle=False)


def paired_embedding_audit() -> dict[str, object]:
    manifest, _ = verify_preparation()
    conch_hashes = np.load(ARTIFACTS / "fm6_chimera_conch_crop_hashes.npy", allow_pickle=False)
    virchow_hashes = np.load(ARTIFACTS / "fm6_chimera_virchow_crop_hashes.npy", allow_pickle=False)
    conch = np.load(
        ARTIFACTS / "fm6_chimera_conch_tile_embeddings.npy", mmap_mode="r", allow_pickle=False
    )
    virchow = np.load(
        ARTIFACTS / "fm6_chimera_virchow_tile_embeddings.npy", mmap_mode="r", allow_pickle=False
    )
    audit = {
        "rows": len(manifest),
        "subjects": int(manifest.subject_id.nunique()),
        "slides": int(manifest.slide_id.nunique()),
        "tile_ids_unique": bool(not manifest.tile_id.duplicated().any()),
        "row_order_locked": bool(
            manifest.embedding_row.equals(pd.Series(np.arange(len(manifest))))
        ),
        "decoded_crop_hashes_identical_across_encoders": bool(
            np.array_equal(conch_hashes, virchow_hashes)
        ),
        "conch_shape": list(conch.shape),
        "virchow_shape": list(virchow.shape),
    }
    audit["status"] = "PASS" if all(
        [
            audit["rows"] == EXPECTED_TILES,
            audit["subjects"] == EXPECTED_SUBJECTS,
            audit["slides"] == EXPECTED_WSI,
            audit["tile_ids_unique"],
            audit["row_order_locked"],
            audit["decoded_crop_hashes_identical_across_encoders"],
            conch.shape == (EXPECTED_TILES, DIMENSION["conch"]),
            virchow.shape == (EXPECTED_TILES, DIMENSION["virchow"]),
            np.isfinite(conch).all(),
            np.isfinite(virchow).all(),
        ]
    ) else "FAIL"
    (ARTIFACTS / "fm6_chimera_paired_embedding_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def aggregate_patient_embeddings(
    manifest: pd.DataFrame, embeddings: np.ndarray
) -> tuple[pd.DataFrame, np.ndarray]:
    if len(manifest) != len(embeddings):
        raise RuntimeError("CHIMERA manifest/embedding row mismatch")
    slide_rows: list[dict[str, object]] = []
    slide_vectors: list[np.ndarray] = []
    for slide_id, rows in manifest.groupby("slide_id", sort=False):
        if rows.subject_id.nunique() != 1 or len(rows) != MAX_TILES:
            raise RuntimeError(f"invalid CHIMERA slide aggregation unit: {slide_id}")
        positions = rows.embedding_row.to_numpy(int)
        slide_vectors.append(np.asarray(embeddings[positions], dtype=np.float64).mean(axis=0))
        slide_rows.append(
            {
                "subject_id": str(rows.subject_id.iloc[0]),
                "slide_id": str(slide_id),
                "n_tiles": len(rows),
            }
        )
    slide = pd.DataFrame(slide_rows)
    slide_x = np.stack(slide_vectors)
    patient_rows: list[dict[str, object]] = []
    patient_vectors: list[np.ndarray] = []
    for subject_id, rows in slide.groupby("subject_id", sort=True):
        patient_vectors.append(slide_x[rows.index.to_numpy(int)].mean(axis=0))
        patient_rows.append(
            {
                "subject_id": str(subject_id),
                "n_slides": len(rows),
                "n_tiles": int(rows.n_tiles.sum()),
            }
        )
    patient = pd.DataFrame(patient_rows)
    if len(patient) != EXPECTED_SUBJECTS or patient.subject_id.duplicated().any():
        raise RuntimeError("CHIMERA patient aggregation membership failure")
    return patient, np.stack(patient_vectors)


def load_external_subject_data(encoder: str) -> tuple[pd.DataFrame, np.ndarray]:
    manifest, _ = verify_preparation()
    values = np.load(
        ARTIFACTS / f"fm6_chimera_{encoder}_tile_embeddings.npy",
        mmap_mode="r",
        allow_pickle=False,
    )
    subject, x = aggregate_patient_embeddings(manifest, values)
    clinical = pd.read_csv(CLINICAL, dtype={"subject_id": str})
    subject = subject.merge(clinical, on="subject_id", validate="one_to_one")
    order = subject.subject_id.argsort(kind="stable").to_numpy()
    subject = subject.iloc[order].reset_index(drop=True)
    x = x[order]
    if int(subject.bcr_event.sum()) != EXPECTED_EVENTS:
        raise RuntimeError("CHIMERA analysis event universe changed")
    return subject, x


def percentile_ci(values: np.ndarray) -> tuple[float, float]:
    valid = np.asarray(values, dtype=float)
    valid = valid[np.isfinite(valid)]
    if len(valid) < int(0.95 * BOOTSTRAPS):
        raise RuntimeError("too few valid patient bootstrap draws")
    low, high = np.quantile(valid, [0.025, 0.975])
    return float(low), float(high)


def bootstrap_spearman(
    truth: np.ndarray, prediction: np.ndarray, token: str
) -> tuple[float, float, int]:
    rng = stable_rng(f"bootstrap-spearman:{token}")
    draws = np.full(BOOTSTRAPS, np.nan)
    for draw in range(BOOTSTRAPS):
        sample = rng.integers(0, len(truth), len(truth))
        value = stats.spearmanr(truth[sample], prediction[sample]).statistic
        if np.isfinite(value):
            draws[draw] = value
    low, high = percentile_ci(draws)
    return low, high, int(np.isfinite(draws).sum())


def bootstrap_survival(
    event: np.ndarray,
    follow_up: np.ndarray,
    full_risk: np.ndarray,
    target_risk: np.ndarray,
    token: str,
) -> tuple[dict[str, tuple[float, float]], int]:
    rng = stable_rng(f"bootstrap-survival:{token}")
    full_draws = np.full(BOOTSTRAPS, np.nan)
    target_draws = np.full(BOOTSTRAPS, np.nan)
    for draw in range(BOOTSTRAPS):
        sample = rng.integers(0, len(event), len(event))
        try:
            full_draws[draw] = SITE_ANALYSIS.ordinary_c_index(
                event[sample], follow_up[sample], full_risk[sample]
            )
            target_draws[draw] = SITE_ANALYSIS.ordinary_c_index(
                event[sample], follow_up[sample], target_risk[sample]
            )
        except Exception:
            continue
    valid = np.isfinite(full_draws) & np.isfinite(target_draws)
    intervals = {
        "full_c_index": percentile_ci(full_draws[valid]),
        "target_erased_c_index": percentile_ci(target_draws[valid]),
        "target_delta_use": percentile_ci((full_draws - target_draws)[valid]),
    }
    return intervals, int(valid.sum())


def classify_cause(row: dict[str, object]) -> str:
    if float(row["isup_spearman_all95"]) <= 0:
        return "ISUP_NOT_RECOVERABLE_EXTERNAL_REPRESENTATION_SHIFT"
    if float(row["isup_spearman_all95_ci_low"]) <= 0:
        return "FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION"
    if float(row["full_c_index"]) <= 0.50:
        return "ISUP_RECOVERABLE_BCR_HEAD_NOT_TRANSPORTED"
    if float(row["full_c_index_ci_low"]) <= 0.50:
        return "FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION"
    if float(row["target_delta_use"]) > 0 and float(row["target_delta_use_ci_low"]) <= 0:
        return "FAIL_OR_INCONCLUSIVE_LOW_EVENT_PRECISION"
    if bool(row["functional_erasure_gate_pass"]):
        return "QUALIFIED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT"
    return "BCR_HEAD_TRANSPORTED_FUNCTIONAL_ERASURE_NOT_QUALIFIED"


def analyze_encoder(
    encoder: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    internal_subject, internal_x, _ = INTERNAL_ANALYSIS.load_subject_data(encoder)
    external_subject, external_x = load_external_subject_data(encoder)
    internal_event = internal_subject.bcr_event.to_numpy(int)
    internal_time = internal_subject.bcr_time_days.to_numpy(float)
    internal_isup = internal_subject.isup_grade_group.to_numpy(float)
    external_event = external_subject.bcr_event.to_numpy(int)
    external_time = external_subject.time_to_follow_up_or_bcr_months.to_numpy(float)
    external_isup = external_subject.isup_grade_group_reported.to_numpy(float)

    model = SITE_ANALYSIS.fit_head(internal_x, internal_event, internal_time)
    scaler = model[0]
    internal_scaled = scaler.transform(internal_x)
    external_scaled = scaler.transform(external_x)
    probe = Ridge(alpha=RIDGE_ALPHA).fit(internal_scaled, internal_isup)
    direction = probe.coef_.astype(float)
    isup_prediction = probe.predict(external_scaled)
    full_risk = SITE_ANALYSIS.predict_standardized_head(model, external_x)
    target_risk = SITE_ANALYSIS.predict_scaled_head(
        model, INTERNAL_ANALYSIS.erase_direction(external_scaled, direction)
    )

    random_directions, variance_ratios, concept_cosines = (
        INTERNAL_ANALYSIS.variance_matched_random_directions(
            internal_scaled,
            direction,
            RANDOM_CONTROLS,
            stable_rng(f"matched-random:{encoder}"),
        )
    )
    full_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, full_risk)
    target_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, target_risk)
    target_delta = full_c - target_c
    random_rows = []
    random_deltas = np.empty(RANDOM_CONTROLS, dtype=float)
    for draw, random_direction in enumerate(random_directions):
        random_risk = SITE_ANALYSIS.predict_scaled_head(
            model, INTERNAL_ANALYSIS.erase_direction(external_scaled, random_direction)
        )
        random_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, random_risk)
        random_deltas[draw] = full_c - random_c
        random_rows.append(
            {
                "encoder": encoder,
                "draw": draw,
                "random_erased_c_index": random_c,
                "random_delta_use": random_deltas[draw],
                "removed_variance_ratio": variance_ratios[draw],
                "concept_abs_cosine": concept_cosines[draw],
            }
        )

    isup_rho = float(stats.spearmanr(external_isup, isup_prediction).statistic)
    isup_ci_low, isup_ci_high, isup_valid = bootstrap_spearman(
        external_isup, isup_prediction, f"{encoder}:all95"
    )
    concordant = external_subject.isup_gleason_consistency.eq("concordant").to_numpy()
    isup_92 = float(
        stats.spearmanr(external_isup[concordant], isup_prediction[concordant]).statistic
    )
    isup_92_low, isup_92_high, isup_92_valid = bootstrap_spearman(
        external_isup[concordant], isup_prediction[concordant], f"{encoder}:concordant92"
    )
    survival_intervals, survival_valid = bootstrap_survival(
        external_event, external_time, full_risk, target_risk, encoder
    )
    random_p95 = float(np.quantile(random_deltas, 0.95))
    p_value = float((1 + np.sum(random_deltas >= target_delta)) / (RANDOM_CONTROLS + 1))

    predictions = external_subject.copy()
    predictions.insert(0, "encoder", encoder)
    predictions["isup_prediction"] = isup_prediction
    predictions["full_risk"] = full_risk
    predictions["target_erased_risk"] = target_risk
    interval_rows = [
        {"encoder": encoder, "universe": "all95", "metric": "isup_spearman", "valid_draws": isup_valid, "ci_low": isup_ci_low, "ci_high": isup_ci_high},
        {"encoder": encoder, "universe": "concordant92", "metric": "isup_spearman", "valid_draws": isup_92_valid, "ci_low": isup_92_low, "ci_high": isup_92_high},
    ]
    interval_rows.extend(
        {"encoder": encoder, "universe": "all95", "metric": metric, "valid_draws": survival_valid, "ci_low": values[0], "ci_high": values[1]}
        for metric, values in survival_intervals.items()
    )
    intervals = pd.DataFrame(interval_rows)
    summary: dict[str, object] = {
        "encoder": encoder,
        "n_subjects": len(external_subject),
        "n_events": int(external_event.sum()),
        "n_slides": int(external_subject.n_slides.sum()),
        "isup_spearman_all95": isup_rho,
        "isup_spearman_all95_ci_low": isup_ci_low,
        "isup_spearman_all95_ci_high": isup_ci_high,
        "isup_spearman_concordant92": isup_92,
        "isup_spearman_concordant92_ci_low": isup_92_low,
        "isup_spearman_concordant92_ci_high": isup_92_high,
        "full_c_index": full_c,
        "full_c_index_ci_low": survival_intervals["full_c_index"][0],
        "full_c_index_ci_high": survival_intervals["full_c_index"][1],
        "target_erased_c_index": target_c,
        "target_delta_use": target_delta,
        "target_delta_use_ci_low": survival_intervals["target_delta_use"][0],
        "target_delta_use_ci_high": survival_intervals["target_delta_use"][1],
        "random_delta_p95": random_p95,
        "target_vs_random_permutation_p_one_sided": p_value,
        "random_removed_variance_ratio_median": float(np.median(variance_ratios)),
        "random_concept_abs_cosine_median": float(np.median(concept_cosines)),
    }
    return predictions, pd.DataFrame(random_rows), intervals, summary


def _runtime_environment() -> dict[str, object]:
    packages = {}
    for name in ["numpy", "pandas", "scipy", "scikit-learn", "scikit-survival", "torch", "timm", "tifffile", "Pillow"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not_installed"
    gpu: dict[str, object] = {"cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "unset")}
    try:
        import torch

        gpu.update(
            {
                "torch_cuda": torch.version.cuda,
                "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unavailable",
                "device_count_visible": torch.cuda.device_count(),
            }
        )
    except Exception as error:
        gpu["error"] = repr(error)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "gpu": gpu,
    }


def model_provenance() -> dict[str, dict[str, object]]:
    locked = pd.read_csv(INTERNAL_OUTPUTS / "fm6_tcga_embedding_technical_qc.csv").set_index(
        "encoder"
    )
    provenance: dict[str, dict[str, object]] = {}
    for encoder in ("conch", "virchow"):
        spec = INTERNAL_RUNNER.model_spec(encoder)
        weights = Path(spec["weights"])
        observed_weight_sha256 = sha256_file(weights)
        expected_weight_sha256 = str(locked.loc[encoder, "weights_sha256"])
        if observed_weight_sha256 != expected_weight_sha256:
            raise RuntimeError(f"{encoder} weight hash changed from locked TCGA extraction")
        provenance[encoder] = {
            "model_id": str(spec["model_id"]),
            "model_revision": str(spec["revision"]),
            "weights_sha256": observed_weight_sha256,
            "dimension": DIMENSION[encoder],
            "tile_embedding_sha256": sha256_file(
                ARTIFACTS / f"fm6_chimera_{encoder}_tile_embeddings.npy"
            ),
            "decoded_crop_hash_array_sha256": sha256_file(
                ARTIFACTS / f"fm6_chimera_{encoder}_crop_hashes.npy"
            ),
        }
    return provenance


def internal_report(summary: pd.DataFrame, overall_status: str) -> str:
    lines = [
        "# FM6 CHIMERA external functional XAI failure decomposition",
        "",
        "**INTERNAL EMBARGO-CONTROLLED RESULT — NOT FOR PUBLICATION OR MANUSCRIPT USE**",
        "",
        f"Publication status: `{EMBARGO_STATUS}`. CHIMERA BCR uses postoperative PSA >=0.1 µg/L and months; endpoint equivalence to TCGA is not asserted. Official tissue masks are not tumor masks. Results are whole-tissue only and precision is constrained by 27 events.",
        "",
        f"Overall locked status: **{overall_status}**",
        "",
    ]
    for row in summary.itertuples(index=False):
        lines.extend(
            [
                f"## {row.encoder}",
                "",
                f"- ISUP all-95 rho: {row.isup_spearman_all95:.6f} (95% CI {row.isup_spearman_all95_ci_low:.6f} to {row.isup_spearman_all95_ci_high:.6f})",
                f"- ISUP concordant-92 rho: {row.isup_spearman_concordant92:.6f} (95% CI {row.isup_spearman_concordant92_ci_low:.6f} to {row.isup_spearman_concordant92_ci_high:.6f})",
                f"- Full BCR-head C-index: {row.full_c_index:.6f} (95% CI {row.full_c_index_ci_low:.6f} to {row.full_c_index_ci_high:.6f})",
                f"- Target-erased C-index: {row.target_erased_c_index:.6f}",
                f"- Target delta_use: {row.target_delta_use:.6f} (95% CI {row.target_delta_use_ci_low:.6f} to {row.target_delta_use_ci_high:.6f})",
                f"- Matched-random p95: {row.random_delta_p95:.6f}; permutation p={row.target_vs_random_permutation_p_one_sided:.6f}; Holm p={row.target_vs_random_p_holm:.6f}",
                f"- Gates: ISUP={row.isup_recoverability_gate_pass}; BCR head={row.bcr_head_validity_gate_pass}; functional erasure={row.functional_erasure_gate_pass}",
                f"- Cause state: `{row.cause_state}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim boundary",
            "",
            "These numbers are internal embargo-controlled evidence, not public results. They do not establish tumor-specific mechanism, clinical deployment, clinical increment, endpoint equivalence, encoder superiority, indispensability, or a new biomarker.",
            "",
        ]
    )
    return "\n".join(lines)


def analyze(run_id: str) -> dict[str, object]:
    if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in run_id):
        raise ValueError("run_id must use lowercase ASCII letters, digits, underscore, or hyphen")
    started = time.time()
    audit = paired_embedding_audit()
    if audit["status"] != "PASS":
        raise RuntimeError("CHIMERA paired embedding integrity failure")
    run_root = ARTIFACTS / "analysis_runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    prediction_frames = []
    random_frames = []
    interval_frames = []
    summaries: dict[str, dict[str, object]] = {}
    for encoder in ("conch", "virchow"):
        print(f"CHIMERA failure decomposition: {encoder}", flush=True)
        predictions, random_controls, intervals, summary = analyze_encoder(encoder)
        prediction_frames.append(predictions)
        random_frames.append(random_controls)
        interval_frames.append(intervals)
        summaries[encoder] = summary
    adjusted = SITE_ANALYSIS.holm_adjust(
        {
            encoder: float(values["target_vs_random_permutation_p_one_sided"])
            for encoder, values in summaries.items()
        }
    )
    rows = []
    evidence_rows = []
    for encoder in ("conch", "virchow"):
        row = dict(summaries[encoder])
        row["target_vs_random_p_holm"] = adjusted[encoder]
        row["isup_recoverability_gate_pass"] = bool(row["isup_spearman_all95_ci_low"] > 0)
        row["bcr_head_validity_gate_pass"] = bool(row["full_c_index_ci_low"] > 0.50)
        row["target_delta_ci_gate_pass"] = bool(row["target_delta_use_ci_low"] > 0)
        row["target_exceeds_random_p95_gate_pass"] = bool(
            row["target_delta_use"] > row["random_delta_p95"]
        )
        row["multiplicity_gate_pass"] = bool(row["target_vs_random_p_holm"] <= 0.05)
        row["functional_erasure_gate_pass"] = bool(
            row["bcr_head_validity_gate_pass"]
            and row["target_delta_ci_gate_pass"]
            and row["target_exceeds_random_p95_gate_pass"]
            and row["multiplicity_gate_pass"]
        )
        row["cause_state"] = classify_cause(row)
        rows.append(row)
        evidence_rows.append(
            {
                "encoder": encoder,
                "external_isup_recoverability": "PASS" if row["isup_recoverability_gate_pass"] else "FAIL_OR_INCONCLUSIVE",
                "external_bcr_head_validity": "PASS" if row["bcr_head_validity_gate_pass"] else "FAIL_OR_INCONCLUSIVE",
                "external_functional_erasure": "PASS" if row["functional_erasure_gate_pass"] else "FAIL_OR_INCONCLUSIVE",
                "cause_state": row["cause_state"],
                "whole_tissue_only": True,
                "tumor_specific_mechanism": "PROHIBITED",
                "clinical_deployment": "PROHIBITED",
                "publication_status": EMBARGO_STATUS,
            }
        )
    summary = pd.DataFrame(rows)
    overall_status = min(
        summary.cause_state,
        key=lambda value: CAUSE_STATES[str(value)],
    )
    evidence = pd.DataFrame(evidence_rows)
    evidence["overall_status"] = overall_status

    outputs = {
        "fm6_chimera_patient_predictions.csv": pd.concat(prediction_frames, ignore_index=True),
        "fm6_chimera_matched_random_controls.csv": pd.concat(random_frames, ignore_index=True),
        "fm6_chimera_bootstrap_intervals.csv": pd.concat(interval_frames, ignore_index=True),
        "fm6_chimera_external_summary.csv": summary,
        "fm6_chimera_external_evidence_chain.csv": evidence,
    }
    for filename, frame in outputs.items():
        frame.to_csv(run_root / filename, index=False, lineterminator="\n")
    report_path = run_root / "fm6-chimera-external-functional-xai-internal-report.md"
    report_path.write_text(internal_report(summary, str(overall_status)), encoding="utf-8")
    output_names = sorted([*outputs, report_path.name])
    config = {
        "protocol": "fm6-chimera-external-functional-xai-protocol",
        "run_id": run_id,
        "finished_at_utc": utc_now(),
        "runtime_seconds": round(time.time() - started, 6),
        "preregistration_code_commit": git_head(),
        "runner_sha256": sha256_file(Path(__file__)),
        "seed": SEED,
        "pca_components": PCA_COMPONENTS,
        "ridge_alpha": RIDGE_ALPHA,
        "cox_alpha": COX_ALPHA,
        "random_controls": RANDOM_CONTROLS,
        "bootstraps": BOOTSTRAPS,
        "subjects": EXPECTED_SUBJECTS,
        "events": EXPECTED_EVENTS,
        "wsi": EXPECTED_WSI,
        "masks": EXPECTED_MASKS,
        "crops": EXPECTED_TILES,
        "primary_aggregation": "crop_mean_then_equal_weight_slide_mean_per_patient",
        "publication_status": EMBARGO_STATUS,
        "publication_gate_checked_on": PUBLICATION_GATE_CHECKED_ON,
        "publication_gate_urls": PUBLICATION_GATE_URLS,
        "publication_gate_rule": PUBLICATION_GATE_RULE,
        "result_visibility": "internal_embargo_controlled_local_artifact_only",
        "target_cohort_tuning": "PROHIBITED",
        "overall_status": overall_status,
        "claim_ceiling": "internal embargo-controlled external whole-tissue failure decomposition only; publication, tumor-specific mechanism, endpoint equivalence, clinical deployment, clinical increment, encoder superiority, and new biomarker claims prohibited",
        "input_sha256": verify_locked_inputs(),
        "preparation_lock_sha256": sha256_file(ARTIFACTS / "fm6_chimera_preparation_lock.json"),
        "paired_embedding_audit_sha256": sha256_file(ARTIFACTS / "fm6_chimera_paired_embedding_audit.json"),
        "environment": _runtime_environment(),
        "model_provenance": model_provenance(),
        "nonvolatile_output_sha256": {
            name: sha256_file(run_root / name) for name in output_names
        },
        "volatile_fields": ["run_id", "finished_at_utc", "runtime_seconds"],
    }
    (run_root / "fm6_chimera_external_run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(config, indent=2, sort_keys=True), flush=True)
    return config


def compare_clean_rerun(first_run_id: str, second_run_id: str) -> dict[str, object]:
    configs = []
    for run_id in (first_run_id, second_run_id):
        path = ARTIFACTS / "analysis_runs" / run_id / "fm6_chimera_external_run_config.json"
        configs.append(json.loads(path.read_text(encoding="utf-8")))
    identical = configs[0]["nonvolatile_output_sha256"] == configs[1]["nonvolatile_output_sha256"]
    record = {
        "status": "PASS" if identical else "FAIL",
        "first_run_id": first_run_id,
        "second_run_id": second_run_id,
        "nonvolatile_output_hashes_exactly_identical": identical,
        "first_hashes": configs[0]["nonvolatile_output_sha256"],
        "second_hashes": configs[1]["nonvolatile_output_sha256"],
        "checked_at_utc": utc_now(),
        "volatile_fields": ["checked_at_utc"],
    }
    (ARTIFACTS / "fm6_chimera_clean_rerun_audit.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not identical:
        raise RuntimeError("CHIMERA clean-rerun nonvolatile output hash mismatch")
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=[
            "verify-source",
            "prepare",
            "prepare-crops",
            "extract",
            "assemble",
            "audit",
            "analyze",
            "compare-rerun",
        ],
        required=True,
    )
    parser.add_argument("--encoder", choices=["conch", "virchow"])
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--full-hash", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--run-id", default="primary")
    parser.add_argument("--first-run-id", default="primary")
    parser.add_argument("--second-run-id", default="clean_rerun")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stage == "verify-source":
        print(json.dumps(verify_source(args.full_hash), indent=2, sort_keys=True))
    elif args.stage == "prepare":
        print(json.dumps(prepare(), indent=2, sort_keys=True))
    elif args.stage == "prepare-crops":
        prepare_crops(args.shard_index, args.shard_count)
    elif args.stage == "extract":
        if args.encoder is None:
            raise ValueError("--encoder is required for extract")
        extract(args.encoder, args.smoke_only, args.shard_index, args.shard_count)
    elif args.stage == "assemble":
        if args.encoder is None:
            raise ValueError("--encoder is required for assemble")
        assemble(args.encoder)
    elif args.stage == "audit":
        print(json.dumps(paired_embedding_audit(), indent=2, sort_keys=True))
    elif args.stage == "analyze":
        analyze(args.run_id)
    else:
        print(
            json.dumps(
                compare_clean_rerun(args.first_run_id, args.second_run_id),
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
