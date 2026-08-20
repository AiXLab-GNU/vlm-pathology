#!/usr/bin/env python3
"""Prepare, extract, and analyze locked LEOPARD external functional XAI evidence."""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
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
MILESTONE = PROJECT / "milestones/fm6_external_functional_validation"
OUTPUTS = MILESTONE / "outputs"
ARTIFACTS = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_external_functional_validation"
LEOPARD = ROOT / "resources/data/shared/opendataset/LEOPARD"
SLIDES = LEOPARD / "training"
LABELS = LEOPARD / "training_labels.csv"
DATASET_MANIFEST = ROOT / "resources/data/manifests/leopard.yaml"
INTERNAL_MILESTONE = PROJECT / "milestones/fm6_internal_development_pilot"
INTERNAL_OUTPUTS = INTERNAL_MILESTONE / "outputs"
INTERNAL_ARTIFACTS = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot"


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


INTERNAL_RUNNER = load_module(
    "fm6_internal_runner", INTERNAL_MILESTONE / "run_fm6_tcga_internal_pilot.py"
)
INTERNAL_ANALYSIS = load_module(
    "fm6_internal_analysis", INTERNAL_MILESTONE / "analyze_fm6_tcga_internal_pilot.py"
)
SITE_ANALYSIS = load_module(
    "fm6_site_analysis",
    PROJECT
    / "milestones/fm6_site_heldout_functional_validation/run_fm6_site_heldout_functional_xai.py",
)

