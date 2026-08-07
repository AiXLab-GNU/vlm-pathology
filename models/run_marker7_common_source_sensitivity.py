"""Run the frozen marker-7 common-498 source-membership sensitivity audit.

The public entry point is executed by the workspace ``.venv``.  The original
marker-7 Cox implementation depended on scikit-survival, which is preserved in
``models/.venv-conch`` but is not installed in the workspace environment.  To
avoid silently changing the frozen estimator, this controller validates and
hashes every input, invokes that exact pinned interpreter in an isolated worker
mode, validates the worker products, re-hashes the inputs, and publishes only a
complete result set.  No slide pixels, model weights, or GPUs are used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, NamedTuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
RUN_ROOT = ROOT / "models/stability_runs/full"

CELLS_NAME = "marker7_common_source_sensitivity_cells.csv"
DELTAS_NAME = "marker7_common_source_sensitivity_paired_deltas.csv"
MEMBERSHIP_NAME = "marker7_common_source_membership_manifest.csv"
CONFIG_NAME = "marker7_common_source_sensitivity_run_config.json"
MANIFEST_NAME = "marker7_common_source_sensitivity_run_manifest.csv"

TILE_COUNTS = (16, 32, 64)
ENCODER_MPPS = (("conch", (0.88, 1.76)), ("virchow", (0.44, 1.76)))
COMMON_SOURCE_COUNT = 498
SOURCE_UNION_COUNT = 502
COMMON_SOURCE_EVENTS = 85
TARGET_SLIDES = 297
TARGET_PATIENTS = 270
TARGET_EVENTS = 57
NULL_VALUE = 0.5
REPRODUCTION_ATOL = 1e-15
CONTRAST_CSV_ATOL = 2e-15

COMMON_SOURCE_ID_SHA256 = "3bf830ff8e7cdc0701c026a4d1425207661ce78e56812f532a5763e4b6eef32a"
SOURCE_UNION_ID_SHA256 = "d1f366c5cbb682454711ab25743cf8470dc0c17666a737f82bf8a8ac295b43b6"
TARGET_PATIENT_ID_SHA256 = "0a762215700364d916425cee8cd7e977309ea3ff829f1eb49ea9aed7d1c91267"
TARGET_SLIDE_CASE_ORDER_SHA256 = "85626cb673bbbb5e36ee7c8765b2cfca99acf1d4a2c97c15733bd75d4329b72f"
R1_RUN_MANIFEST_SHA256 = "10e5574bea12f3b8375ec12e5e9879e0d93aa6f79043e02797a9b4c09717ca4c"
FROZEN_EMBEDDING_LINEAGE_SHA256 = "2a5ecdc9df45383457c8d5309e1fa35ef3854996357d10aaf52494c9419191b8"

SOURCE_COLUMNS = ["case_id", "event", "follow_up_years", "n_tiles", "file_name", "path"]
TARGET_COLUMNS = ["file_name", "case_id", "path", "event", "follow_up_y"]

CELL_COLUMNS = [
    "cell_id", "marker", "canonical_cohort", "outcome_type", "primary_metric",
    "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
    "source_configuration_id", "n_original_source_patients",
    "n_common_source_patients", "n_source_events", "n_target_slides",
    "n_target_patients", "n_target_events", "n_target_folds", "saved_raw_c_index",
    "integrated_raw_c_index", "recomputed_raw_c_index",
    "raw_reproduction_error_vs_saved", "raw_reproduction_error_vs_integrated",
    "common_source_c_index", "common_minus_saved_raw", "raw_relation_to_null",
    "common_relation_to_null", "raw_common_null_crossing", "status",
]

DELTA_COLUMNS = [
    "contrast", "pair_id", "cell_id_a", "cell_id_b", "sampling_seed",
    "encoder_a", "encoder_b", "tiles_per_slide_a", "tiles_per_slide_b",
    "target_mpp_a", "target_mpp_b", "raw_metric_a", "raw_metric_b",
    "raw_delta_b_minus_a", "common498_metric_a", "common498_metric_b",
    "common498_delta_b_minus_a", "common_source_adjustment", "raw_direction",
    "common498_direction", "direction_status", "raw_null_crossing",
    "common498_null_crossing", "raw_exact_tie", "common498_exact_tie",
]

MEMBERSHIP_COLUMNS = [
    "source_configuration_id", "encoder", "sampling_seed", "target_mpp",
    "source_case_id", "retained_in_config", "source_row_index",
    "common_source_member", "common_row_index", "event", "follow_up_years",
    "outcome_consistency_status",
]

R1_CONTRAST_COLUMNS = [
    "contrast", "pair_id", "cell_id_a", "cell_id_b", "marker", "outcome_type",
    "primary_metric", "sampling_seed", "encoder_a", "encoder_b",
    "tiles_per_slide_a", "tiles_per_slide_b", "target_mpp_a", "target_mpp_b",
    "patient_metric_a", "patient_metric_b", "delta_b_minus_a", "null_value",
    "metric_direction", "relation_a", "relation_b", "null_crossing", "exact_tie",
]

RUN_MANIFEST_COLUMNS = [
    "artifact_kind", "artifact_role", "source_configuration_id", "artifact_path",
    "size_bytes", "mtime_ns", "rows", "array_shape", "array_dtype",
    "sha256_before", "sha256_after", "hash_reconciled", "controller_or_worker",
    "software_version", "included_in_output_hashes", "hash_exclusion_reason",
    "volatile_fields", "generated_at_utc", "elapsed_seconds",
]

WORKER_VERSIONS = {
    "python": "3.11.2",
    "numpy": "2.4.6",
    "pandas": "2.3.3",
    "scipy": "1.17.1",
    "sklearn": "1.9.0",
    "sksurv": "0.28.0",
}

CONTROLLER_VERSIONS = {
    "python": "3.11.2",
    "numpy": "2.4.6",
    "pandas": "3.0.3",
    "scipy": "1.17.1",
    "sklearn": "1.9.0",
}


class R2IntegrityError(RuntimeError):
    """Raised when the frozen R2 contract cannot be reconciled exactly."""


class SourceConfig(NamedTuple):
    config_id: str
    encoder_key: str
    encoder: str
    sampling_seed: int
    target_mpp: float
    source_meta: Path
    source_embeddings: Path
    target_meta: Path
    target_embeddings: Path


class InputAudit(NamedTuple):
    configs: list[SourceConfig]
    membership: pd.DataFrame
    common_ids: list[str]
    union_ids: list[str]
    target_summary: dict[str, Any]
    integrated_cells: pd.DataFrame
    contrasts: pd.DataFrame


def expected_configs(run_root: Path) -> list[SourceConfig]:
    configs: list[SourceConfig] = []
    for encoder_key, mpps in ENCODER_MPPS:
        encoder = "CONCH" if encoder_key == "conch" else "Virchow"
        directory = Path(run_root) / f"marker7_{encoder_key}"
        for seed in range(5):
            for mpp in mpps:
                suffix = f"s{seed}_mpp{mpp:.2f}"
                configs.append(SourceConfig(
                    config_id=f"{encoder_key}__s{seed}__mpp{mpp:.2f}",
                    encoder_key=encoder_key,
                    encoder=encoder,
                    sampling_seed=seed,
                    target_mpp=float(mpp),
                    source_meta=directory / f"source_meta_{suffix}.csv",
                    source_embeddings=directory / f"source_tile_embeddings_{suffix}.npy",
                    target_meta=directory / f"target_meta_{suffix}.csv",
                    target_embeddings=directory / f"target_tile_embeddings_{suffix}.npy",
                ))
    return configs


def expected_cell_ids() -> set[str]:
    return {
        f"marker7__{encoder_key}__s{seed}__t{tiles}__mpp{mpp:.2f}"
        for encoder_key, mpps in ENCODER_MPPS
        for seed in range(5)
        for mpp in mpps
        for tiles in TILE_COUNTS
    }


def discover_configs(run_root: Path) -> list[SourceConfig]:
    configs = expected_configs(run_root)
    expected_paths = {
        path.resolve()
        for config in configs
        for path in (
            config.source_meta, config.source_embeddings,
            config.target_meta, config.target_embeddings,
        )
    }
    for directory_name in ("marker7_conch", "marker7_virchow"):
        directory = Path(run_root) / directory_name
        for pattern in (
            "source_meta_s*_mpp*.csv", "source_tile_embeddings_s*_mpp*.npy",
            "target_meta_s*_mpp*.csv", "target_tile_embeddings_s*_mpp*.npy",
        ):
            for path in directory.glob(pattern):
                if path.resolve() not in expected_paths:
                    raise R2IntegrityError(f"unexpected source config artifact: {path}")
    missing = [str(path) for path in sorted(expected_paths) if not path.is_file()]
    if missing:
        raise R2IntegrityError(f"exact config files are incomplete: {missing[:5]}")
    return configs


def _require_exact_columns(frame: pd.DataFrame, expected: list[str], label: str) -> None:
    if list(frame.columns) != expected:
        raise R2IntegrityError(
            f"{label} header mismatch: expected {expected!r}, got {list(frame.columns)!r}"
        )


def _array_is_finite(array: np.ndarray, chunk_rows: int = 16) -> bool:
    for start in range(0, array.shape[0], chunk_rows):
        if not np.isfinite(np.asarray(array[start:start + chunk_rows])).all():
            return False
    return True


def validate_config_inputs(config: SourceConfig, *, scan_finite: bool) -> dict[str, Any]:
    source = pd.read_csv(config.source_meta)
    target = pd.read_csv(config.target_meta)
    _require_exact_columns(source, SOURCE_COLUMNS, "marker7 source metadata")
    _require_exact_columns(target, TARGET_COLUMNS, "marker7 target metadata")

    if source["case_id"].isna().any() or source["case_id"].astype(str).duplicated().any():
        raise R2IntegrityError("duplicate or missing source case_id")
    if source["file_name"].isna().any() or source["file_name"].astype(str).duplicated().any():
        raise R2IntegrityError("duplicate or missing source file_name")
    if source[["event", "follow_up_years", "n_tiles"]].isna().any().any():
        raise R2IntegrityError("missing source outcome or tile count")
    if not set(pd.to_numeric(source["event"], errors="coerce").unique()).issubset({0, 1}):
        raise R2IntegrityError("source event labels must be binary")
    follow_up = pd.to_numeric(source["follow_up_years"], errors="coerce").to_numpy(float)
    if not np.isfinite(follow_up).all() or (follow_up <= 0).any():
        raise R2IntegrityError("non-finite or non-positive source follow-up")
    if not pd.to_numeric(source["n_tiles"], errors="coerce").eq(64).all():
        raise R2IntegrityError("every source row must record exactly 64 tiles")

    if target[["file_name", "case_id", "event", "follow_up_y"]].isna().any().any():
        raise R2IntegrityError("missing target identity or outcome")
    if target["file_name"].astype(str).duplicated().any():
        raise R2IntegrityError("target file_name must be unique")
    target_event = pd.to_numeric(target["event"], errors="coerce").to_numpy(float)
    target_time = pd.to_numeric(target["follow_up_y"], errors="coerce").to_numpy(float)
    if not np.isfinite(target_event).all() or not np.isfinite(target_time).all():
        raise R2IntegrityError("non-finite target outcome")
    if not set(np.unique(target_event)).issubset({0, 1}) or (target_time <= 0).any():
        raise R2IntegrityError("invalid target event or follow-up")

    source_array = np.load(config.source_embeddings, mmap_mode="r")
    target_array = np.load(config.target_embeddings, mmap_mode="r")
    for label, array, rows in (
        ("source", source_array, len(source)), ("target", target_array, len(target)),
    ):
        if array.ndim != 3 or array.shape[0] != rows or array.shape[1] != 64:
            raise R2IntegrityError(f"{label} metadata/embedding alignment or tile shape mismatch")
        if array.dtype != np.dtype("float32"):
            raise R2IntegrityError(f"{label} embedding dtype must be float32")
        if scan_finite and not _array_is_finite(array):
            raise R2IntegrityError(f"non-finite {label} embedding")
    if source_array.shape[2] != target_array.shape[2]:
        raise R2IntegrityError("source/target embedding dimensions disagree")
    return {
        "source": source,
        "target": target,
        "source_shape": tuple(source_array.shape),
        "target_shape": tuple(target_array.shape),
        "dtype": str(source_array.dtype),
    }


def id_list_sha256(ids: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(map(str, ids))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ordered_slide_case_sha256(frame: pd.DataFrame) -> str:
    if not {"file_name", "case_id"}.issubset(frame.columns):
        raise R2IntegrityError("target slide identity columns are absent")
    payload = "".join(
        f"{file_name}\t{case_id}\n"
        for file_name, case_id in frame[["file_name", "case_id"]].astype(str).itertuples(
            index=False, name=None
        )
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_membership_manifest(
    frames: Mapping[str, tuple[SourceConfig, pd.DataFrame]],
    *,
    expected_common: int,
    expected_union: int,
    expected_common_events: int,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    sets = {key: set(frame["case_id"].astype(str)) for key, (_, frame) in frames.items()}
    if not sets:
        raise R2IntegrityError("no marker7 source frames")
    common_ids = sorted(set.intersection(*sets.values()))
    union_ids = sorted(set.union(*sets.values()))
    if len(common_ids) != expected_common or len(union_ids) != expected_union:
        raise R2IntegrityError(
            f"source membership mismatch: common={len(common_ids)}, union={len(union_ids)}"
        )

    canonical: dict[str, tuple[int, float]] = {}
    common_orders: list[list[str]] = []
    for config, frame in frames.values():
        frame = frame.reset_index(drop=True)
        common_orders.append(frame.loc[frame["case_id"].astype(str).isin(common_ids), "case_id"].astype(str).tolist())
        for row in frame.itertuples(index=False):
            case_id = str(row.case_id)
            value = (int(row.event), float(row.follow_up_years))
            if case_id in canonical and canonical[case_id] != value:
                raise R2IntegrityError(f"source outcome disagreement for {case_id}")
            canonical[case_id] = value
    if any(order != common_orders[0] for order in common_orders[1:]):
        raise R2IntegrityError("common source row order differs across configurations")
    if sum(canonical[case_id][0] for case_id in common_ids) != expected_common_events:
        raise R2IntegrityError("common source event count mismatch")

    # The worker applies a row-preserving positional mask to each source array.
    # Publish that filtered-array row index, not the lexical ID-list index used
    # solely for stable set hashing.
    common_index = {case_id: index for index, case_id in enumerate(common_orders[0])}
    rows: list[dict[str, Any]] = []
    for config_id, (config, frame) in frames.items():
        source_index = {str(case_id): index for index, case_id in enumerate(frame["case_id"])}
        for case_id in union_ids:
            retained = case_id in source_index
            event, follow_up = canonical[case_id]
            rows.append({
                "source_configuration_id": config_id,
                "encoder": config.encoder,
                "sampling_seed": config.sampling_seed,
                "target_mpp": config.target_mpp,
                "source_case_id": case_id,
                "retained_in_config": retained,
                "source_row_index": source_index.get(case_id, ""),
                "common_source_member": case_id in common_index,
                "common_row_index": common_index.get(case_id, ""),
                "event": event,
                "follow_up_years": follow_up,
                "outcome_consistency_status": "consistent" if retained else "not_retained",
            })
    return pd.DataFrame(rows), common_ids, union_ids


def validate_target_and_folds(
    targets: Mapping[str, tuple[SourceConfig, pd.DataFrame]],
    folds: pd.DataFrame,
    *,
    expected_slides: int,
    expected_patients: int,
    expected_events: int,
    expected_patient_hash: str,
    require_all_five_folds: bool,
    expected_slide_case_hash: str | None = None,
) -> dict[str, Any]:
    canonical: pd.DataFrame | None = None
    for _, target in targets.values():
        _require_exact_columns(target, TARGET_COLUMNS, "marker7 target metadata")
        values = target[["event", "follow_up_y"]].apply(pd.to_numeric, errors="coerce")
        if values.isna().any().any() or not np.isfinite(values.to_numpy(float)).all():
            raise R2IntegrityError("non-finite target outcome")
        if canonical is None:
            canonical = target.reset_index(drop=True)
        else:
            current = target.reset_index(drop=True)
            if not current[["case_id", "event", "follow_up_y"]].equals(
                canonical[["case_id", "event", "follow_up_y"]]
            ):
                raise R2IntegrityError("target outcome metadata disagree across configurations")
            if not current.equals(canonical):
                raise R2IntegrityError("target metadata rows differ across configurations")
    assert canonical is not None
    if len(canonical) != expected_slides:
        raise R2IntegrityError("target slide count mismatch")
    if canonical["file_name"].isna().any() or canonical["file_name"].astype(str).duplicated().any():
        raise R2IntegrityError("target file_name must be present and unique")
    if canonical["case_id"].isna().any():
        raise R2IntegrityError("target case_id is missing")
    slide_case_hash = ordered_slide_case_sha256(canonical)
    if expected_slide_case_hash is not None and slide_case_hash != expected_slide_case_hash:
        raise R2IntegrityError("target slide/case ordered membership hash mismatch")
    duplicated_outcomes = canonical.groupby("case_id")[["event", "follow_up_y"]].nunique(dropna=False)
    if (duplicated_outcomes > 1).any().any():
        raise R2IntegrityError("target outcome disagrees within patient")
    patient = canonical.drop_duplicates("case_id").copy()
    if len(patient) != expected_patients or int(patient["event"].sum()) != expected_events:
        raise R2IntegrityError("target patient/event count mismatch")
    patient_ids = sorted(patient["case_id"].astype(str))
    patient_hash = id_list_sha256(patient_ids)
    if patient_hash != expected_patient_hash:
        raise R2IntegrityError("target patient membership hash mismatch")

    marker_folds = folds.loc[folds["marker"].eq("marker7")].copy()
    if marker_folds["case_id"].astype(str).duplicated().any():
        raise R2IntegrityError("duplicate marker7 fold assignment")
    if set(marker_folds["case_id"].astype(str)) != set(patient_ids):
        raise R2IntegrityError("target and frozen fold patient sets disagree")
    marker_folds["fold"] = pd.to_numeric(marker_folds["fold"], errors="coerce")
    if marker_folds["fold"].isna().any() or not np.equal(marker_folds["fold"] % 1, 0).all():
        raise R2IntegrityError("marker7 folds must be integers")
    counts = marker_folds["fold"].astype(int).value_counts().sort_index()
    if require_all_five_folds and (counts.to_dict() != {index: 54 for index in range(5)}):
        raise R2IntegrityError("marker7 folds must be exactly 54 patients in folds 0-4")
    return {
        "n_target_slides": len(canonical),
        "n_target_patients": len(patient),
        "n_target_events": int(patient["event"].sum()),
        "n_target_folds": int(counts.size),
        "target_patient_id_sha256": patient_hash,
        "target_slide_case_order_sha256": slide_case_hash,
    }


def _validate_marker7_spec(spec: pd.DataFrame) -> None:
    marker = spec.loc[spec["marker"].eq("marker7")]
    if len(marker) != 60 or set(marker["cell_id"].astype(str)) != expected_cell_ids():
        raise R2IntegrityError("frozen marker7 spec does not contain the exact 60 cells")
    if not marker["status"].eq("pending").all():
        raise R2IntegrityError("frozen spec status was altered")


def _validate_integrated_cells(frame: pd.DataFrame) -> pd.DataFrame:
    marker = frame.loc[frame["marker"].eq("marker7")].copy()
    if len(marker) != 60 or marker["cell_id"].duplicated().any():
        raise R2IntegrityError("integrated marker7 cells must be 60 unique rows")
    if set(marker["cell_id"].astype(str)) != expected_cell_ids():
        raise R2IntegrityError("integrated marker7 cell set disagrees with the frozen spec")
    if not marker["reconciliation_status"].eq("reconciled").all():
        raise R2IntegrityError("integrated marker7 cells are not reconciled")
    if not np.isfinite(pd.to_numeric(marker["patient_metric"], errors="coerce")).all():
        raise R2IntegrityError("integrated marker7 metric is non-finite")
    return marker.reset_index(drop=True)


def _expected_contrast_metadata() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for encoder_key, mpps in ENCODER_MPPS:
        encoder = "CONCH" if encoder_key == "conch" else "Virchow"
        for seed in range(5):
            for tiles in TILE_COUNTS:
                rows.append({
                    "contrast": "native_vs_1.76",
                    "pair_id": f"native_vs_1.76__marker7__{encoder_key}__s{seed}__t{tiles}",
                    "cell_id_a": f"marker7__{encoder_key}__s{seed}__t{tiles}__mpp{mpps[0]:.2f}",
                    "cell_id_b": f"marker7__{encoder_key}__s{seed}__t{tiles}__mpp1.76",
                    "sampling_seed": seed, "encoder_a": encoder, "encoder_b": encoder,
                    "tiles_per_slide_a": tiles, "tiles_per_slide_b": tiles,
                    "target_mpp_a": mpps[0], "target_mpp_b": 1.76,
                })
    for seed in range(5):
        for tiles in TILE_COUNTS:
            rows.append({
                "contrast": "virchow_vs_conch_at_1.76",
                "pair_id": f"virchow_vs_conch_at_1.76__marker7__s{seed}__t{tiles}",
                "cell_id_a": f"marker7__conch__s{seed}__t{tiles}__mpp1.76",
                "cell_id_b": f"marker7__virchow__s{seed}__t{tiles}__mpp1.76",
                "sampling_seed": seed, "encoder_a": "CONCH", "encoder_b": "Virchow",
                "tiles_per_slide_a": tiles, "tiles_per_slide_b": tiles,
                "target_mpp_a": 1.76, "target_mpp_b": 1.76,
            })
    for encoder_key, mpps in ENCODER_MPPS:
        encoder = "CONCH" if encoder_key == "conch" else "Virchow"
        for seed in range(5):
            for mpp in mpps:
                rows.append({
                    "contrast": "tile64_vs16",
                    "pair_id": f"tile64_vs16__marker7__{encoder_key}__s{seed}__mpp{mpp}",
                    "cell_id_a": f"marker7__{encoder_key}__s{seed}__t16__mpp{mpp:.2f}",
                    "cell_id_b": f"marker7__{encoder_key}__s{seed}__t64__mpp{mpp:.2f}",
                    "sampling_seed": seed, "encoder_a": encoder, "encoder_b": encoder,
                    "tiles_per_slide_a": 16, "tiles_per_slide_b": 64,
                    "target_mpp_a": mpp, "target_mpp_b": mpp,
                })
    return pd.DataFrame(rows)


def _boolean_array(values: pd.Series, label: str) -> np.ndarray:
    mapping = {True: True, False: False, "True": True, "False": False, 1: True, 0: False}
    converted = values.map(mapping)
    if converted.isna().any():
        raise R2IntegrityError(f"{label} is not strictly boolean")
    return converted.to_numpy(dtype=bool)


def _validate_contrasts(frame: pd.DataFrame) -> pd.DataFrame:
    if list(frame.columns) != R1_CONTRAST_COLUMNS:
        raise R2IntegrityError("R1 contrast schema mismatch")
    marker = frame.loc[frame["marker"].eq("marker7")].copy().reset_index(drop=True)
    if len(marker) != 65 or marker["pair_id"].duplicated().any():
        raise R2IntegrityError("R1 marker7 contrasts must contain 65 unique pairs")
    expected = _expected_contrast_metadata()
    text_columns = ["contrast", "pair_id", "cell_id_a", "cell_id_b", "encoder_a", "encoder_b"]
    integer_columns = ["sampling_seed", "tiles_per_slide_a", "tiles_per_slide_b"]
    float_columns = ["target_mpp_a", "target_mpp_b"]
    for column in text_columns:
        if marker[column].astype(str).tolist() != expected[column].astype(str).tolist():
            raise R2IntegrityError(f"R1 contrast metadata mismatch: {column}")
    for column in integer_columns:
        values = pd.to_numeric(marker[column], errors="coerce").to_numpy(float)
        expected_values = expected[column].to_numpy(float)
        if not np.isfinite(values).all() or not np.array_equal(values, expected_values):
            raise R2IntegrityError(f"R1 contrast metadata mismatch: {column}")
    for column in float_columns:
        values = pd.to_numeric(marker[column], errors="coerce").to_numpy(float)
        if not np.allclose(values, expected[column].to_numpy(float), rtol=0, atol=1e-12):
            raise R2IntegrityError(f"R1 contrast metadata mismatch: {column}")
    for column, expected_value in (
        ("marker", "marker7"), ("outcome_type", "survival"),
        ("primary_metric", "patient_c_index"), ("metric_direction", "higher_is_better"),
    ):
        if not marker[column].eq(expected_value).all():
            raise R2IntegrityError(f"R1 contrast semantic mismatch: {column}")
    nulls = pd.to_numeric(marker["null_value"], errors="coerce").to_numpy(float)
    metric_a = pd.to_numeric(marker["patient_metric_a"], errors="coerce").to_numpy(float)
    metric_b = pd.to_numeric(marker["patient_metric_b"], errors="coerce").to_numpy(float)
    if not (np.isfinite(nulls).all() and np.isfinite(metric_a).all() and np.isfinite(metric_b).all()):
        raise R2IntegrityError("R1 marker7 contrast metric is non-finite")
    if not np.allclose(nulls, NULL_VALUE, rtol=0, atol=0):
        raise R2IntegrityError("R1 marker7 contrast null value changed")
    arithmetic = metric_b - metric_a
    if not np.allclose(
        arithmetic, pd.to_numeric(marker["delta_b_minus_a"]),
        atol=CONTRAST_CSV_ATOL, rtol=0,
    ):
        raise R2IntegrityError("R1 marker7 contrast arithmetic mismatch")
    expected_relation_a = [_relation(value) for value in metric_a]
    expected_relation_b = [_relation(value) for value in metric_b]
    if marker["relation_a"].astype(str).tolist() != expected_relation_a:
        raise R2IntegrityError("R1 contrast relation_a mismatch")
    if marker["relation_b"].astype(str).tolist() != expected_relation_b:
        raise R2IntegrityError("R1 contrast relation_b mismatch")
    crossing = np.array(expected_relation_a) != np.array(expected_relation_b)
    if not np.array_equal(_boolean_array(marker["null_crossing"], "R1 null_crossing"), crossing):
        raise R2IntegrityError("R1 contrast null-crossing mismatch")
    if not np.array_equal(_boolean_array(marker["exact_tie"], "R1 exact_tie"), arithmetic == 0):
        raise R2IntegrityError("R1 contrast tie mismatch")
    return marker


def audit_inputs(
    *,
    root: Path,
    run_root: Path,
    spec_path: Path,
    fold_path: Path,
    integrated_cells_path: Path,
    contrasts_path: Path,
    scan_embeddings: bool,
) -> InputAudit:
    configs = discover_configs(run_root)
    sources: dict[str, tuple[SourceConfig, pd.DataFrame]] = {}
    targets: dict[str, tuple[SourceConfig, pd.DataFrame]] = {}
    for config in configs:
        checked = validate_config_inputs(config, scan_finite=scan_embeddings)
        sources[config.config_id] = (config, checked["source"])
        targets[config.config_id] = (config, checked["target"])
    membership, common_ids, union_ids = build_membership_manifest(
        sources,
        expected_common=COMMON_SOURCE_COUNT,
        expected_union=SOURCE_UNION_COUNT,
        expected_common_events=COMMON_SOURCE_EVENTS,
    )
    if id_list_sha256(common_ids) != COMMON_SOURCE_ID_SHA256:
        raise R2IntegrityError("frozen common-498 membership hash mismatch")
    if id_list_sha256(union_ids) != SOURCE_UNION_ID_SHA256:
        raise R2IntegrityError("frozen source union membership hash mismatch")

    folds = pd.read_csv(fold_path)
    target_summary = validate_target_and_folds(
        targets, folds,
        expected_slides=TARGET_SLIDES,
        expected_patients=TARGET_PATIENTS,
        expected_events=TARGET_EVENTS,
        expected_patient_hash=TARGET_PATIENT_ID_SHA256,
        require_all_five_folds=True,
        expected_slide_case_hash=TARGET_SLIDE_CASE_ORDER_SHA256,
    )
    spec = pd.read_csv(spec_path)
    _validate_marker7_spec(spec)
    integrated = _validate_integrated_cells(pd.read_csv(integrated_cells_path))
    contrasts = _validate_contrasts(pd.read_csv(contrasts_path))
    return InputAudit(configs, membership, common_ids, union_ids, target_summary, integrated, contrasts)


def _relation(value: float, null: float = NULL_VALUE) -> str:
    if value > null:
        return "above_null"
    if value < null:
        return "below_null"
    return "at_null"


def _direction(value: float) -> str:
    return "positive" if value > 0 else "negative" if value < 0 else "tie"


def validate_reproduction(frame: pd.DataFrame, *, atol: float) -> None:
    columns = ["raw_reproduction_error_vs_saved", "raw_reproduction_error_vs_integrated"]
    if any(column not in frame for column in columns):
        raise R2IntegrityError("raw reproduction error columns are absent")
    values = frame[columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(values).all() or (values > atol).any():
        raise R2IntegrityError(f"raw reproduction tolerance exceeded (atol={atol})")


def build_paired_deltas(
    cells: pd.DataFrame, contrasts: pd.DataFrame, *, require_full: bool
) -> pd.DataFrame:
    indexed = cells.set_index("cell_id", drop=False)
    if indexed.index.duplicated().any():
        raise R2IntegrityError("duplicate common-source cell_id")
    if require_full:
        contrasts = _validate_contrasts(contrasts)
    rows: list[dict[str, Any]] = []
    for contrast in contrasts.itertuples(index=False):
        if contrast.cell_id_a not in indexed.index or contrast.cell_id_b not in indexed.index:
            raise R2IntegrityError("paired contrast endpoint is absent from R2 cells")
        a, b = indexed.loc[contrast.cell_id_a], indexed.loc[contrast.cell_id_b]
        raw_a, raw_b = float(a.saved_raw_c_index), float(b.saved_raw_c_index)
        common_a, common_b = float(a.common_source_c_index), float(b.common_source_c_index)
        raw_delta = raw_b - raw_a
        common_delta = common_b - common_a
        if not np.isclose(
            raw_delta, float(contrast.delta_b_minus_a),
            atol=CONTRAST_CSV_ATOL, rtol=0,
        ):
            raise R2IntegrityError(f"R2/R1 raw contrast mismatch for {contrast.pair_id}")
        raw_direction, common_direction = _direction(raw_delta), _direction(common_delta)
        rows.append({
            "contrast": contrast.contrast,
            "pair_id": contrast.pair_id,
            "cell_id_a": contrast.cell_id_a,
            "cell_id_b": contrast.cell_id_b,
            "sampling_seed": int(contrast.sampling_seed),
            "encoder_a": contrast.encoder_a,
            "encoder_b": contrast.encoder_b,
            "tiles_per_slide_a": int(contrast.tiles_per_slide_a),
            "tiles_per_slide_b": int(contrast.tiles_per_slide_b),
            "target_mpp_a": float(contrast.target_mpp_a),
            "target_mpp_b": float(contrast.target_mpp_b),
            "raw_metric_a": raw_a,
            "raw_metric_b": raw_b,
            "raw_delta_b_minus_a": raw_delta,
            "common498_metric_a": common_a,
            "common498_metric_b": common_b,
            "common498_delta_b_minus_a": common_delta,
            "common_source_adjustment": common_delta - raw_delta,
            "raw_direction": raw_direction,
            "common498_direction": common_direction,
            "direction_status": "preserved" if raw_direction == common_direction else "reversed",
            "raw_null_crossing": _relation(raw_a) != _relation(raw_b),
            "common498_null_crossing": _relation(common_a) != _relation(common_b),
            "raw_exact_tie": raw_delta == 0,
            "common498_exact_tie": common_delta == 0,
        })
    result = pd.DataFrame(rows)
    if require_full and len(result) != 65:
        raise R2IntegrityError("R2 paired table must contain exactly 65 rows")
    if any("p_value" in column.lower() for column in result.columns):
        raise R2IntegrityError("R2 paired table must not contain inferential p-values")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(16 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _logical_path(path: Path, root: Path, manifest_path: Path | None = None) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        if manifest_path is not None and path.parent.resolve() == manifest_path.parent.resolve():
            return path.name
        return path.as_posix()


def snapshot_paths(paths: Iterable[Path], root: Path) -> dict[Path, dict[str, Any]]:
    snapshots: dict[Path, dict[str, Any]] = {}
    for original in sorted({Path(path) for path in paths}, key=lambda value: value.as_posix()):
        path = original.resolve()
        if not path.is_file():
            raise R2IntegrityError(f"input artifact is absent: {original}")
        stat_before = path.stat()
        n_rows, array_shape, array_dtype = _artifact_details(path)
        digest = _sha256(path)
        stat = path.stat()
        if (stat_before.st_size, stat_before.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise R2IntegrityError(f"input changed while snapshotting: {_logical_path(path, root)}")
        snapshots[path] = {
            "artifact_path": _logical_path(path, root),
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": digest,
            "rows": n_rows,
            "array_shape": array_shape,
            "array_dtype": array_dtype,
        }
    return snapshots


def assert_snapshots_unchanged(
    before: Mapping[Path, Mapping[str, Any]], after: Mapping[Path, Mapping[str, Any]]
) -> None:
    if set(before) != set(after):
        raise R2IntegrityError("input changed: snapshot path set differs")
    for path in before:
        for field in ("size_bytes", "mtime_ns", "sha256"):
            if before[path][field] != after[path][field]:
                raise R2IntegrityError(f"input changed during R2: {path} ({field})")


def validate_r1_config_lineage(
    snapshots: Mapping[Path, Mapping[str, Any]], r1_manifest: pd.DataFrame
) -> int:
    required_columns = {
        "artifact_kind", "artifact_path", "sha256_before", "sha256_after", "hash_reconciled"
    }
    if not required_columns.issubset(r1_manifest.columns):
        raise R2IntegrityError("R1 lineage manifest schema mismatch")
    declared = r1_manifest.loc[r1_manifest["artifact_kind"].eq("input")].copy()
    if declared["artifact_path"].astype(str).duplicated().any():
        raise R2IntegrityError("R1 lineage manifest has duplicate input paths")
    declared.index = declared["artifact_path"].astype(str)
    matched = 0
    prefixes = ("source_meta_", "target_meta_")
    for snapshot in snapshots.values():
        artifact_path = str(snapshot["artifact_path"])
        parts = Path(artifact_path).parts
        if "stability_runs" not in parts or not Path(artifact_path).name.startswith(prefixes):
            continue
        if artifact_path not in declared.index:
            raise R2IntegrityError(f"R1 lineage is missing frozen input {artifact_path}")
        row = declared.loc[artifact_path]
        if isinstance(row, pd.DataFrame):
            raise R2IntegrityError(f"R1 lineage is ambiguous for {artifact_path}")
        reconciled = _boolean_array(
            pd.Series([row["hash_reconciled"]]), "R1 hash_reconciled"
        )[0]
        digest = str(snapshot["sha256"])
        if not reconciled or str(row["sha256_before"]) != digest or str(row["sha256_after"]) != digest:
            raise R2IntegrityError(f"R1 lineage hash mismatch for {artifact_path}")
        matched += 1
    if matched == 0:
        raise R2IntegrityError("R1 lineage matched no marker7 configuration inputs")
    return matched


def configuration_embedding_lineage_sha256(
    snapshots: Mapping[Path, Mapping[str, Any]], *, expected_count: int | None = None
) -> str:
    records = []
    prefixes = ("source_tile_embeddings_", "target_tile_embeddings_")
    for snapshot in snapshots.values():
        artifact_path = str(snapshot["artifact_path"])
        if "stability_runs" in Path(artifact_path).parts and Path(artifact_path).name.startswith(prefixes):
            records.append((artifact_path, str(snapshot["sha256"])))
    records.sort()
    if expected_count is not None and len(records) != expected_count:
        raise R2IntegrityError(
            f"frozen embedding lineage count mismatch: {len(records)} != {expected_count}"
        )
    payload = "".join(f"{path}\t{digest}\n" for path, digest in records).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _package_version(distribution: str) -> str:
    return importlib.metadata.version(distribution)


def controller_probe() -> dict[str, str]:
    return {
        "executable": sys.executable,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": _package_version("scipy"),
        "sklearn": _package_version("scikit-learn"),
    }


def worker_probe() -> dict[str, str]:
    import scipy
    import sklearn
    import sksurv

    return {
        "executable": sys.executable,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
        "sksurv": sksurv.__version__,
    }


def _absolute_without_symlink_resolution(path: str | os.PathLike[str]) -> Path:
    """Normalize ``.``/``..`` while retaining the selected virtualenv path."""
    return Path(os.path.abspath(os.fspath(path)))


def validate_controller_probe(probe: Mapping[str, str], expected_interpreter: Path) -> None:
    if _absolute_without_symlink_resolution(str(probe.get("executable", ""))) != (
        _absolute_without_symlink_resolution(expected_interpreter)
    ):
        raise R2IntegrityError("controller executable is not the mandated workspace venv")
    for key, expected in CONTROLLER_VERSIONS.items():
        if str(probe.get(key)) != expected:
            raise R2IntegrityError(
                f"controller version mismatch for {key}: {probe.get(key)!r} != {expected!r}"
            )


def validate_worker_probe(probe: Mapping[str, str], expected_interpreter: Path) -> None:
    if _absolute_without_symlink_resolution(str(probe.get("executable", ""))) != (
        _absolute_without_symlink_resolution(expected_interpreter)
    ):
        raise R2IntegrityError("worker executable is not the pinned worker")
    for key, expected in WORKER_VERSIONS.items():
        if str(probe.get(key)) != expected:
            raise R2IntegrityError(
                f"worker version mismatch for {key}: {probe.get(key)!r} != {expected!r}"
            )


def probe_worker(interpreter: Path) -> dict[str, str]:
    if _absolute_without_symlink_resolution(interpreter) != _absolute_without_symlink_resolution(
        ROOT / "models/.venv-conch/bin/python"
    ):
        raise R2IntegrityError("only the pinned worker interpreter may be probed")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["CUDA_VISIBLE_DEVICES"] = ""
    completed = subprocess.run(
        [str(interpreter), str(SCRIPT), "--probe-worker"],
        check=False, capture_output=True, text=True, env=environment,
    )
    if completed.returncode != 0:
        raise R2IntegrityError(f"worker probe failed: {completed.stderr.strip()}")
    try:
        probe = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise R2IntegrityError("worker probe did not return JSON") from exc
    validate_worker_probe(probe, interpreter)
    return probe


def invoke_worker(job_path: Path, output_path: Path, interpreter: Path) -> None:
    expected = ROOT / "models/.venv-conch/bin/python"
    if _absolute_without_symlink_resolution(interpreter) != _absolute_without_symlink_resolution(
        expected
    ):
        raise R2IntegrityError("worker invocation requires the pinned worker interpreter")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["CUDA_VISIBLE_DEVICES"] = ""
    completed = subprocess.run(
        [str(interpreter), str(SCRIPT), "--worker", "--job", str(job_path),
         "--worker-output", str(output_path)],
        check=False, capture_output=True, text=True, env=environment,
    )
    if completed.returncode != 0:
        raise R2IntegrityError(f"pinned worker failed: {completed.stderr.strip()}")
    if not output_path.is_file():
        raise R2IntegrityError("pinned worker did not produce its staged result")


def _structured(event: np.ndarray, follow_up: np.ndarray) -> np.ndarray:
    return np.array(
        list(zip(event.astype(bool), follow_up.astype(float))),
        dtype=[("event", bool), ("time", float)],
    )


def _pool_prefix(array: np.ndarray, indices: Iterable[int], tile_count: int) -> np.ndarray:
    return np.stack([np.asarray(array[index, :tile_count]).mean(0) for index in indices])


def _score_source_target(
    source_pool: np.ndarray,
    source: pd.DataFrame,
    target_pool: np.ndarray,
    target: pd.DataFrame,
) -> float:
    # Imports remain worker-only; the controller environment intentionally lacks sksurv.
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sksurv.linear_model import CoxPHSurvivalAnalysis
    from sksurv.metrics import concordance_index_censored

    target_features = pd.DataFrame(target_pool)
    target_features["case_id"] = target["case_id"].to_numpy()
    patient_x = target_features.groupby("case_id").mean()
    patient = target.drop_duplicates("case_id").set_index("case_id").loc[patient_x.index]

    scaler = StandardScaler(copy=True, with_mean=True, with_std=True).fit(source_pool)
    pca = PCA(
        n_components=8,
        copy=True,
        whiten=False,
        svd_solver="auto",
        tol=0.0,
        iterated_power="auto",
        n_oversamples=10,
        power_iteration_normalizer="auto",
        random_state=0,
    ).fit(scaler.transform(source_pool))
    model = CoxPHSurvivalAnalysis(
        alpha=1.0, ties="breslow", n_iter=100, tol=1e-9, verbose=0
    ).fit(
        pca.transform(scaler.transform(source_pool)),
        _structured(source["event"].to_numpy(), source["follow_up_years"].to_numpy()),
    )
    risk = model.predict(pca.transform(scaler.transform(patient_x.to_numpy())))
    return float(concordance_index_censored(
        patient["event"].to_numpy().astype(bool),
        patient["follow_up_y"].to_numpy(float),
        risk,
    )[0])


def _worker_run(job_path: Path, output_path: Path) -> None:
    probe = worker_probe()
    validate_worker_probe(probe, ROOT / "models/.venv-conch/bin/python")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    root = Path(job["root"])
    common = set(map(str, job["common_source_ids"]))
    integrated = {key: float(value) for key, value in job["integrated_scores"].items()}
    rows: list[dict[str, Any]] = []
    raw_cache: dict[str, pd.DataFrame] = {}

    for item in job["configs"]:
        source_meta_path = root / item["source_meta"]
        source_embeddings_path = root / item["source_embeddings"]
        target_meta_path = root / item["target_meta"]
        target_embeddings_path = root / item["target_embeddings"]
        source = pd.read_csv(source_meta_path)
        target = pd.read_csv(target_meta_path)
        source_array = np.load(source_embeddings_path, mmap_mode="r")
        target_array = np.load(target_embeddings_path, mmap_mode="r")
        common_indices = [
            index for index, case_id in enumerate(source["case_id"].astype(str))
            if case_id in common
        ]
        common_source = source.iloc[common_indices].reset_index(drop=True)
        if len(common_source) != COMMON_SOURCE_COUNT:
            raise R2IntegrityError("worker common source count changed")

        runner = item["runner"]
        if runner not in raw_cache:
            raw_cache[runner] = pd.read_csv(root / item["raw_cells"] ).set_index("cell_id")
        raw_saved = raw_cache[runner]
        all_source_indices = range(len(source))
        all_target_indices = range(len(target))
        for tile_count in TILE_COUNTS:
            source_pool = _pool_prefix(source_array, all_source_indices, tile_count)
            common_pool = _pool_prefix(source_array, common_indices, tile_count)
            target_pool = _pool_prefix(target_array, all_target_indices, tile_count)
            raw_value = _score_source_target(source_pool, source, target_pool, target)
            common_value = _score_source_target(common_pool, common_source, target_pool, target)
            cell_id = (
                f"marker7__{item['encoder_key']}__s{item['sampling_seed']}__"
                f"t{tile_count}__mpp{float(item['target_mpp']):.2f}"
            )
            saved = float(raw_saved.loc[cell_id, "patient_metric"])
            integrated_value = integrated[cell_id]
            rows.append({
                "cell_id": cell_id,
                "marker": "marker7",
                "canonical_cohort": "LEOPARD-to-TCGA-PRAD",
                "outcome_type": "survival",
                "primary_metric": "patient_c_index",
                "encoder": item["encoder"],
                "sampling_seed": int(item["sampling_seed"]),
                "tiles_per_slide": tile_count,
                "target_mpp": float(item["target_mpp"]),
                "source_configuration_id": item["config_id"],
                "n_original_source_patients": len(source),
                "n_common_source_patients": len(common_source),
                "n_source_events": int(common_source["event"].sum()),
                "n_target_slides": len(target),
                "n_target_patients": int(target["case_id"].nunique()),
                "n_target_events": int(target.drop_duplicates("case_id")["event"].sum()),
                "n_target_folds": 5,
                "saved_raw_c_index": saved,
                "integrated_raw_c_index": integrated_value,
                "recomputed_raw_c_index": raw_value,
                "raw_reproduction_error_vs_saved": abs(raw_value - saved),
                "raw_reproduction_error_vs_integrated": abs(raw_value - integrated_value),
                "common_source_c_index": common_value,
                "common_minus_saved_raw": common_value - saved,
                "raw_relation_to_null": _relation(saved),
                "common_relation_to_null": _relation(common_value),
                "raw_common_null_crossing": _relation(saved) != _relation(common_value),
                "status": "complete",
            })
    output_path.write_text(
        json.dumps({"worker_probe": probe, "cells": rows}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _input_paths_and_roles(root: Path, configs: list[SourceConfig]) -> tuple[list[Path], dict[Path, str]]:
    roles: dict[Path, str] = {}
    for config in configs:
        for path, role in (
            (config.source_meta, "source_meta"),
            (config.source_embeddings, "source_embeddings"),
            (config.target_meta, "target_meta"),
            (config.target_embeddings, "target_embeddings"),
        ):
            roles[path.resolve()] = f"{role}:{config.config_id}"
    supporting = {
        root / "models/stability_grid_spec.csv": "frozen_spec",
        root / "models/stability_fold_assignments.csv": "frozen_folds",
        root / "models/stability_cell_results.csv": "r1_integrated_cells",
        root / "models/stability_contrast_summary.csv": "r1_contrasts",
        root / "models/stability_qc_report.json": "r1_qc",
        root / "models/stability_tile_coordinate_manifest.csv": "r1_coordinate_manifest",
        root / "models/stability_run_manifest.csv": "r1_run_manifest",
        root / "models/stability_runs/full/marker7_conch/cell_results.csv": "raw_cells:marker7_conch",
        root / "models/stability_runs/full/marker7_conch/fold_results.csv": "raw_folds:marker7_conch",
        root / "models/stability_runs/full/marker7_virchow/cell_results.csv": "raw_cells:marker7_virchow",
        root / "models/stability_runs/full/marker7_virchow/fold_results.csv": "raw_folds:marker7_virchow",
        root / "models/run_stability_marker7.py": "frozen_runner",
        SCRIPT: "r2_entry_point",
        root / "environment.yml": "environment_spec",
        root / "requirements-lock.txt": "requirements_lock",
    }
    for path, role in supporting.items():
        roles[path.resolve()] = role
    return list(roles), roles


def _artifact_details(path: Path) -> tuple[str, str, str]:
    try:
        if path.suffix == ".npy":
            array = np.load(path, mmap_mode="r")
            return "", "x".join(map(str, array.shape)), str(array.dtype)
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            return str(len(frame)), "", ""
    except Exception:
        pass
    return "", "", ""


def build_run_manifest(
    *,
    root: Path,
    input_before: Mapping[Path, Mapping[str, Any]],
    input_after: Mapping[Path, Mapping[str, Any]],
    input_roles: Mapping[Path, str],
    output_paths: list[Path],
    manifest_path: Path,
    controller_probe: Mapping[str, str],
    worker_probe: Mapping[str, str],
    generated_at_utc: str,
    elapsed_seconds: float,
    path_labels: Mapping[Path, str] | None = None,
) -> pd.DataFrame:
    labels = {Path(key).resolve(): value for key, value in (path_labels or {}).items()}
    rows: list[dict[str, Any]] = []
    controller_version = json.dumps(dict(controller_probe), sort_keys=True)
    worker_version = json.dumps(dict(worker_probe), sort_keys=True)
    for path in input_before:
        before, after = input_before[path], input_after[path]
        rows.append({
            "artifact_kind": "input",
            "artifact_role": input_roles.get(path, "input"),
            "source_configuration_id": input_roles.get(path, "").split(":", 1)[-1]
            if ":" in input_roles.get(path, "") else "",
            "artifact_path": labels.get(path, before["artifact_path"]),
            "size_bytes": after["size_bytes"],
            "mtime_ns": after["mtime_ns"],
            "rows": after.get("rows", ""),
            "array_shape": after.get("array_shape", ""),
            "array_dtype": after.get("array_dtype", ""),
            "sha256_before": before["sha256"],
            "sha256_after": after["sha256"],
            "hash_reconciled": before["sha256"] == after["sha256"],
            "controller_or_worker": "controller",
            "software_version": controller_version,
            "included_in_output_hashes": False,
            "hash_exclusion_reason": "immutable_input",
            "volatile_fields": "",
            "generated_at_utc": "",
            "elapsed_seconds": "",
        })
    for path in output_paths:
        resolved = path.resolve()
        stat = path.stat()
        n_rows, shape, dtype = _artifact_details(path)
        rows.append({
            "artifact_kind": "output",
            "artifact_role": path.stem,
            "source_configuration_id": "",
            "artifact_path": labels.get(resolved, _logical_path(path, root, manifest_path)),
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "rows": n_rows,
            "array_shape": shape,
            "array_dtype": dtype,
            "sha256_before": "",
            "sha256_after": _sha256(path),
            "hash_reconciled": True,
            "controller_or_worker": "worker+controller" if path.name == CELLS_NAME else "controller",
            "software_version": worker_version if path.name == CELLS_NAME else controller_version,
            "included_in_output_hashes": True,
            "hash_exclusion_reason": "",
            "volatile_fields": "",
            "generated_at_utc": "",
            "elapsed_seconds": "",
        })
    manifest_resolved = manifest_path.resolve()
    rows.append({
        "artifact_kind": "manifest",
        "artifact_role": "run_manifest",
        "source_configuration_id": "",
        "artifact_path": labels.get(
            manifest_resolved, _logical_path(manifest_path, root, manifest_path)
        ),
        "size_bytes": "",
        "mtime_ns": "",
        "rows": "",
        "array_shape": "",
        "array_dtype": "",
        "sha256_before": "",
        "sha256_after": "",
        "hash_reconciled": True,
        "controller_or_worker": "controller",
        "software_version": controller_version,
        "included_in_output_hashes": False,
        "hash_exclusion_reason": "self_referential_manifest",
        "volatile_fields": "generated_at_utc;elapsed_seconds;mtime_ns",
        "generated_at_utc": generated_at_utc,
        "elapsed_seconds": elapsed_seconds,
    })
    return pd.DataFrame(rows)


def normalize_manifest_for_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in ("mtime_ns", "generated_at_utc", "elapsed_seconds"):
        if column in normalized:
            normalized[column] = ""
    return normalized


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")


def _expected_cell_metadata() -> pd.DataFrame:
    rows = []
    for config in expected_configs(Path("/unused")):
        for tiles in TILE_COUNTS:
            rows.append({
                "cell_id": (
                    f"marker7__{config.encoder_key}__s{config.sampling_seed}__"
                    f"t{tiles}__mpp{config.target_mpp:.2f}"
                ),
                "source_configuration_id": config.config_id,
                "encoder": config.encoder,
                "sampling_seed": config.sampling_seed,
                "tiles_per_slide": tiles,
                "target_mpp": config.target_mpp,
            })
    return pd.DataFrame(rows)


def _validate_membership_output(membership: pd.DataFrame) -> dict[str, int]:
    if list(membership.columns) != MEMBERSHIP_COLUMNS:
        raise R2IntegrityError("R2 membership schema mismatch")
    if len(membership) != 10_040:
        raise R2IntegrityError("R2 membership manifest must contain 10,040 rows")
    if membership[["source_configuration_id", "source_case_id"]].duplicated().any():
        raise R2IntegrityError("R2 membership Cartesian key is duplicated")

    config_metadata = {
        config.config_id: config for config in expected_configs(Path("/unused"))
    }
    if membership["source_configuration_id"].drop_duplicates().astype(str).tolist() != list(
        config_metadata
    ):
        raise R2IntegrityError("R2 membership configuration order/set mismatch")
    retained_all = _boolean_array(membership["retained_in_config"], "retained_in_config")
    common_all = _boolean_array(membership["common_source_member"], "common_source_member")
    if int(retained_all.sum()) != 9_992 or int(common_all.sum()) != 9_960:
        raise R2IntegrityError("R2 membership retained/common totals changed")

    event = pd.to_numeric(membership["event"], errors="coerce")
    follow_up = pd.to_numeric(membership["follow_up_years"], errors="coerce")
    if event.isna().any() or follow_up.isna().any() or not np.isfinite(follow_up).all():
        raise R2IntegrityError("R2 membership outcome is missing or non-finite")
    if not set(event.unique()).issubset({0, 1}) or (follow_up <= 0).any():
        raise R2IntegrityError("R2 membership outcome is invalid")
    outcomes = membership.assign(_event=event, _follow_up=follow_up).groupby("source_case_id")[[
        "_event", "_follow_up"
    ]].nunique(dropna=False)
    if (outcomes != 1).any().any():
        raise R2IntegrityError("R2 membership outcome consistency mismatch")

    original_counts: dict[str, int] = {}
    canonical_union: list[str] | None = None
    canonical_common_order: list[str] | None = None
    for config_id, group in membership.groupby("source_configuration_id", sort=False):
        config = config_metadata[str(config_id)]
        if not (
            group["encoder"].eq(config.encoder).all()
            and pd.to_numeric(group["sampling_seed"], errors="coerce").eq(config.sampling_seed).all()
            and np.allclose(
                pd.to_numeric(group["target_mpp"], errors="coerce"),
                config.target_mpp, rtol=0, atol=1e-12,
            )
        ):
            raise R2IntegrityError(f"R2 membership axis mismatch for {config_id}")
        union_ids = group["source_case_id"].astype(str).tolist()
        if union_ids != sorted(union_ids) or id_list_sha256(union_ids) != SOURCE_UNION_ID_SHA256:
            raise R2IntegrityError(f"R2 membership union order/hash mismatch for {config_id}")
        if canonical_union is None:
            canonical_union = union_ids
        elif union_ids != canonical_union:
            raise R2IntegrityError("R2 membership union differs across configurations")

        retained = _boolean_array(group["retained_in_config"], "retained_in_config")
        common = _boolean_array(group["common_source_member"], "common_source_member")
        retained_group = group.loc[retained].copy()
        common_group = group.loc[common].copy()
        original_counts[str(config_id)] = len(retained_group)
        if len(common_group) != COMMON_SOURCE_COUNT or not retained[common].all():
            raise R2IntegrityError(f"R2 common membership/retention mismatch for {config_id}")
        if id_list_sha256(common_group["source_case_id"].astype(str)) != COMMON_SOURCE_ID_SHA256:
            raise R2IntegrityError(f"R2 common membership hash mismatch for {config_id}")
        if int(pd.to_numeric(common_group["event"], errors="coerce").sum()) != COMMON_SOURCE_EVENTS:
            raise R2IntegrityError(f"R2 common event count mismatch for {config_id}")

        source_index = pd.to_numeric(retained_group["source_row_index"], errors="coerce")
        if source_index.isna().any() or not np.equal(source_index % 1, 0).all():
            raise R2IntegrityError(f"R2 source row index is invalid for {config_id}")
        if sorted(source_index.astype(int).tolist()) != list(range(len(retained_group))):
            raise R2IntegrityError(f"R2 source row index is not contiguous for {config_id}")
        if pd.to_numeric(
            group.loc[~retained, "source_row_index"], errors="coerce"
        ).notna().any():
            raise R2IntegrityError(f"R2 non-retained source has a row index for {config_id}")

        common_index = pd.to_numeric(common_group["common_row_index"], errors="coerce")
        if common_index.isna().any() or not np.equal(common_index % 1, 0).all():
            raise R2IntegrityError(f"R2 common row index is invalid for {config_id}")
        ordered_common = common_group.assign(
            _source_index=pd.to_numeric(common_group["source_row_index"], errors="raise"),
            _common_index=common_index,
        ).sort_values("_source_index")
        if ordered_common["_common_index"].astype(int).tolist() != list(range(COMMON_SOURCE_COUNT)):
            raise R2IntegrityError(f"R2 common row index is not row-preserving for {config_id}")
        current_common_order = ordered_common["source_case_id"].astype(str).tolist()
        if canonical_common_order is None:
            canonical_common_order = current_common_order
        elif current_common_order != canonical_common_order:
            raise R2IntegrityError("R2 filtered common order differs across configurations")
        if pd.to_numeric(
            group.loc[~common, "common_row_index"], errors="coerce"
        ).notna().any():
            raise R2IntegrityError(f"R2 non-common source has common row index for {config_id}")

        expected_status = np.where(retained, "consistent", "not_retained")
        if group["outcome_consistency_status"].astype(str).tolist() != expected_status.tolist():
            raise R2IntegrityError(f"R2 membership status mismatch for {config_id}")
    return original_counts


def _validate_outputs(
    cells: pd.DataFrame,
    deltas: pd.DataFrame,
    membership: pd.DataFrame,
    contrasts: pd.DataFrame,
) -> None:
    original_counts = _validate_membership_output(membership)
    if list(cells.columns) != CELL_COLUMNS:
        raise R2IntegrityError("R2 cell schema mismatch")
    expected_cells = _expected_cell_metadata()
    if len(cells) != 60 or cells["cell_id"].duplicated().any():
        raise R2IntegrityError("R2 cells must contain 60 unique rows")
    if cells["cell_id"].astype(str).tolist() != expected_cells["cell_id"].tolist():
        raise R2IntegrityError("R2 cell order/set disagrees with the frozen axes")
    for column in ("source_configuration_id", "encoder"):
        if cells[column].astype(str).tolist() != expected_cells[column].astype(str).tolist():
            raise R2IntegrityError(f"R2 cell semantics mismatch: {column}")
    for column in ("sampling_seed", "tiles_per_slide"):
        values = pd.to_numeric(cells[column], errors="coerce").to_numpy(float)
        expected_values = expected_cells[column].to_numpy(float)
        if not np.isfinite(values).all() or not np.array_equal(values, expected_values):
            raise R2IntegrityError(f"R2 cell semantics mismatch: {column}")
    if not np.allclose(
        pd.to_numeric(cells["target_mpp"], errors="coerce"),
        expected_cells["target_mpp"], rtol=0, atol=1e-12,
    ):
        raise R2IntegrityError("R2 cell semantics mismatch: target_mpp")
    for column, value in (
        ("marker", "marker7"), ("canonical_cohort", "LEOPARD-to-TCGA-PRAD"),
        ("outcome_type", "survival"), ("primary_metric", "patient_c_index"),
        ("status", "complete"),
    ):
        if not cells[column].eq(value).all():
            raise R2IntegrityError(f"R2 cell semantics mismatch: {column}")

    expected_original = cells["source_configuration_id"].map(original_counts)
    denominators = {
        "n_original_source_patients": expected_original,
        "n_common_source_patients": COMMON_SOURCE_COUNT,
        "n_source_events": COMMON_SOURCE_EVENTS,
        "n_target_slides": TARGET_SLIDES,
        "n_target_patients": TARGET_PATIENTS,
        "n_target_events": TARGET_EVENTS,
        "n_target_folds": 5,
    }
    for column, expected in denominators.items():
        values = pd.to_numeric(cells[column], errors="coerce")
        expected_values = (
            pd.to_numeric(expected, errors="coerce").to_numpy(float)
            if isinstance(expected, pd.Series)
            else np.full(len(cells), float(expected))
        )
        if values.isna().any() or not np.array_equal(values.to_numpy(float), expected_values):
            raise R2IntegrityError(f"R2 cell denominator mismatch: {column}")

    metric_columns = [
        "saved_raw_c_index", "integrated_raw_c_index", "recomputed_raw_c_index",
        "raw_reproduction_error_vs_saved", "raw_reproduction_error_vs_integrated",
        "common_source_c_index", "common_minus_saved_raw",
    ]
    metrics = cells[metric_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(metrics.to_numpy(float)).all():
        raise R2IntegrityError("R2 cell metric is non-finite")
    for column in (
        "saved_raw_c_index", "integrated_raw_c_index", "recomputed_raw_c_index",
        "common_source_c_index",
    ):
        if not metrics[column].between(0, 1, inclusive="both").all():
            raise R2IntegrityError(f"R2 C-index outside [0,1]: {column}")
    expected_arithmetic = {
        "raw_reproduction_error_vs_saved": np.abs(
            metrics["recomputed_raw_c_index"] - metrics["saved_raw_c_index"]
        ),
        "raw_reproduction_error_vs_integrated": np.abs(
            metrics["recomputed_raw_c_index"] - metrics["integrated_raw_c_index"]
        ),
        "common_minus_saved_raw": metrics["common_source_c_index"] - metrics["saved_raw_c_index"],
    }
    for column, expected in expected_arithmetic.items():
        if not np.allclose(metrics[column], expected, rtol=0, atol=REPRODUCTION_ATOL):
            raise R2IntegrityError(f"R2 cell arithmetic mismatch: {column}")
    validate_reproduction(cells, atol=REPRODUCTION_ATOL)
    raw_relation = [_relation(value) for value in metrics["saved_raw_c_index"]]
    common_relation = [_relation(value) for value in metrics["common_source_c_index"]]
    if cells["raw_relation_to_null"].astype(str).tolist() != raw_relation:
        raise R2IntegrityError("R2 raw null relation mismatch")
    if cells["common_relation_to_null"].astype(str).tolist() != common_relation:
        raise R2IntegrityError("R2 common null relation mismatch")
    if not np.array_equal(
        _boolean_array(cells["raw_common_null_crossing"], "raw_common_null_crossing"),
        np.array(raw_relation) != np.array(common_relation),
    ):
        raise R2IntegrityError("R2 raw/common null-crossing mismatch")

    if list(deltas.columns) != DELTA_COLUMNS:
        raise R2IntegrityError("R2 paired-delta schema mismatch")
    expected_contrasts = _validate_contrasts(contrasts)
    if len(deltas) != 65 or deltas["pair_id"].duplicated().any():
        raise R2IntegrityError("R2 paired deltas must contain 65 unique rows")
    metadata_columns = [
        "contrast", "pair_id", "cell_id_a", "cell_id_b", "sampling_seed",
        "encoder_a", "encoder_b", "tiles_per_slide_a", "tiles_per_slide_b",
        "target_mpp_a", "target_mpp_b",
    ]
    for column in metadata_columns:
        actual = deltas[column]
        expected = expected_contrasts[column]
        if column.startswith("target_mpp"):
            matches = np.allclose(
                pd.to_numeric(actual, errors="coerce"), pd.to_numeric(expected, errors="coerce"),
                rtol=0, atol=1e-12,
            )
        elif column in {"sampling_seed", "tiles_per_slide_a", "tiles_per_slide_b"}:
            actual_values = pd.to_numeric(actual, errors="coerce").to_numpy(float)
            expected_values = pd.to_numeric(expected, errors="coerce").to_numpy(float)
            matches = np.isfinite(actual_values).all() and np.array_equal(
                actual_values, expected_values
            )
        else:
            matches = actual.astype(str).tolist() == expected.astype(str).tolist()
        if not matches:
            raise R2IntegrityError(f"R2 paired-delta metadata mismatch: {column}")

    indexed = cells.set_index("cell_id")
    a = indexed.loc[deltas["cell_id_a"]]
    b = indexed.loc[deltas["cell_id_b"]]
    a.index = deltas.index; b.index = deltas.index
    expected_numeric = {
        "raw_metric_a": a["saved_raw_c_index"].astype(float),
        "raw_metric_b": b["saved_raw_c_index"].astype(float),
        "raw_delta_b_minus_a": b["saved_raw_c_index"].astype(float) - a["saved_raw_c_index"].astype(float),
        "common498_metric_a": a["common_source_c_index"].astype(float),
        "common498_metric_b": b["common_source_c_index"].astype(float),
        "common498_delta_b_minus_a": b["common_source_c_index"].astype(float) - a["common_source_c_index"].astype(float),
    }
    expected_numeric["common_source_adjustment"] = (
        expected_numeric["common498_delta_b_minus_a"] - expected_numeric["raw_delta_b_minus_a"]
    )
    for column, expected in expected_numeric.items():
        if not np.allclose(
            pd.to_numeric(deltas[column], errors="coerce"), expected,
            rtol=0, atol=CONTRAST_CSV_ATOL,
        ):
            raise R2IntegrityError(f"R2 paired-delta arithmetic mismatch: {column}")
    raw_direction = [_direction(value) for value in expected_numeric["raw_delta_b_minus_a"]]
    common_direction = [_direction(value) for value in expected_numeric["common498_delta_b_minus_a"]]
    expected_text = {
        "raw_direction": raw_direction,
        "common498_direction": common_direction,
        "direction_status": [
            "preserved" if raw == common else "reversed"
            for raw, common in zip(raw_direction, common_direction)
        ],
    }
    for column, expected in expected_text.items():
        if deltas[column].astype(str).tolist() != expected:
            raise R2IntegrityError(f"R2 paired-delta semantic mismatch: {column}")
    expected_boolean = {
        "raw_null_crossing": np.array([_relation(value) for value in expected_numeric["raw_metric_a"]])
        != np.array([_relation(value) for value in expected_numeric["raw_metric_b"]]),
        "common498_null_crossing": np.array([
            _relation(value) for value in expected_numeric["common498_metric_a"]
        ]) != np.array([_relation(value) for value in expected_numeric["common498_metric_b"]]),
        "raw_exact_tie": expected_numeric["raw_delta_b_minus_a"].to_numpy() == 0,
        "common498_exact_tie": expected_numeric["common498_delta_b_minus_a"].to_numpy() == 0,
    }
    for column, expected in expected_boolean.items():
        if not np.array_equal(_boolean_array(deltas[column], column), expected):
            raise R2IntegrityError(f"R2 paired-delta semantic mismatch: {column}")
    if any("p_value" in column.lower() for column in deltas.columns):
        raise R2IntegrityError("R2 paired table must not contain inferential p-values")


def _run_config(audit: InputAudit, controller: Mapping[str, str], worker: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "analysis_id": "marker7_common_source_sensitivity",
        "entry_environment": ".venv/bin/python",
        "worker_environment": "models/.venv-conch/bin/python",
        "controller_software": dict(controller),
        "worker_software": dict(worker),
        "axes": {
            "encoders": ["CONCH", "Virchow"],
            "sampling_seeds": list(range(5)),
            "tile_prefixes": list(TILE_COUNTS),
            "target_mpp": {"CONCH": [0.88, 1.76], "Virchow": [0.44, 1.76]},
        },
        "source": {
            "n_configurations": 20,
            "common_patients": 498,
            "common_events": 85,
            "union_patients": 502,
            "common_patient_id_sha256": id_list_sha256(audit.common_ids),
            "union_patient_id_sha256": id_list_sha256(audit.union_ids),
            "filtering": "row-preserving positional mask applied identically to metadata and embeddings",
        },
        "target": {**audit.target_summary, "pooling": "tile-prefix mean per slide, then mean by case_id"},
        "model": {
            "StandardScaler": {"copy": True, "with_mean": True, "with_std": True},
            "PCA": {
                "n_components": 8, "copy": True, "whiten": False, "svd_solver": "auto",
                "tol": 0.0, "iterated_power": "auto", "n_oversamples": 10,
                "power_iteration_normalizer": "auto", "random_state": 0,
            },
            "CoxPHSurvivalAnalysis": {
                "alpha": 1.0, "ties": "breslow", "n_iter": 100, "tol": 1e-9, "verbose": 0,
            },
            "metric": "Harrell concordance_index_censored",
            "null_value": 0.5,
        },
        "outputs": [CELLS_NAME, DELTAS_NAME, MEMBERSHIP_NAME, CONFIG_NAME, MANIFEST_NAME],
        "reproduction_atol": REPRODUCTION_ATOL,
        "volatile_manifest_fields": ["generated_at_utc", "elapsed_seconds", "mtime_ns"],
        "interpretation": "correlated source-membership sensitivity; no independent replication or p-values",
    }


def validate_staged_artifacts(
    staged: Mapping[str, Path], audit: InputAudit, expected_config: Mapping[str, Any]
) -> None:
    required = {CELLS_NAME, DELTAS_NAME, MEMBERSHIP_NAME, CONFIG_NAME, MANIFEST_NAME}
    if set(staged) != required or any(not Path(staged[name]).is_file() for name in required):
        raise R2IntegrityError("staged R2 artifact set is incomplete")
    cells = pd.read_csv(staged[CELLS_NAME])
    deltas = pd.read_csv(staged[DELTAS_NAME])
    membership = pd.read_csv(staged[MEMBERSHIP_NAME])
    _validate_outputs(cells, deltas, membership, audit.contrasts)
    try:
        read_config = json.loads(Path(staged[CONFIG_NAME]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise R2IntegrityError("staged R2 run config is unreadable") from exc
    if read_config != dict(expected_config):
        raise R2IntegrityError("staged R2 run config changed on read-back")

    manifest = pd.read_csv(staged[MANIFEST_NAME], dtype=str, keep_default_na=False)
    if list(manifest.columns) != RUN_MANIFEST_COLUMNS or len(manifest) != 100:
        raise R2IntegrityError("staged R2 manifest schema/row count mismatch")
    input_rows = manifest.loc[manifest["artifact_kind"].eq("input")]
    if len(input_rows) != 95:
        raise R2IntegrityError("staged R2 manifest input count mismatch")
    if not _boolean_array(input_rows["hash_reconciled"], "manifest input hash_reconciled").all():
        raise R2IntegrityError("staged R2 manifest contains an unreconciled input")
    if not (input_rows["sha256_before"] == input_rows["sha256_after"]).all():
        raise R2IntegrityError("staged R2 manifest input pre/post hashes differ")
    output_rows = manifest.loc[manifest["artifact_kind"].eq("output")]
    expected_outputs = {Path(staged[name]).stem: Path(staged[name]) for name in (
        CELLS_NAME, DELTAS_NAME, MEMBERSHIP_NAME, CONFIG_NAME
    )}
    if set(output_rows["artifact_role"]) != set(expected_outputs) or len(output_rows) != 4:
        raise R2IntegrityError("staged R2 manifest output set mismatch")
    for role, path in expected_outputs.items():
        row = output_rows.loc[output_rows["artifact_role"].eq(role)].iloc[0]
        if row["sha256_after"] != _sha256(path) or row["size_bytes"] != str(path.stat().st_size):
            raise R2IntegrityError(f"staged R2 manifest output hash mismatch: {role}")
    self_rows = manifest.loc[manifest["artifact_kind"].eq("manifest")]
    if len(self_rows) != 1:
        raise R2IntegrityError("staged R2 manifest self row mismatch")
    self_row = self_rows.iloc[0]
    if (
        self_row["sha256_after"] != ""
        or self_row["included_in_output_hashes"] != "False"
        or self_row["hash_exclusion_reason"] != "self_referential_manifest"
    ):
        raise R2IntegrityError("staged R2 manifest self-hash exclusion mismatch")


def publish_output_set(
    staged: Mapping[str, Path], output_dir: Path, names: Iterable[str]
) -> dict[str, Path]:
    """Publish a validated output set and restore the old set on any replace failure."""
    names = tuple(names)
    output_dir = Path(output_dir)
    missing = [name for name in names if name not in staged or not Path(staged[name]).is_file()]
    if missing:
        raise R2IntegrityError(f"staged publication set is incomplete: {missing}")
    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = {name: output_dir / name for name in names}
    invalid = [str(path) for path in destinations.values() if path.exists() and not path.is_file()]
    if invalid:
        raise R2IntegrityError(f"publication destination is not a regular file: {invalid}")

    with tempfile.TemporaryDirectory(prefix="marker7-common498-backup-", dir=output_dir.parent) as temporary:
        backup_dir = Path(temporary)
        for name, destination in destinations.items():
            if destination.exists():
                shutil.copy2(destination, backup_dir / name)

        installed: set[str] = set()
        try:
            for name in names:
                os.replace(Path(staged[name]), destinations[name])
                installed.add(name)
        except Exception as exc:
            rollback_errors: list[str] = []
            for name, destination in destinations.items():
                backup = backup_dir / name
                try:
                    if backup.exists():
                        os.replace(backup, destination)
                    elif name in installed and destination.exists():
                        destination.unlink()
                except Exception as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                    rollback_errors.append(f"{name}:{rollback_exc}")
            if rollback_errors:
                raise R2IntegrityError(
                    "publication failed and rollback was incomplete: " + "; ".join(rollback_errors)
                ) from exc
            raise R2IntegrityError("publication failed; previous output set restored") from exc
    return destinations


def run_analysis(*, root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Path]:
    start = time.perf_counter()
    root = Path(root).resolve()
    output_dir = (Path(output_dir) if output_dir is not None else root / "models").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_root = root / "models/stability_runs/full"
    configs = discover_configs(run_root)
    input_paths, input_roles = _input_paths_and_roles(root, configs)
    before = snapshot_paths(input_paths, root)
    r1_manifest_path = (root / "models/stability_run_manifest.csv").resolve()
    if before[r1_manifest_path]["sha256"] != R1_RUN_MANIFEST_SHA256:
        raise R2IntegrityError("frozen R1 run-manifest hash mismatch")
    r1_manifest = pd.read_csv(r1_manifest_path, dtype=str, keep_default_na=False)
    if validate_r1_config_lineage(before, r1_manifest) != 40:
        raise R2IntegrityError("R1 lineage did not bind the exact 40 configuration metadata inputs")
    if configuration_embedding_lineage_sha256(before, expected_count=40) != (
        FROZEN_EMBEDDING_LINEAGE_SHA256
    ):
        raise R2IntegrityError("frozen configuration embedding lineage hash mismatch")

    audit = audit_inputs(
        root=root,
        run_root=run_root,
        spec_path=root / "models/stability_grid_spec.csv",
        fold_path=root / "models/stability_fold_assignments.csv",
        integrated_cells_path=root / "models/stability_cell_results.csv",
        contrasts_path=root / "models/stability_contrast_summary.csv",
        scan_embeddings=True,
    )
    controller = controller_probe()
    validate_controller_probe(controller, root / ".venv/bin/python")
    interpreter = root / "models/.venv-conch/bin/python"
    worker = probe_worker(interpreter)
    controller_record = {**controller, "executable": ".venv/bin/python"}
    worker_record = {**worker, "executable": "models/.venv-conch/bin/python"}

    with tempfile.TemporaryDirectory(prefix="marker7-common498-", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        job_path = stage / "worker_job.json"
        worker_output = stage / "worker_results.json"
        integrated_scores = dict(zip(
            audit.integrated_cells["cell_id"].astype(str),
            pd.to_numeric(audit.integrated_cells["patient_metric"], errors="raise").astype(float),
        ))
        job = {
            "root": str(root),
            "common_source_ids": audit.common_ids,
            "integrated_scores": integrated_scores,
            "configs": [
                {
                    "config_id": config.config_id,
                    "encoder_key": config.encoder_key,
                    "encoder": config.encoder,
                    "sampling_seed": config.sampling_seed,
                    "target_mpp": config.target_mpp,
                    "runner": f"marker7_{config.encoder_key}",
                    "source_meta": _relative(config.source_meta, root),
                    "source_embeddings": _relative(config.source_embeddings, root),
                    "target_meta": _relative(config.target_meta, root),
                    "target_embeddings": _relative(config.target_embeddings, root),
                    "raw_cells": f"models/stability_runs/full/marker7_{config.encoder_key}/cell_results.csv",
                }
                for config in audit.configs
            ],
        }
        job_path.write_text(json.dumps(job, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        invoke_worker(job_path, worker_output, interpreter)
        payload = json.loads(worker_output.read_text(encoding="utf-8"))
        validate_worker_probe(payload["worker_probe"], interpreter)
        cells = pd.DataFrame(payload["cells"], columns=CELL_COLUMNS)
        deltas = build_paired_deltas(cells, audit.contrasts, require_full=True)
        membership = audit.membership.copy()
        _validate_outputs(cells, deltas, membership, audit.contrasts)

        staged = {
            CELLS_NAME: stage / CELLS_NAME,
            DELTAS_NAME: stage / DELTAS_NAME,
            MEMBERSHIP_NAME: stage / MEMBERSHIP_NAME,
            CONFIG_NAME: stage / CONFIG_NAME,
            MANIFEST_NAME: stage / MANIFEST_NAME,
        }
        _write_csv(cells, staged[CELLS_NAME])
        _write_csv(deltas, staged[DELTAS_NAME])
        _write_csv(membership, staged[MEMBERSHIP_NAME])
        run_config = _run_config(audit, controller_record, worker_record)
        staged[CONFIG_NAME].write_text(
            json.dumps(run_config, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        after = snapshot_paths(input_paths, root)
        assert_snapshots_unchanged(before, after)
        official_output = output_dir == (root / "models").resolve()
        labels = {
            path.resolve(): (f"models/{name}" if official_output else name)
            for name, path in staged.items()
        }
        generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        manifest = build_run_manifest(
            root=root,
            input_before=before,
            input_after=after,
            input_roles=input_roles,
            output_paths=[staged[CELLS_NAME], staged[DELTAS_NAME], staged[MEMBERSHIP_NAME], staged[CONFIG_NAME]],
            manifest_path=staged[MANIFEST_NAME],
            controller_probe=controller_record,
            worker_probe=worker_record,
            generated_at_utc=generated,
            elapsed_seconds=time.perf_counter() - start,
            path_labels=labels,
        )
        _write_csv(manifest, staged[MANIFEST_NAME])
        validate_staged_artifacts(staged, audit, run_config)

        # All scientific and lineage validation has completed. Publish the
        # manifest last and roll back the whole previous set if any replace fails.
        outputs = publish_output_set(
            staged,
            output_dir,
            (CELLS_NAME, DELTAS_NAME, MEMBERSHIP_NAME, CONFIG_NAME, MANIFEST_NAME),
        )
    return outputs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--probe-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--job", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.probe_worker:
        print(json.dumps(worker_probe(), sort_keys=True))
        return
    if args.worker:
        if args.job is None or args.worker_output is None:
            raise SystemExit("--worker requires --job and --worker-output")
        _worker_run(args.job, args.worker_output)
        return
    outputs = run_analysis(root=args.root, output_dir=args.output_dir)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