SEED = 260820
FOV_UM = 394.24
MAX_TILES = 64
MIN_TILES = 16
TISSUE_FRACTION_PRIMARY = 0.35
TISSUE_FRACTION_FALLBACK = 0.15
DIMENSION = {"conch": 512, "virchow": 2560}
BATCH_SIZE = {"conch": 64, "virchow": 64}
EXPECTED_SUBJECTS = 508
EXPECTED_EVENTS = 87
MIN_EVALUABLE_EVENTS = 80
RANDOM_CONTROLS = 100
BOOTSTRAPS = 2000
RIDGE_ALPHA = 1000.0
COX_ALPHA = 1000.0
EXPECTED_LABELS_SHA256 = "04d8229b58348a317790d279ae134d84f6a795ab956fd52208c08f2279ff1186"
EXPECTED_INTERNAL_SHA256 = {
    "development_subjects.csv": "c36bfc442f6f33aaa6887eb6882c62f8984561e2336a35b6ab30eab370e1d814",
    "fm6_tcga_conch_tile_embeddings.npy": "99c6d5f3bc59070a7c2e74f3c6f3adc3f7f8db5cf6d8837465bde955953e9d2d",
    "fm6_tcga_virchow_tile_embeddings.npy": "4e23555436084c1154dbfdd94df86ddff556617fa41864615fb505f438f17ca7",
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


def expected_source_paths(case_id: str) -> tuple[Path, Path]:
    if not str(case_id).endswith(".tif") or "case_radboud_" not in str(case_id):
        raise ValueError(f"unexpected LEOPARD case id: {case_id}")
    return SLIDES / case_id, SLIDES / case_id.replace(".tif", "_tissue.tif")


def verify_source_membership() -> pd.DataFrame:
    if sha256_file(LABELS) != EXPECTED_LABELS_SHA256:
        raise RuntimeError("LEOPARD label hash changed")
    labels = pd.read_csv(LABELS)
    if len(labels) != EXPECTED_SUBJECTS or labels.case_id.nunique() != EXPECTED_SUBJECTS:
        raise RuntimeError("LEOPARD subject universe changed")
    if int(labels.event.sum()) != EXPECTED_EVENTS:
        raise RuntimeError("LEOPARD event universe changed")
    rows = []
    for row in labels.itertuples(index=False):
        image, mask = expected_source_paths(row.case_id)
        if not image.is_file() or not mask.is_file():
            raise FileNotFoundError(f"missing LEOPARD image/mask pair: {row.case_id}")
        rows.append(
            {
                "case_id": row.case_id,
                "wsi_local_relative_path": str(image.relative_to(ROOT)),
                "wsi_bytes": image.stat().st_size,
                "mask_local_relative_path": str(mask.relative_to(ROOT)),
                "mask_bytes": mask.stat().st_size,
            }
        )
    return pd.DataFrame(rows)


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
            fraction = mask_fraction(mask, cx - half_x, cy - half_y, cx + half_x, cy + half_y)
            if fraction >= threshold:
                choices.append((cx, cy, fraction))
    return choices


def prepare_case(case_id: str, image: Path, mask_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    with tifffile.TiffFile(image) as tif, tifffile.TiffFile(mask_path) as mask_tif:
        base = tif.series[0].levels[0].pages[0]
        mpp = INTERNAL_RUNNER.native_mpp(base)
        crop_px = int(round(FOV_UM / mpp))
        mask = np.asarray(mask_tif.pages[0].asarray())
        choices = candidate_coordinates(
            mask, base.imagewidth, base.imagelength, crop_px, TISSUE_FRACTION_PRIMARY, 1
        )
        selection_rule = "primary"
        if len(choices) < MIN_TILES:
            choices = candidate_coordinates(
                mask, base.imagewidth, base.imagelength, crop_px, TISSUE_FRACTION_FALLBACK, 2
            )
            selection_rule = "fallback"
        rng = stable_rng(case_id)
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
                    "case_id": case_id,
                    "tile_rank": rank,
                    "tile_id": f"{case_id}:{rank:03d}",
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
            "case_id": case_id,
            "width_px": int(base.imagewidth),
            "height_px": int(base.imagelength),
            "mpp": mpp,
            "crop_px": crop_px,
            "mask_width": int(mask.shape[1]),
            "mask_height": int(mask.shape[0]),
            "candidate_count": len(choices),
            "selected_count": len(selected),
            "selection_rule": selection_rule,
            "sampling_status": "PASS" if len(selected) >= MIN_TILES else "INSUFFICIENT_TISSUE",
        }
        return records, audit


def prepare() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    inventory = verify_source_membership()
    inventory.to_csv(ARTIFACTS / "fm6_leopard_source_inventory.csv", index=False, lineterminator="\n")
    rows = []
    audits = []
    embedding_row = 0
    for number, source in enumerate(inventory.itertuples(index=False), 1):
        records, audit = prepare_case(
            source.case_id, ROOT / source.wsi_local_relative_path, ROOT / source.mask_local_relative_path
        )
        audits.append(audit)
        if audit["sampling_status"] == "PASS":
            for record in records:
                rows.append({"embedding_row": embedding_row, **record})
                embedding_row += 1
        if number % 20 == 0 or number == len(inventory):
            print(f"prepare LEOPARD {number}/{len(inventory)}; {embedding_row} crops", flush=True)
    manifest = pd.DataFrame(rows)
    audit = pd.DataFrame(audits)
    if manifest.tile_id.duplicated().any() or not manifest.embedding_row.equals(pd.Series(np.arange(len(manifest)))):
        raise RuntimeError("LEOPARD tile identity/order failure")
    manifest.to_csv(ARTIFACTS / "fm6_leopard_tile_manifest.csv", index=False, lineterminator="\n")
    audit.to_csv(ARTIFACTS / "fm6_leopard_sampling_qc.csv", index=False, lineterminator="\n")
    evaluable = set(manifest.case_id.unique())
    labels = pd.read_csv(LABELS)
    evaluable_events = int(labels[labels.case_id.isin(evaluable)].event.sum())
    if evaluable_events < MIN_EVALUABLE_EVENTS:
        raise RuntimeError(f"only {evaluable_events} evaluable external events")
    lock = {
        "protocol": "fm6-leopard-external-functional-xai-protocol",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "physical_fov_um": FOV_UM,
        "max_tiles_per_wsi": MAX_TILES,
        "min_tiles_per_wsi": MIN_TILES,
        "source_subjects": len(labels),
        "source_events": int(labels.event.sum()),
        "evaluable_subjects": len(evaluable),
        "evaluable_events": evaluable_events,
        "evaluable_tiles": len(manifest),
        "labels_sha256": sha256_file(LABELS),
        "source_inventory_sha256": sha256_file(ARTIFACTS / "fm6_leopard_source_inventory.csv"),
        "tile_manifest_sha256": sha256_file(ARTIFACTS / "fm6_leopard_tile_manifest.csv"),
        "sampling_qc_sha256": sha256_file(ARTIFACTS / "fm6_leopard_sampling_qc.csv"),
        "publication_clearance": "accountable_author_confirmed_embargo_complete_2026-08-20",
        "external_clearance_document": "unrecorded",
        "claim_ceiling": "external whole-tissue functional transport; external ISUP R, tumor-specific use, endpoint equivalence, clinical increment, and strong H2 prohibited",
        "volatile_fields": ["created_at_utc"],
    }
    (OUTPUTS / "fm6_leopard_preparation_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(lock, indent=2, sort_keys=True), flush=True)


def verify_preparation() -> tuple[pd.DataFrame, dict[str, object]]:
    lock = json.loads((OUTPUTS / "fm6_leopard_preparation_lock.json").read_text())
    paths = {
        "source_inventory_sha256": ARTIFACTS / "fm6_leopard_source_inventory.csv",
        "tile_manifest_sha256": ARTIFACTS / "fm6_leopard_tile_manifest.csv",
        "sampling_qc_sha256": ARTIFACTS / "fm6_leopard_sampling_qc.csv",
    }
    for field, path in paths.items():
        if sha256_file(path) != lock[field]:
            raise RuntimeError(f"LEOPARD preparation hash changed: {field}")
    if sha256_file(LABELS) != lock["labels_sha256"]:
        raise RuntimeError("LEOPARD labels changed after preparation")
    return pd.read_csv(ARTIFACTS / "fm6_leopard_tile_manifest.csv"), lock


def slide_cache_path(encoder: str, case_id: str) -> Path:
    return ARTIFACTS / "slide_cache" / encoder / f"{case_id.removesuffix('.tif')}.npz"


def canonical_crops(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    case_id = str(rows.case_id.iloc[0])
    image, _ = expected_source_paths(case_id)
    crops = []
    hashes = []
    with tifffile.TiffFile(image) as tif:
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


def extract(encoder: str, smoke_only: bool = False) -> None:
    import torch

    manifest, _ = verify_preparation()
    device = INTERNAL_RUNNER.configure_device()
    model, _ = INTERNAL_RUNNER.load_model(encoder, device)
    first_rows = next(iter(manifest.groupby("case_id", sort=False)))[1]
    first_crops, _ = canonical_crops(first_rows.iloc[: min(4, len(first_rows))])
    tensor = INTERNAL_RUNNER.transform_canonical_batch(encoder, first_crops, device)
    with torch.inference_mode():
        first = INTERNAL_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
        second = INTERNAL_RUNNER.embed_batch(encoder, model, tensor).detach().cpu().float().numpy()
    if not np.array_equal(first, second) or first.shape != (len(first_crops), DIMENSION[encoder]):
        raise RuntimeError(f"{encoder} LEOPARD deterministic smoke failed")
    print(json.dumps({"encoder": encoder, "smoke_shape": list(first.shape), "exact_repeat": True}), flush=True)
    if smoke_only:
        return

    cache_root = ARTIFACTS / "slide_cache" / encoder
    cache_root.mkdir(parents=True, exist_ok=True)
    grouped = list(manifest.groupby("case_id", sort=False))
    for complete, (case_id, rows) in enumerate(grouped, 1):
        destination = slide_cache_path(encoder, case_id)
        if destination.exists():
            with np.load(destination, allow_pickle=False) as cached:
                valid = (
                    cached["embedding"].shape == (len(rows), DIMENSION[encoder])
                    and np.array_equal(cached["tile_id"].astype(str), rows.tile_id.to_numpy(str))
                    and np.isfinite(cached["embedding"]).all()
                )
            if valid:
                if complete % 20 == 0 or complete == len(grouped):
                    print(f"{encoder} LEOPARD {complete}/{len(grouped)} cached", flush=True)
                continue
        crops, hashes = canonical_crops(rows)
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
            raise RuntimeError(f"invalid {encoder} LEOPARD embeddings: {case_id}")
        with tempfile.NamedTemporaryFile(dir=cache_root, suffix=".npz", delete=False) as handle:
            temporary = Path(handle.name)
        np.savez_compressed(
            temporary,
            tile_id=rows.tile_id.to_numpy(str),
            embedding=embeddings,
            level0_crop_sha256=hashes,
        )
        os.replace(temporary, destination)
        if complete % 10 == 0 or complete == len(grouped):
            print(f"{encoder} LEOPARD {complete}/{len(grouped)}", flush=True)
    del model, tensor
    gc.collect()
    torch.cuda.empty_cache()
    assemble(encoder)


def assemble(encoder: str) -> None:
    manifest, _ = verify_preparation()
    embeddings = np.empty((len(manifest), DIMENSION[encoder]), dtype=np.float32)
    hashes = np.empty(len(manifest), dtype="U64")
    for case_id, rows in manifest.groupby("case_id", sort=False):
        with np.load(slide_cache_path(encoder, case_id), allow_pickle=False) as cached:
            if not np.array_equal(cached["tile_id"].astype(str), rows.tile_id.to_numpy(str)):
                raise RuntimeError(f"{encoder} LEOPARD tile order mismatch: {case_id}")
            position = rows.embedding_row.to_numpy(int)
            embeddings[position] = cached["embedding"]
            hashes[position] = cached["level0_crop_sha256"]
    np.save(ARTIFACTS / f"fm6_leopard_{encoder}_tile_embeddings.npy", embeddings, allow_pickle=False)
    np.save(ARTIFACTS / f"fm6_leopard_{encoder}_crop_hashes.npy", hashes, allow_pickle=False)


def paired_embedding_audit() -> dict[str, object]:
    manifest, _ = verify_preparation()
    conch_hashes = np.load(ARTIFACTS / "fm6_leopard_conch_crop_hashes.npy", allow_pickle=False)
    virchow_hashes = np.load(ARTIFACTS / "fm6_leopard_virchow_crop_hashes.npy", allow_pickle=False)
    conch = np.load(ARTIFACTS / "fm6_leopard_conch_tile_embeddings.npy", mmap_mode="r", allow_pickle=False)
    virchow = np.load(ARTIFACTS / "fm6_leopard_virchow_tile_embeddings.npy", mmap_mode="r", allow_pickle=False)
    audit = {
        "rows": len(manifest),
        "subjects": int(manifest.case_id.nunique()),
        "tile_ids_unique": bool(not manifest.tile_id.duplicated().any()),
        "row_order_locked": bool(manifest.embedding_row.equals(pd.Series(np.arange(len(manifest))))),
        "crop_hashes_identical_across_encoders": bool(np.array_equal(conch_hashes, virchow_hashes)),
        "conch_shape": list(conch.shape),
        "virchow_shape": list(virchow.shape),
    }
    audit["status"] = "PASS" if all(
        [
            audit["subjects"] == EXPECTED_SUBJECTS,
            audit["tile_ids_unique"],
            audit["row_order_locked"],
            audit["crop_hashes_identical_across_encoders"],
            conch.shape == (len(manifest), DIMENSION["conch"]),
            virchow.shape == (len(manifest), DIMENSION["virchow"]),
        ]
    ) else "FAIL"
    (OUTPUTS / "fm6_leopard_paired_embedding_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def load_external_subject_data(encoder: str) -> tuple[pd.DataFrame, np.ndarray]:
    manifest, _ = verify_preparation()
    array = np.load(
        ARTIFACTS / f"fm6_leopard_{encoder}_tile_embeddings.npy", mmap_mode="r", allow_pickle=False
    )
    if len(array) != len(manifest):
        raise RuntimeError(f"{encoder} external embedding row mismatch")
    vectors = []
    rows = []
    for case_id, group in manifest.groupby("case_id", sort=True):
        vectors.append(np.asarray(array[group.embedding_row.to_numpy(int)], dtype=np.float64).mean(axis=0))
        rows.append({"case_id": case_id, "n_tiles": len(group)})
    subject = pd.DataFrame(rows).merge(pd.read_csv(LABELS), on="case_id", validate="one_to_one")
    x = np.stack(vectors)
    order = subject.case_id.argsort(kind="stable").to_numpy()
    return subject.iloc[order].reset_index(drop=True), x[order]


def analyze_encoder(encoder: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    internal_subject, internal_x, _ = INTERNAL_ANALYSIS.load_subject_data(encoder)
    external_subject, external_x = load_external_subject_data(encoder)
    internal_event = internal_subject.bcr_event.to_numpy(int)
    internal_time = internal_subject.bcr_time_days.to_numpy(float)
    internal_isup = internal_subject.isup_grade_group.to_numpy(float)
    external_event = external_subject.event.to_numpy(int)
    external_time = external_subject.follow_up_years.to_numpy(float)
    if len(external_subject) != EXPECTED_SUBJECTS or int(external_event.sum()) != EXPECTED_EVENTS:
        raise RuntimeError("external analysis universe changed")

    model = SITE_ANALYSIS.fit_head(internal_x, internal_event, internal_time)
    scaler = model[0]
    internal_scaled = scaler.transform(internal_x)
    external_scaled = scaler.transform(external_x)
    direction = Ridge(alpha=RIDGE_ALPHA).fit(internal_scaled, internal_isup).coef_.astype(float)
    full_risk = SITE_ANALYSIS.predict_standardized_head(model, external_x)
    target_risk = SITE_ANALYSIS.predict_scaled_head(
        model, INTERNAL_ANALYSIS.erase_direction(external_scaled, direction)
    )
    rng = np.random.default_rng(SEED + (1000 if encoder == "conch" else 2000))
    random_directions, variance_ratios, concept_cosines = INTERNAL_ANALYSIS.variance_matched_random_directions(
        internal_scaled, direction, RANDOM_CONTROLS, rng
    )
    random_risk = np.empty((RANDOM_CONTROLS, len(external_subject)), dtype=np.float64)
    for draw, random_direction in enumerate(random_directions):
        random_risk[draw] = SITE_ANALYSIS.predict_scaled_head(
            model, INTERNAL_ANALYSIS.erase_direction(external_scaled, random_direction)
        )
    full_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, full_risk)
    target_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, target_risk)
    target_delta = full_c - target_c
    random_rows = []
    random_deltas = np.empty(RANDOM_CONTROLS, dtype=float)
    for draw in range(RANDOM_CONTROLS):
        random_c = SITE_ANALYSIS.ordinary_c_index(external_event, external_time, random_risk[draw])
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

    rng_bootstrap = np.random.default_rng(SEED + (10 if encoder == "conch" else 20))
    bootstrap_rows = []
    valid = 0
    while valid < BOOTSTRAPS:
        sample = rng_bootstrap.integers(0, len(external_subject), len(external_subject))
        try:
            full_draw = SITE_ANALYSIS.ordinary_c_index(
                external_event[sample], external_time[sample], full_risk[sample]
            )
            target_draw = SITE_ANALYSIS.ordinary_c_index(
                external_event[sample], external_time[sample], target_risk[sample]
            )
        except Exception:
            continue
        bootstrap_rows.append(
            {
                "encoder": encoder,
                "draw": valid,
                "full_c_index": full_draw,
                "target_erased_c_index": target_draw,
                "target_delta_use": full_draw - target_draw,
            }
        )
        valid += 1
    bootstrap = pd.DataFrame(bootstrap_rows)
    full_ci = np.quantile(bootstrap.full_c_index, [0.025, 0.975])
    delta_ci = np.quantile(bootstrap.target_delta_use, [0.025, 0.975])
    p_value = float((1 + np.sum(random_deltas >= target_delta)) / (RANDOM_CONTROLS + 1))
    predictions = external_subject.copy()
    predictions["encoder"] = encoder
    predictions["full_risk"] = full_risk
    predictions["target_erased_risk"] = target_risk
    summary = {
        "n_subjects": float(len(external_subject)),
        "n_events": float(external_event.sum()),
        "full_c_index": full_c,
        "full_c_index_ci_low": float(full_ci[0]),
        "full_c_index_ci_high": float(full_ci[1]),
        "target_erased_c_index": target_c,
        "target_delta_use": target_delta,
        "target_delta_use_ci_low": float(delta_ci[0]),
        "target_delta_use_ci_high": float(delta_ci[1]),
        "random_delta_p95": float(np.quantile(random_deltas, 0.95)),
        "target_vs_random_p_one_sided": p_value,
        "random_removed_variance_ratio_median": float(np.median(variance_ratios)),
        "random_concept_abs_cosine_median": float(np.median(concept_cosines)),
    }
    intervals = pd.DataFrame(
        [
            {"encoder": encoder, "metric": "full_c_index", "valid_draws": BOOTSTRAPS, "ci_low": full_ci[0], "ci_high": full_ci[1]},
            {"encoder": encoder, "metric": "target_delta_use", "valid_draws": BOOTSTRAPS, "ci_low": delta_ci[0], "ci_high": delta_ci[1]},
        ]
    )
    return predictions, pd.DataFrame(random_rows), intervals, summary


def analyze() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if paired_embedding_audit()["status"] != "PASS":
        raise RuntimeError("LEOPARD paired embedding audit failed")
    prediction_frames = []
    random_frames = []
    interval_frames = []
    summaries: dict[str, dict[str, float]] = {}
    for encoder in ("conch", "virchow"):
        print(f"external functional analysis: {encoder}", flush=True)
        predictions, random_controls, intervals, summary = analyze_encoder(encoder)
        prediction_frames.append(predictions)
        random_frames.append(random_controls)
        interval_frames.append(intervals)
        summaries[encoder] = summary
    adjusted = SITE_ANALYSIS.holm_adjust(
        {encoder: summary["target_vs_random_p_one_sided"] for encoder, summary in summaries.items()}
    )
    summary_rows = []
    evidence_rows = []
    for encoder in ("conch", "virchow"):
        row = {"encoder": encoder, **summaries[encoder], "target_vs_random_p_holm": adjusted[encoder]}
        passed = bool(
            row["full_c_index_ci_low"] > 0.50
            and row["target_delta_use_ci_low"] > 0
            and row["target_vs_random_p_holm"] <= 0.05
            and row["n_events"] >= MIN_EVALUABLE_EVENTS
        )
        row["external_whole_tissue_functional_transport_pass"] = passed
        summary_rows.append(row)
        evidence_rows.append(
            {
                "encoder": encoder,
                "external_bcr_head_validity": "PASS" if row["full_c_index_ci_low"] > 0.50 else "FAIL_OR_INCONCLUSIVE",
                "external_whole_tissue_functional_transport": "PASS" if passed else "FAIL_OR_INCONCLUSIVE",
                "external_isup_recoverability": "NOT_TESTED_LABEL_UNAVAILABLE",
                "tumor_specific_functional_use": "NOT_TESTED",
                "endpoint_threshold_equivalence": "NOT_ESTABLISHED",
                "strong_H2": "PROHIBITED",
            }
        )
    summary_frame = pd.DataFrame(summary_rows)
    passes = int(summary_frame.external_whole_tissue_functional_transport_pass.sum())
    if passes == 2:
        overall_status = "PASS_REPLICATED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT"
    elif passes == 1:
        overall_status = "PARTIAL_ENCODER_SPECIFIC_EXTERNAL_FUNCTIONAL_TRANSPORT"
    else:
        overall_status = "FAIL_OR_INCONCLUSIVE_EXTERNAL_FUNCTIONAL_TRANSPORT"
    evidence = pd.DataFrame(evidence_rows)
    evidence["overall_status"] = overall_status

    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.to_csv(ARTIFACTS / "fm6_leopard_patient_predictions.csv", index=False, lineterminator="\n")
    pd.concat(random_frames, ignore_index=True).to_csv(
        OUTPUTS / "fm6_leopard_matched_random_controls.csv", index=False, lineterminator="\n"
    )
    pd.concat(interval_frames, ignore_index=True).to_csv(
        OUTPUTS / "fm6_leopard_bootstrap_intervals.csv", index=False, lineterminator="\n"
    )
    summary_frame.to_csv(OUTPUTS / "fm6_leopard_external_summary.csv", index=False, lineterminator="\n")
    evidence.to_csv(OUTPUTS / "fm6_leopard_external_evidence_chain.csv", index=False, lineterminator="\n")

    report = [
        "---",
        "document_id: fm6-leopard-external-functional-xai-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: generated",
        "created: 2026-08-20",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_external_functional_validation/outputs/fm6-leopard-external-functional-xai-report.md",
        "---",
        "",
        "# FM6 LEOPARD external functional XAI validation",
        "",
        "## Evidence scope",
        "",
        "This analysis applies TCGA-only locked heads and ISUP-correlated directions to the independent LEOPARD BCR cohort. LEOPARD lacks ISUP and treatment covariates; external ISUP recoverability, tumor-specific use, endpoint-threshold equivalence, clinical increment, and strong H2 therefore remain unestablished.",
        "",
        f"- External subjects/events: {EXPECTED_SUBJECTS}/{EXPECTED_EVENTS}",
        f"- Overall prespecified status: **{overall_status}**",
        "",
        "## Prespecified results",
        "",
    ]
    for row in summary_frame.itertuples(index=False):
        report.extend(
            [
                f"### {row.encoder}",
                "",
                f"- External full-head C-index: {row.full_c_index:.3f} (95% CI {row.full_c_index_ci_low:.3f}–{row.full_c_index_ci_high:.3f})",
                f"- Target-erased C-index: {row.target_erased_c_index:.3f}",
                f"- External delta_use: {row.target_delta_use:.3f} (95% CI {row.target_delta_use_ci_low:.3f}–{row.target_delta_use_ci_high:.3f})",
                f"- Matched-random p95: {row.random_delta_p95:.3f}; one-sided p={row.target_vs_random_p_one_sided:.4f}; Holm p={row.target_vs_random_p_holm:.4f}",
                f"- Encoder gate: {'PASS' if row.external_whole_tissue_functional_transport_pass else 'FAIL_OR_INCONCLUSIVE'}",
                "",
            ]
        )
    report.extend(
        [
            "## Locked interpretation",
            "",
            "The prespecified result is reported without target-cohort tuning. A positive gate supports independent external BCR transport of whole-tissue functional sensitivity only. It does not establish strong H2 or a tumor-specific human-equivalent mechanism.",
            "",
        ]
    )
    report_path = OUTPUTS / "fm6-leopard-external-functional-xai-report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    output_names = sorted(
        [
            "fm6_leopard_paired_embedding_audit.json",
            "fm6_leopard_matched_random_controls.csv",
            "fm6_leopard_bootstrap_intervals.csv",
            "fm6_leopard_external_summary.csv",
            "fm6_leopard_external_evidence_chain.csv",
            report_path.name,
        ]
    )
    config = {
        "protocol": "fm6-leopard-external-functional-xai-protocol",
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "pca_components": SITE_ANALYSIS.PCA_COMPONENTS,
        "ridge_alpha": RIDGE_ALPHA,
        "cox_alpha": COX_ALPHA,
        "random_controls": RANDOM_CONTROLS,
        "bootstraps": BOOTSTRAPS,
        "publication_clearance": "accountable_author_confirmed_embargo_complete_2026-08-20",
        "external_clearance_document": "unrecorded",
        "overall_status": overall_status,
        "claim_ceiling": "independent external BCR whole-tissue functional transport only; external ISUP R, tumor-specific use, endpoint equivalence, clinical increment, and strong H2 prohibited",
        "preparation_lock_sha256": sha256_file(OUTPUTS / "fm6_leopard_preparation_lock.json"),
        "patient_predictions_sha256": sha256_file(ARTIFACTS / "fm6_leopard_patient_predictions.csv"),
        "output_sha256": {name: sha256_file(OUTPUTS / name) for name in output_names},
        "volatile_fields": ["finished_at_utc"],
    }
    (OUTPUTS / "fm6_leopard_external_run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(config, indent=2, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["prepare", "extract", "analyze", "all"], default="all")
    parser.add_argument("--encoder", choices=["conch", "virchow"])
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "extract":
        if args.encoder is None:
            raise ValueError("--encoder is required for extract")
        extract(args.encoder, smoke_only=args.smoke_only)
    elif args.stage == "analyze":
        analyze()
    else:
        prepare()
        for encoder in ("conch", "virchow"):
            extract(encoder)
        analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
