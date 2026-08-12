"""Fail-closed schema loading and reconciliation for the frozen stability grid."""

from __future__ import annotations

import csv
import contextlib
import argparse
import hashlib
import io
import json
import logging
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Sequence

import pandas as pd
from scipy.stats import t
import tifffile


class StabilityGridIntegrityError(ValueError):
    """Raised when frozen stability-grid inputs cannot be reconciled exactly."""


SPEC_COLUMNS = (
    "cell_id", "marker", "canonical_cohort", "outcome_type", "primary_metric",
    "encoder", "sampling_seed", "tiles_per_slide", "target_mpp", "fold_file", "status",
)
ASSIGNMENT_COLUMNS = ("marker", "canonical_cohort", "case_id", "fold")
STANDARD_CELL_COLUMNS = (
    "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
    "n_slides", "n_patients", "slide_metric", "patient_metric", "status",
)
MARKER7_CELL_COLUMNS = (
    "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
    "n_source_patients", "n_patients", "n_events", "patient_metric", "status",
)
FOLD_COLUMNS = (
    "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
    "fold", "n_patients", "patient_metric",
)

RUNNER_SPECS = {
    "conch": {
        "markers": frozenset({"ar", "pten", "spop"}), "encoder": "CONCH",
        "canonical_cohort": "TCGA-PRAD", "cell_count": 90,
    },
    "virchow": {
        "markers": frozenset({"ar", "pten", "spop"}), "encoder": "Virchow",
        "canonical_cohort": "TCGA-PRAD", "cell_count": 90,
    },
    "nadt_conch": {
        "markers": frozenset({"gleason", "phenotype"}), "encoder": "CONCH",
        "canonical_cohort": "NADT-Prostate", "cell_count": 60,
    },
    "nadt_virchow": {
        "markers": frozenset({"gleason", "phenotype"}), "encoder": "Virchow",
        "canonical_cohort": "NADT-Prostate", "cell_count": 60,
    },
    "marker7_conch": {
        "markers": frozenset({"marker7"}), "encoder": "CONCH",
        "canonical_cohort": "LEOPARD-to-TCGA-PRAD", "cell_count": 30,
    },
    "marker7_virchow": {
        "markers": frozenset({"marker7"}), "encoder": "Virchow",
        "canonical_cohort": "LEOPARD-to-TCGA-PRAD", "cell_count": 30,
    },
}

CELL_CANONICAL_COLUMNS = SPEC_COLUMNS + (
    "raw_runner_dir", "raw_cell_results_path", "raw_cell_results_sha256", "raw_status",
    "reconciliation_status", "n_slides", "n_source_patients", "n_patients", "n_events",
    "slide_metric", "patient_metric",
)
FOLD_CANONICAL_COLUMNS = SPEC_COLUMNS + (
    "raw_runner_dir", "raw_fold_results_path", "raw_fold_results_sha256", "raw_status",
    "reconciliation_status", "fold", "fold_n_patients", "fold_patient_metric",
    "assignment_n_patients", "fold_assignment_reconciled",
)

FROZEN_MARKER_METRICS = {
    "ar": ("continuous", "patient_spearman_rho"),
    "gleason": ("continuous", "patient_spearman_rho"),
    "marker7": ("survival", "patient_c_index"),
    "phenotype": ("binary", "patient_auroc"),
    "pten": ("binary", "patient_auroc"),
    "spop": ("binary", "patient_auroc"),
}

STANDARD_COORDINATE_COLUMNS = (
    "file_name", "case_id", "encoder", "sampling_seed", "target_mpp", "pyramid_level",
    "level_mpp", "x", "y", "crop_size_native_px", "tissue_fraction", "tile_rank",
)
MARKER_COORDINATE_COLUMNS = ("cohort",) + STANDARD_COORDINATE_COLUMNS
TCGA_METADATA_COLUMNS = ("file_name", "case_id", "gleason_sum", "pten", "spop", "ar")
NADT_METADATA_COLUMNS = ("file_name", "patient_id", "phenotype", "gleason", "path")
MARKER_SOURCE_METADATA_COLUMNS = (
    "case_id", "event", "follow_up_years", "n_tiles", "file_name", "path",
)
MARKER_TARGET_METADATA_COLUMNS = ("file_name", "case_id", "path", "event", "follow_up_y")
COORDINATE_MANIFEST_COLUMNS = (
    "raw_runner_dir", "encoder", "sampling_seed", "target_mpp",
    "raw_coordinate_path", "raw_coordinate_sha256",
    "raw_metadata_path", "raw_metadata_sha256",
    "raw_source_metadata_path", "raw_source_metadata_sha256",
    "raw_target_metadata_path", "raw_target_metadata_sha256",
    "n_coordinate_rows", "n_slides", "n_patients", "pyramid_levels",
    "tile_rank_min", "tile_rank_max", "n_rank_violations",
    "coordinate_metadata_reconciled",
    "n_phenotype_evaluable_slides", "n_gleason_evaluable_slides",
    "n_gleason_evaluable_patients",
    "marker7_source_slides", "marker7_source_patients",
    "marker7_target_slides", "marker7_target_patients", "marker7_target_events",
)
COORDINATE_FILENAME = re.compile(r"^coordinates_s([0-9]+)_mpp([0-9]+\.[0-9]{2})\.csv$")
RUNNER_MPPS = {
    "conch": ("0.88", "1.76"),
    "virchow": ("0.44", "1.76"),
    "nadt_conch": ("0.88", "1.76"),
    "nadt_virchow": ("0.44", "1.76"),
    "marker7_conch": ("0.88", "1.76"),
    "marker7_virchow": ("0.44", "1.76"),
}
FROZEN_NADT_AFFECTED_TIFF_BASENAMES = {
    "1004.Prostate.Bx5A.slide.04.HE.tiff",
    "1004.Prostate.Bx7A.slide.04.HE.tiff",
}
LOG_SUMMARY_COLUMNS = (
    "log_name", "log_path", "log_sha256", "total_lines", "traceback_lines",
    "error_prefixed_lines", "warning_token_lines", "invalid_page_offset_lines",
    "invalid_page_offset_error_prefixed_lines", "invalid_page_offset_unprefixed_lines",
    "futurewarning_lines", "futurewarning_events", "resume_lines",
)
FULL_LOG_NAMES = {
    "marker7_conch.log", "marker7_virchow.log", "nadt_conch.log",
    "nadt_virchow.log", "tcga_conch.log", "tcga_virchow.log",
}
SUMMARY_COLUMNS = (
    "marker", "metric", "chance_value", "encoder", "tiles_per_slide", "target_mpp",
    "n_seeds", "mean", "sample_sd", "sampling_seed_t_ci_low",
    "sampling_seed_t_ci_high", "min", "max", "n_chance_or_worse",
    "chance_or_worse_rate", "seed_null_straddle", "n_ties", "outcome_type",
    "primary_metric", "null_value",
)
CONTRAST_COLUMNS = (
    "contrast", "pair_id", "cell_id_a", "cell_id_b", "marker", "outcome_type",
    "primary_metric", "sampling_seed", "encoder_a", "encoder_b",
    "tiles_per_slide_a", "tiles_per_slide_b", "target_mpp_a", "target_mpp_b",
    "patient_metric_a", "patient_metric_b", "delta_b_minus_a", "null_value",
    "metric_direction", "relation_a", "relation_b", "null_crossing", "exact_tie",
)
RUN_MANIFEST_COLUMNS = (
    "artifact_kind", "artifact_role", "runner", "artifact_path", "size_bytes",
    "mtime_ns", "sha256_before", "sha256_after", "hash_reconciled",
    "software_version", "included_in_output_sha256", "hash_exclusion_reason",
    "volatile_fields",
)
PROVENANCE_RELATIVE_PATHS = (
    "resources/projects/prostate_biomarker_validation/model_workspace/aggregate_stability_grid.py", "resources/projects/prostate_biomarker_validation/model_workspace/build_stability_grid_spec.py",
    "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_tcga.py", "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_nadt.py",
    "resources/projects/prostate_biomarker_validation/model_workspace/run_stability_marker7.py",
    "projects/prostate_biomarker_validation/docs/RUN_REPRODUCTION.md", "environment.yml",
    "requirements-lock.txt",
)
REPO_ROOT = Path(__file__).resolve().parents[4]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_exact_csv(path: Path, expected_columns: tuple[str, ...], label: str) -> pd.DataFrame:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle), None)
    except FileNotFoundError as error:
        raise StabilityGridIntegrityError(f"missing {label}: {path}") from error
    if header != list(expected_columns):
        raise StabilityGridIntegrityError(
            f"{label} header must exactly equal {list(expected_columns)!r}, got {header!r}"
        )
    return pd.read_csv(path)


def _read_exact_csv_strict(
    path: Path, expected_columns: tuple[str, ...], label: str
) -> pd.DataFrame:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except FileNotFoundError as error:
        raise StabilityGridIntegrityError(f"missing {label}: {path}") from error
    except UnicodeDecodeError as error:
        raise StabilityGridIntegrityError(f"{label} is not valid UTF-8: {path}") from error
    header = rows[0] if rows else None
    if header != list(expected_columns):
        raise StabilityGridIntegrityError(
            f"{label} header must exactly equal {list(expected_columns)!r}, got {header!r}"
        )
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected_columns):
            raise StabilityGridIntegrityError(
                f"{label} row {line_number} has {len(row)} fields, expected {len(expected_columns)}"
            )
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_spec(path: Path) -> pd.DataFrame:
    """Load the frozen cell specification without accepting header drift."""
    return _read_exact_csv(Path(path), SPEC_COLUMNS, "stability-grid spec")


def load_assignments(path: Path) -> pd.DataFrame:
    """Load frozen fold assignments without accepting header drift."""
    return _read_exact_csv(Path(path), ASSIGNMENT_COLUMNS, "stability-fold assignments")


def _runner_name(value: object) -> str:
    return Path(str(value)).name


def load_runner_results(run_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[Path]]:
    """Load one fixed runner's raw cells and folds, annotating immutable provenance."""
    run_root = Path(run_root)
    runner = run_root.name
    if runner not in RUNNER_SPECS:
        raise StabilityGridIntegrityError(f"unexpected runner directory: {run_root}")
    cell_path = run_root / "cell_results.csv"
    fold_path = run_root / "fold_results.csv"
    expected_cells = MARKER7_CELL_COLUMNS if runner.startswith("marker7_") else STANDARD_CELL_COLUMNS
    cells = _read_exact_csv(cell_path, expected_cells, f"{runner} cell-results")
    folds = _read_exact_csv(fold_path, FOLD_COLUMNS, f"{runner} fold-results")
    cells = cells.assign(
        raw_runner_dir=runner,
        raw_cell_results_path=str(cell_path),
        raw_cell_results_sha256=_sha256(cell_path),
    )
    folds = folds.assign(
        raw_runner_dir=runner,
        raw_fold_results_path=str(fold_path),
        raw_fold_results_sha256=_sha256(fold_path),
    )
    return cells, folds, [cell_path, fold_path]


def _mpp(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise StabilityGridIntegrityError(f"target_mpp is not numeric: {value!r}") from error
    if not math.isfinite(numeric):
        raise StabilityGridIntegrityError(f"target_mpp is not finite: {value!r}")
    return f"{numeric:.2f}"


def _integer(value: object, column: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise StabilityGridIntegrityError(f"{column} is not an integer: {value!r}") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise StabilityGridIntegrityError(f"{column} is not an integer: {value!r}")
    return int(numeric)


def _nonblank(value: object, column: str) -> str:
    text = str(value).strip()
    if not text:
        raise StabilityGridIntegrityError(f"{column} must be nonblank")
    return text


def _finite_number(value: object, column: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise StabilityGridIntegrityError(f"{column} must be finite: {value!r}") from error
    if not math.isfinite(numeric):
        raise StabilityGridIntegrityError(f"{column} must be finite: {value!r}")
    return numeric


def _expected_coordinate_inputs(run_root: Path) -> tuple[set[Path], set[Path]]:
    coordinates: set[Path] = set()
    metadata: set[Path] = set()
    for runner, mpps in RUNNER_MPPS.items():
        for seed in range(5):
            for mpp in mpps:
                suffix = f"s{seed}_mpp{mpp}"
                runner_root = run_root / runner
                coordinates.add(runner_root / f"coordinates_{suffix}.csv")
                if runner.startswith("marker7_"):
                    metadata.add(runner_root / f"source_meta_{suffix}.csv")
                    metadata.add(runner_root / f"target_meta_{suffix}.csv")
                else:
                    metadata.add(runner_root / f"meta_{suffix}.csv")
    return coordinates, metadata


def _discover_coordinate_inputs(
    run_root: Path, *, require_full_grid: bool
) -> tuple[list[tuple[str, Path, int, str, tuple[Path, ...]]], list[Path]]:
    run_root = Path(run_root)
    if not run_root.is_dir():
        raise StabilityGridIntegrityError(f"missing coordinate run root: {run_root}")
    for candidate in run_root.iterdir():
        if not candidate.is_dir() or candidate.name in RUNNER_SPECS:
            continue
        relevant = list(candidate.glob("coordinates*.csv"))
        relevant += list(candidate.glob("meta*.csv"))
        relevant += list(candidate.glob("source_meta*.csv"))
        relevant += list(candidate.glob("target_meta*.csv"))
        if relevant:
            raise StabilityGridIntegrityError(
                f"unexpected coordinate runner directory: {candidate.name}"
            )
    discovered_coordinates: set[Path] = set()
    discovered_metadata: set[Path] = set()
    for runner in RUNNER_SPECS:
        runner_root = run_root / runner
        if not runner_root.is_dir():
            continue
        discovered_coordinates.update(runner_root.glob("coordinates*.csv"))
        discovered_metadata.update(runner_root.glob("meta*.csv"))
        discovered_metadata.update(runner_root.glob("source_meta*.csv"))
        discovered_metadata.update(runner_root.glob("target_meta*.csv"))
    if not discovered_coordinates:
        raise StabilityGridIntegrityError("no coordinate shards were discovered")
    if require_full_grid:
        expected_coordinates, expected_metadata = _expected_coordinate_inputs(run_root)
        if discovered_coordinates != expected_coordinates:
            raise StabilityGridIntegrityError(
                "full-grid coordinate shard filename set does not exactly match the frozen axes"
            )
        if discovered_metadata != expected_metadata:
            raise StabilityGridIntegrityError(
                "full-grid metadata filename set does not exactly match the coordinate axes"
            )

    shards = []
    expected_metadata: set[Path] = set()
    for coordinate_path in sorted(discovered_coordinates, key=lambda path: path.as_posix()):
        runner = coordinate_path.parent.name
        if runner not in RUNNER_SPECS:
            raise StabilityGridIntegrityError(f"unexpected coordinate runner: {runner}")
        match = COORDINATE_FILENAME.fullmatch(coordinate_path.name)
        if match is None:
            raise StabilityGridIntegrityError(f"malformed coordinate filename: {coordinate_path.name}")
        seed = _integer(match.group(1), "filename sampling seed")
        mpp = _mpp(match.group(2))
        if seed not in range(5) or mpp not in RUNNER_MPPS[runner]:
            raise StabilityGridIntegrityError(
                f"coordinate filename seed/MPP is outside the frozen {runner} axes"
            )
        suffix = f"s{seed}_mpp{mpp}"
        if runner.startswith("marker7_"):
            metadata_paths = (
                coordinate_path.parent / f"source_meta_{suffix}.csv",
                coordinate_path.parent / f"target_meta_{suffix}.csv",
            )
        else:
            metadata_paths = (coordinate_path.parent / f"meta_{suffix}.csv",)
        expected_metadata.update(metadata_paths)
        shards.append((runner, coordinate_path, seed, mpp, metadata_paths))
    if discovered_metadata != expected_metadata:
        raise StabilityGridIntegrityError(
            "coordinate metadata paths do not exactly match discovered shard stems"
        )
    consumed = sorted(
        discovered_coordinates | discovered_metadata, key=lambda path: path.as_posix()
    )
    return shards, consumed


def _validate_coordinate_rows(
    coordinates: pd.DataFrame,
    *,
    runner: str,
    seed: int,
    mpp: str,
    marker7: bool,
) -> tuple[pd.DataFrame, list[str]]:
    coordinates = coordinates.copy()
    if coordinates.empty:
        raise StabilityGridIntegrityError("empty coordinate shard is not evaluable")
    expected_encoder = RUNNER_SPECS[runner]["encoder"]
    for column in ("file_name", "case_id"):
        coordinates[column] = coordinates[column].map(lambda value: _nonblank(value, column))
    if marker7:
        coordinates["cohort"] = coordinates["cohort"].map(
            lambda value: _nonblank(value, "cohort")
        )
        cohorts = set(coordinates["cohort"])
        if not cohorts.issubset({"LEOPARD", "TCGA-PRAD"}):
            raise StabilityGridIntegrityError(f"unexpected marker7 coordinate cohort: {cohorts!r}")
    if not coordinates["encoder"].eq(expected_encoder).all():
        raise StabilityGridIntegrityError(f"coordinate row encoder disagrees with runner {runner}")
    coordinates["sampling_seed"] = coordinates["sampling_seed"].map(
        lambda value: _integer(value, "sampling_seed")
    )
    if not coordinates["sampling_seed"].eq(seed).all():
        raise StabilityGridIntegrityError("coordinate row sampling seed disagrees with filename")
    if not coordinates["target_mpp"].map(_mpp).eq(mpp).all():
        raise StabilityGridIntegrityError("coordinate row MPP disagrees with filename")
    for column in ("tile_rank", "pyramid_level", "x", "y", "crop_size_native_px"):
        coordinates[column] = coordinates[column].map(lambda value: _integer(value, column))
    if (coordinates[["tile_rank", "pyramid_level", "x", "y"]] < 0).any().any():
        raise StabilityGridIntegrityError("coordinate ranks, levels, and positions must be nonnegative")
    if coordinates["crop_size_native_px"].le(0).any():
        raise StabilityGridIntegrityError("coordinate crop size must be positive")
    coordinates["level_mpp"] = coordinates["level_mpp"].map(
        lambda value: _finite_number(value, "level_mpp")
    )
    coordinates["tissue_fraction"] = coordinates["tissue_fraction"].map(
        lambda value: _finite_number(value, "tissue_fraction")
    )
    if not coordinates["tissue_fraction"].between(0.0, 1.0).all():
        raise StabilityGridIntegrityError("coordinate tissue fraction must be within [0, 1]")
    entity_columns = ["cohort", "file_name", "case_id"] if marker7 else ["file_name", "case_id"]
    rank_key = entity_columns + ["tile_rank"]
    if coordinates.duplicated(rank_key).any():
        raise StabilityGridIntegrityError("coordinate shard contains duplicate normalized tile ranks")
    expected_ranks = set(range(64))
    for entity, group in coordinates.groupby(entity_columns, dropna=False, sort=False):
        if len(group) != 64 or set(group["tile_rank"]) != expected_ranks:
            raise StabilityGridIntegrityError(
                f"coordinate entity {entity!r} must contain exactly 64 rows and ranks 0 through 63"
            )
    return coordinates, entity_columns


def _metadata_keys(metadata: pd.DataFrame, columns: list[str], label: str) -> set[tuple]:
    for column in columns:
        metadata[column] = metadata[column].map(lambda value: _nonblank(value, column))
    if metadata.duplicated(columns).any():
        raise StabilityGridIntegrityError(f"{label} contains duplicate metadata entity keys")
    return set(metadata.loc[:, columns].itertuples(index=False, name=None))


def _validate_full_coordinate_invariants(
    manifest: pd.DataFrame, source_case_sets: list[set[str]]
) -> dict:
    if len(manifest) != 60:
        raise StabilityGridIntegrityError("full coordinate grid must contain exactly 60 shards")
    tcga = manifest[manifest["raw_runner_dir"].isin(["conch", "virchow"])]
    nadt = manifest[manifest["raw_runner_dir"].isin(["nadt_conch", "nadt_virchow"])]
    marker = manifest[manifest["raw_runner_dir"].isin(["marker7_conch", "marker7_virchow"])]
    if len(tcga) != 20 or not (
        tcga["n_coordinate_rows"].eq(19200).all()
        and tcga["n_slides"].eq(300).all()
        and tcga["n_patients"].eq(273).all()
    ):
        raise StabilityGridIntegrityError("full TCGA coordinate cohort must be 19,200/300/273 per shard")
    if len(nadt) != 20 or not (
        nadt["n_coordinate_rows"].eq(29632).all()
        and nadt["n_slides"].eq(463).all()
        and nadt["n_patients"].eq(39).all()
        and nadt["n_phenotype_evaluable_slides"].eq(463).all()
        and nadt["n_gleason_evaluable_slides"].eq(334).all()
        and nadt["n_gleason_evaluable_patients"].eq(39).all()
    ):
        raise StabilityGridIntegrityError("full NADT coordinate cohort must be 29,632/463/39 with 334/39 Gleason")
    if len(marker) != 20 or not (
        marker["marker7_target_slides"].eq(297).all()
        and marker["marker7_target_patients"].eq(270).all()
        and marker["marker7_target_events"].eq(57).all()
    ):
        raise StabilityGridIntegrityError("full marker7 target cohort must be 297/270/57 per shard")
    source_counts = [len(case_ids) for case_ids in source_case_sets]
    if len(source_counts) != 20 or not all(498 <= count <= 502 for count in source_counts):
        raise StabilityGridIntegrityError("marker7 source retention must be 498 through 502 per shard")
    common_source = len(set.intersection(*source_case_sets))
    if common_source != 498:
        raise StabilityGridIntegrityError("marker7 common source intersection must equal 498")
    conch_counts = marker.loc[marker["raw_runner_dir"].eq("marker7_conch"), "marker7_source_patients"]
    virchow_counts = marker.loc[marker["raw_runner_dir"].eq("marker7_virchow"), "marker7_source_patients"]
    if not conch_counts.between(498, 500).all() or not virchow_counts.between(499, 502).all():
        raise StabilityGridIntegrityError("marker7 encoder-specific source retention is outside frozen ranges")
    return {
        "full_mode_assertions_passed": True,
        "tcga_shards_asserted": 20,
        "nadt_shards_asserted": 20,
        "marker7_shards_asserted": 20,
        "marker7_source_min_patients": int(min(source_counts)),
        "marker7_source_max_patients": int(max(source_counts)),
        "marker7_common_source_patients": int(common_source),
        "marker7_source_retention_varies": bool(len(set(source_counts)) > 1),
        "marker7_source_retention_limitation": (
            "source retention varies by configuration within the accepted frozen range"
        ),
    }


def build_coordinate_manifest(
    run_root: Path, *, require_full_grid: bool
) -> tuple[pd.DataFrame, dict, list[Path]]:
    """Validate coordinate shards in place and return one deterministic row per shard."""
    shards, consumed_paths = _discover_coordinate_inputs(
        Path(run_root), require_full_grid=require_full_grid
    )
    rows = []
    source_case_sets: list[set[str]] = []
    for runner, coordinate_path, seed, mpp, metadata_paths in shards:
        marker7 = runner.startswith("marker7_")
        coordinate_columns = MARKER_COORDINATE_COLUMNS if marker7 else STANDARD_COORDINATE_COLUMNS
        coordinates = _read_exact_csv_strict(
            coordinate_path, coordinate_columns, f"{runner} coordinate shard"
        )
        coordinates, entity_columns = _validate_coordinate_rows(
            coordinates, runner=runner, seed=seed, mpp=mpp, marker7=marker7
        )
        coordinate_keys = set(
            coordinates.loc[:, entity_columns].itertuples(index=False, name=None)
        )
        row = {column: pd.NA for column in COORDINATE_MANIFEST_COLUMNS}
        row.update(
            raw_runner_dir=runner,
            encoder=RUNNER_SPECS[runner]["encoder"],
            sampling_seed=seed,
            target_mpp=float(mpp),
            raw_coordinate_path=str(coordinate_path),
            raw_coordinate_sha256=_sha256(coordinate_path),
            n_coordinate_rows=int(len(coordinates)),
            n_slides=int(len(coordinate_keys)),
            n_patients=int(coordinates["case_id"].nunique()),
            pyramid_levels=json.dumps(sorted(int(value) for value in coordinates["pyramid_level"].unique())),
            tile_rank_min=int(coordinates["tile_rank"].min()),
            tile_rank_max=int(coordinates["tile_rank"].max()),
            n_rank_violations=0,
            coordinate_metadata_reconciled=True,
        )
        if marker7:
            source_path, target_path = metadata_paths
            source = _read_exact_csv_strict(
                source_path, MARKER_SOURCE_METADATA_COLUMNS, f"{runner} source metadata"
            )
            target = _read_exact_csv_strict(
                target_path, MARKER_TARGET_METADATA_COLUMNS, f"{runner} target metadata"
            )
            source_keys_plain = _metadata_keys(source, ["file_name", "case_id"], "marker7 source")
            target_keys_plain = _metadata_keys(target, ["file_name", "case_id"], "marker7 target")
            if source_keys_plain & target_keys_plain:
                raise StabilityGridIntegrityError("marker7 source/target metadata cohort collision")
            source_keys = {("LEOPARD", *key) for key in source_keys_plain}
            target_keys = {("TCGA-PRAD", *key) for key in target_keys_plain}
            if coordinate_keys != source_keys | target_keys:
                raise StabilityGridIntegrityError("marker7 coordinate/metadata entity sets disagree")
            event_counts = target.groupby("case_id", dropna=False)["event"].nunique(dropna=False)
            if not event_counts.eq(1).all():
                raise StabilityGridIntegrityError("marker7 target patient event labels are inconsistent")
            target_events = target.assign(
                _event=target["event"].map(lambda value: _integer(value, "event"))
            ).drop_duplicates("case_id")["_event"]
            if not target_events.isin([0, 1]).all():
                raise StabilityGridIntegrityError("marker7 target event labels must be binary")
            source_cases = set(source["case_id"])
            source_case_sets.append(source_cases)
            row.update(
                raw_source_metadata_path=str(source_path),
                raw_source_metadata_sha256=_sha256(source_path),
                raw_target_metadata_path=str(target_path),
                raw_target_metadata_sha256=_sha256(target_path),
                marker7_source_slides=int(len(source_keys_plain)),
                marker7_source_patients=int(len(source_cases)),
                marker7_target_slides=int(len(target_keys_plain)),
                marker7_target_patients=int(target["case_id"].nunique()),
                marker7_target_events=int(target_events.sum()),
            )
        else:
            metadata_path = metadata_paths[0]
            if runner.startswith("nadt_"):
                metadata = _read_exact_csv_strict(
                    metadata_path, NADT_METADATA_COLUMNS, f"{runner} metadata"
                )
                metadata = metadata.copy()
                metadata["case_id"] = metadata["patient_id"]
                phenotype_evaluable = metadata["phenotype"].map(lambda value: bool(str(value).strip()))
                gleason_evaluable = metadata["gleason"].map(lambda value: bool(str(value).strip()))
                row.update(
                    n_phenotype_evaluable_slides=int(phenotype_evaluable.sum()),
                    n_gleason_evaluable_slides=int(gleason_evaluable.sum()),
                    n_gleason_evaluable_patients=int(
                        metadata.loc[gleason_evaluable, "case_id"].nunique()
                    ),
                )
            else:
                metadata = _read_exact_csv_strict(
                    metadata_path, TCGA_METADATA_COLUMNS, f"{runner} metadata"
                )
            metadata_keys = _metadata_keys(metadata, ["file_name", "case_id"], f"{runner}")
            if coordinate_keys != metadata_keys:
                raise StabilityGridIntegrityError("coordinate/metadata entity sets disagree")
            row.update(
                raw_metadata_path=str(metadata_path),
                raw_metadata_sha256=_sha256(metadata_path),
            )
        rows.append(row)
    manifest = pd.DataFrame(rows, columns=COORDINATE_MANIFEST_COLUMNS).sort_values(
        ["raw_runner_dir", "sampling_seed", "target_mpp"], kind="stable"
    ).reset_index(drop=True)
    source_counts = [len(case_ids) for case_ids in source_case_sets]
    qc = {
        "coordinate_shards": int(len(manifest)),
        "coordinate_rows": int(manifest["n_coordinate_rows"].sum()),
        "coordinate_rank_violations": 0,
        "coordinate_metadata_violations": 0,
        "coordinate_input_paths": int(len(consumed_paths)),
        "marker7_source_min_patients": int(min(source_counts)) if source_counts else None,
        "marker7_source_max_patients": int(max(source_counts)) if source_counts else None,
        "marker7_common_source_patients": (
            int(len(set.intersection(*source_case_sets))) if source_case_sets else None
        ),
        "marker7_source_retention_varies": (
            bool(len(set(source_counts)) > 1) if source_counts else False
        ),
    }
    if require_full_grid:
        if len(consumed_paths) != 140:
            raise StabilityGridIntegrityError("full coordinate grid must consume exactly 140 paths")
        qc.update(_validate_full_coordinate_invariants(manifest, source_case_sets))
    else:
        qc["full_mode_assertions_passed"] = False
    return manifest, qc, consumed_paths


def summarize_logs(log_root: Path) -> tuple[pd.DataFrame, dict, list[Path]]:
    """Summarize historical physical log lines without treating them as run-lifetime events."""
    log_root = Path(log_root)
    if not log_root.is_dir():
        raise StabilityGridIntegrityError(f"missing log root: {log_root}")
    paths = sorted(log_root.glob("*.log"), key=lambda path: path.as_posix())
    if not paths:
        raise StabilityGridIntegrityError(f"no log files found under: {log_root}")
    rows = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            raise StabilityGridIntegrityError(f"cannot read UTF-8 log: {path}") from error
        invalid = ["invalid page offset" in line.lower() for line in lines]
        prefixed_offset = [
            is_invalid and line.startswith("ERROR:tifffile")
            for line, is_invalid in zip(lines, invalid, strict=True)
        ]
        rows.append(
            {
                "log_name": path.name,
                "log_path": str(path),
                "log_sha256": _sha256(path),
                "total_lines": len(lines),
                "traceback_lines": sum(line.startswith("Traceback (") for line in lines),
                "error_prefixed_lines": sum(line.startswith("ERROR:") for line in lines),
                "warning_token_lines": sum("warning" in line.lower() for line in lines),
                "invalid_page_offset_lines": sum(invalid),
                "invalid_page_offset_error_prefixed_lines": sum(prefixed_offset),
                "invalid_page_offset_unprefixed_lines": sum(
                    is_invalid and not is_prefixed
                    for is_invalid, is_prefixed in zip(invalid, prefixed_offset, strict=True)
                ),
                "futurewarning_lines": sum("FutureWarning" in line for line in lines),
                "futurewarning_events": sum("FutureWarning:" in line for line in lines),
                "resume_lines": sum(line.startswith("[resume]") for line in lines),
            }
        )
    summary = pd.DataFrame(rows, columns=LOG_SUMMARY_COLUMNS).sort_values(
        "log_name", kind="stable"
    ).reset_index(drop=True)
    count_columns = [column for column in LOG_SUMMARY_COLUMNS if column.endswith("_lines")]
    qc = {f"total_{column}": int(summary[column].sum()) for column in count_columns}
    qc.update(
        total_log_files=int(len(summary)),
        total_futurewarning_events=int(summary["futurewarning_events"].sum()),
        historical_log_observations_nonfatal=True,
        log_count_limitation=(
            "Counts are observed physical lines in append/resume logs, not complete lifetime "
            "event totals; migration occurred after completed cells and no run-level code/config "
            "manifest is available."
        ),
    )
    return summary, qc, paths


class _MessageHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _build_warning_slide_retention(
    affected_paths: Sequence[Path],
    coordinate_paths: Sequence[Path],
    *,
    require_full_grid: bool,
) -> dict:
    """Join affected NADT basenames to coordinate ranks and used levels without pixel access."""
    affected = sorted({Path(path) for path in affected_paths}, key=lambda path: path.as_posix())
    by_name = {path.name: path for path in affected}
    if len(by_name) != len(affected):
        raise StabilityGridIntegrityError("affected TIFF basenames must be unique")
    if require_full_grid:
        if len(affected) != 2:
            raise StabilityGridIntegrityError(
                "full warning-slide retention requires exact two frozen affected TIFF slides"
            )
        if set(by_name) != FROZEN_NADT_AFFECTED_TIFF_BASENAMES:
            raise StabilityGridIntegrityError(
                "full warning-slide retention requires the frozen affected TIFF basenames"
            )
    coordinates = sorted({Path(path) for path in coordinate_paths}, key=lambda path: path.as_posix())
    expected_levels = {
        ("nadt_conch", "0.88"): 2,
        ("nadt_conch", "1.76"): 3,
        ("nadt_virchow", "0.44"): 1,
        ("nadt_virchow", "1.76"): 3,
    }
    observed_axes = set()
    details = []
    for coordinate_path in coordinates:
        runner = coordinate_path.parent.name
        if runner not in {"nadt_conch", "nadt_virchow"}:
            raise StabilityGridIntegrityError(
                f"warning-slide retention received non-NADT coordinate shard: {coordinate_path}"
            )
        match = COORDINATE_FILENAME.fullmatch(coordinate_path.name)
        if match is None:
            raise StabilityGridIntegrityError(
                f"malformed warning-slide coordinate filename: {coordinate_path.name}"
            )
        seed = _integer(match.group(1), "filename sampling seed")
        mpp = _mpp(match.group(2))
        observed_axes.add((runner, seed, mpp))
        frame = _read_exact_csv_strict(
            coordinate_path, STANDARD_COORDINATE_COLUMNS, "NADT warning-slide coordinate shard"
        )
        frame, _ = _validate_coordinate_rows(
            frame, runner=runner, seed=seed, mpp=mpp, marker7=False
        )
        for file_name, affected_path in by_name.items():
            retained = frame.loc[frame["file_name"].eq(file_name)]
            if len(retained) != 64 or set(retained["tile_rank"]) != set(range(64)):
                raise StabilityGridIntegrityError(
                    f"warning slide {file_name!r} must retain 64 ranks in {coordinate_path.name}"
                )
            levels = sorted(int(value) for value in retained["pyramid_level"].unique())
            expected_level = expected_levels.get((runner, mpp))
            if levels != [expected_level]:
                raise StabilityGridIntegrityError(
                    f"warning slide {file_name!r} used level {levels!r}, expected {expected_level}"
                )
            details.append(
                {
                    "affected_path": affected_path.as_posix(),
                    "file_name": file_name,
                    "raw_runner_dir": runner,
                    "sampling_seed": seed,
                    "target_mpp": float(mpp),
                    "coordinate_path": coordinate_path.as_posix(),
                    "n_coordinate_rows": 64,
                    "tile_rank_min": 0,
                    "tile_rank_max": 63,
                    "used_pyramid_level": expected_level,
                }
            )
    if require_full_grid:
        expected_axes = {
            (runner, seed, mpp)
            for (runner, mpp) in expected_levels
            for seed in range(5)
        }
        if observed_axes != expected_axes or len(coordinates) != 20:
            raise StabilityGridIntegrityError(
                "warning-slide retention must cover the exact 20 NADT coordinate shards"
            )
        expected_details = len(affected) * 20
        if len(details) != expected_details:
            raise StabilityGridIntegrityError(
                "every warning slide must be retained in all 20 NADT coordinate shards"
            )
    details.sort(
        key=lambda row: (
            row["file_name"], row["raw_runner_dir"], row["sampling_seed"], row["target_mpp"]
        )
    )
    return {
        "warning_slide_count": int(len(affected)),
        "nadt_coordinate_shards": int(len(coordinates)),
        "retention_details": details,
        "all_warning_slides_retained_in_all_shards": bool(
            len(details) == len(affected) * len(coordinates)
        ),
    }


def scan_nadt_tiff_headers(paths: Sequence[Path]) -> dict:
    """Enumerate TIFF headers only and associate captured messages with the current path."""
    requested = sorted({Path(path) for path in paths}, key=lambda path: path.as_posix())
    affected = []
    failures = []
    scanned = 0
    message_count = 0
    logger = logging.getLogger("tifffile")
    for path in requested:
        handler = _MessageHandler()
        previous = (logger.level, logger.disabled, logger.propagate, list(logger.handlers))
        stderr = io.StringIO()
        try:
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.disabled = False
            with contextlib.redirect_stderr(stderr):
                with tifffile.TiffFile(path) as tiff:
                    for page in tiff.pages:
                        _ = page.shape
                        _ = len(page.tags)
            scanned += 1
        except (OSError, ValueError, tifffile.TiffFileError) as error:
            failures.append({"path": path.as_posix(), "error": f"{type(error).__name__}: {error}"})
        finally:
            logger.handlers[:] = previous[3]
            logger.setLevel(previous[0])
            logger.disabled = previous[1]
            logger.propagate = previous[2]
        stderr_messages = [line.strip() for line in stderr.getvalue().splitlines() if line.strip()]
        messages = sorted(set(handler.messages + stderr_messages))
        message_count += len(messages)
        if messages:
            affected.append({"path": path.as_posix(), "messages": messages})
    return {
        "requested_paths": [path.as_posix() for path in requested],
        "requested_path_count": int(len(requested)),
        "scanned_path_count": int(scanned),
        "scan_failure_count": int(len(failures)),
        "scan_complete": bool(scanned == len(requested) and not failures),
        "header_message_count": int(message_count),
        "affected_slide_count": int(len(affected)),
        "affected_slides": affected,
        "scan_failures": failures,
        "limitation": "Header-scan messages observed; pixel-level impact was not assessed.",
    }


def _reconstructed_cell_id(row: pd.Series) -> str:
    return (
        f"{row['marker']}__{str(row['encoder']).lower()}__s{_integer(row['sampling_seed'], 'sampling_seed')}"
        f"__t{_integer(row['tiles_per_slide'], 'tiles_per_slide')}__mpp{_mpp(row['target_mpp'])}"
    )


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise StabilityGridIntegrityError(f"{label} is missing required columns: {missing}")


def _require_finite(frame: pd.DataFrame, column: str, label: str) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    if not values.map(math.isfinite).all():
        raise StabilityGridIntegrityError(f"{column} must be finite for every {label}")


def _null_value(primary_metric: object) -> float:
    thresholds = {
        "patient_auroc": 0.5,
        "patient_c_index": 0.5,
        "patient_spearman_rho": 0.0,
    }
    try:
        return thresholds[str(primary_metric)]
    except KeyError as error:
        raise StabilityGridIntegrityError(
            f"unsupported primary metric for null comparison: {primary_metric!r}"
        ) from error


def _validate_marker_metric_metadata(cells: pd.DataFrame) -> None:
    for marker, group in cells.groupby("marker", dropna=False, sort=False):
        pairs = group[["outcome_type", "primary_metric"]].drop_duplicates()
        if len(pairs) != 1:
            raise StabilityGridIntegrityError(
                f"marker {marker!r} metric metadata must be consistent across all cells"
            )
        expected = FROZEN_MARKER_METRICS.get(marker)
        observed = tuple(pairs.iloc[0])
        if expected is None or observed != expected:
            raise StabilityGridIntegrityError(
                f"frozen marker metadata mismatch for {marker!r}: expected {expected!r}, "
                f"got {observed!r}"
            )


def build_stability_summary(cells: pd.DataFrame) -> pd.DataFrame:
    """Summarize the five sampling-seed results in each frozen grid cell family."""
    group_columns = ["marker", "encoder", "tiles_per_slide", "target_mpp"]
    _require_columns(
        cells,
        tuple(group_columns + ["outcome_type", "primary_metric", "sampling_seed", "patient_metric"]),
        "canonical cells",
    )
    _validate_marker_metric_metadata(cells)
    cells = cells.copy()
    cells["sampling_seed"] = cells["sampling_seed"].map(
        lambda value: _integer(value, "sampling_seed")
    )
    _require_finite(cells, "patient_metric", "canonical cell")
    rows = []
    for key, group in cells.groupby(group_columns, dropna=False, sort=False):
        seeds = group["sampling_seed"].tolist()
        if len(seeds) != 5 or set(seeds) != set(range(5)):
            raise StabilityGridIntegrityError(
                f"summary group {key!r} must contain exactly sampling seeds 0 through 4"
            )
        if group["outcome_type"].nunique(dropna=False) != 1 or group[
            "primary_metric"
        ].nunique(dropna=False) != 1:
            raise StabilityGridIntegrityError(f"summary group {key!r} has inconsistent metric metadata")
        metrics = pd.to_numeric(group["patient_metric"])
        mean = float(metrics.mean())
        sample_sd = float(metrics.std(ddof=1))
        half_width = float(t.ppf(0.975, len(seeds) - 1) * sample_sd / math.sqrt(len(seeds)))
        null_value = _null_value(group["primary_metric"].iloc[0])
        rows.append(
            {
                "marker": key[0],
                "metric": group["primary_metric"].iloc[0],
                "chance_value": null_value,
                "encoder": key[1],
                "tiles_per_slide": key[2],
                "target_mpp": key[3],
                "n_seeds": len(seeds),
                "mean": mean,
                "sample_sd": sample_sd,
                "sampling_seed_t_ci_low": mean - half_width,
                "sampling_seed_t_ci_high": mean + half_width,
                "min": float(metrics.min()),
                "max": float(metrics.max()),
                "n_chance_or_worse": int(metrics.le(null_value).sum()),
                "chance_or_worse_rate": float(metrics.le(null_value).mean()),
                "seed_null_straddle": bool(
                    metrics.lt(null_value).any() and metrics.gt(null_value).any()
                ),
                "n_ties": int(metrics.eq(null_value).sum()),
                "outcome_type": group["outcome_type"].iloc[0],
                "primary_metric": group["primary_metric"].iloc[0],
                "null_value": null_value,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["marker", "encoder", "tiles_per_slide", "target_mpp"], kind="stable"
    ).reset_index(drop=True)


def _null_relation(value: float, null_value: float) -> str:
    if value < null_value:
        return "below_null"
    if value > null_value:
        return "above_null"
    return "at_null"


def _contrast_row(contrast: str, pair_id: str, row_a: pd.Series, row_b: pd.Series) -> dict:
    for column in ("marker", "outcome_type", "primary_metric", "sampling_seed"):
        if row_a[column] != row_b[column]:
            raise StabilityGridIntegrityError(
                f"{contrast} pair {pair_id!r} has inconsistent {column} metadata"
            )
    metric_a = float(row_a["patient_metric"])
    metric_b = float(row_b["patient_metric"])
    null_value = _null_value(row_a["primary_metric"])
    relation_a = _null_relation(metric_a, null_value)
    relation_b = _null_relation(metric_b, null_value)
    return {
        "contrast": contrast,
        "pair_id": pair_id,
        "cell_id_a": row_a["cell_id"],
        "cell_id_b": row_b["cell_id"],
        "marker": row_a["marker"],
        "outcome_type": row_a["outcome_type"],
        "primary_metric": row_a["primary_metric"],
        "sampling_seed": int(row_a["sampling_seed"]),
        "encoder_a": row_a["encoder"],
        "encoder_b": row_b["encoder"],
        "tiles_per_slide_a": int(row_a["tiles_per_slide"]),
        "tiles_per_slide_b": int(row_b["tiles_per_slide"]),
        "target_mpp_a": float(row_a["target_mpp"]),
        "target_mpp_b": float(row_b["target_mpp"]),
        "patient_metric_a": metric_a,
        "patient_metric_b": metric_b,
        "delta_b_minus_a": metric_b - metric_a,
        "null_value": null_value,
        "metric_direction": "higher_is_better",
        "relation_a": relation_a,
        "relation_b": relation_b,
        "null_crossing": bool(
            {relation_a, relation_b} == {"below_null", "above_null"}
        ),
        "exact_tie": bool(metric_a == metric_b),
    }


def build_stability_contrasts(cells: pd.DataFrame) -> pd.DataFrame:
    """Build frozen within-seed scale, encoder, and tile-count contrasts."""
    required = (
        "cell_id", "marker", "outcome_type", "primary_metric", "encoder", "sampling_seed",
        "tiles_per_slide", "target_mpp", "patient_metric",
    )
    _require_columns(cells, required, "canonical cells")
    _validate_marker_metric_metadata(cells)
    cells = cells.copy()
    cells["sampling_seed"] = cells["sampling_seed"].map(
        lambda value: _integer(value, "sampling_seed")
    )
    cells["tiles_per_slide"] = cells["tiles_per_slide"].map(
        lambda value: _integer(value, "tiles_per_slide")
    )
    cells["_target_mpp_key"] = cells["target_mpp"].map(_mpp)
    _require_finite(cells, "patient_metric", "canonical cell")
    grid_key = ["marker", "encoder", "sampling_seed", "tiles_per_slide", "_target_mpp_key"]
    if cells.duplicated(grid_key).any():
        raise StabilityGridIntegrityError("canonical cells contain duplicate contrast keys")

    rows = []
    native_mpp = {"CONCH": "0.88", "Virchow": "0.44"}
    native_groups = cells.groupby(
        ["marker", "encoder", "sampling_seed", "tiles_per_slide"],
        dropna=False,
        sort=True,
    )
    for (marker, encoder, seed, tiles), group in native_groups:
        if encoder not in native_mpp:
            raise StabilityGridIntegrityError(f"unsupported encoder in contrast grid: {encoder!r}")
        by_mpp = group.set_index("_target_mpp_key")
        expected_mpps = {native_mpp[encoder], "1.76"}
        if set(by_mpp.index) != expected_mpps:
            raise StabilityGridIntegrityError(
                f"native contrast group {(marker, encoder, seed, tiles)!r} must contain {expected_mpps}"
            )
        pair_id = (
            f"native_vs_1.76__{marker}__{str(encoder).lower()}__s{seed}__t{tiles}"
        )
        rows.append(
            _contrast_row(
                "native_vs_1.76",
                pair_id,
                by_mpp.loc[native_mpp[encoder]],
                by_mpp.loc["1.76"],
            )
        )

    shared = cells.loc[cells["_target_mpp_key"].eq("1.76")]
    shared_groups = shared.groupby(
        ["marker", "sampling_seed", "tiles_per_slide"], dropna=False, sort=True
    )
    for (marker, seed, tiles), group in shared_groups:
        by_encoder = group.set_index("encoder", drop=False)
        if set(by_encoder.index) != {"CONCH", "Virchow"}:
            raise StabilityGridIntegrityError(
                f"shared-scale contrast group {(marker, seed, tiles)!r} must contain both encoders"
            )
        pair_id = f"virchow_vs_conch_at_1.76__{marker}__s{seed}__t{tiles}"
        rows.append(
            _contrast_row(
                "virchow_vs_conch_at_1.76",
                pair_id,
                by_encoder.loc["CONCH"],
                by_encoder.loc["Virchow"],
            )
        )

    tile_groups = cells.groupby(
        ["marker", "encoder", "sampling_seed", "_target_mpp_key"],
        dropna=False,
        sort=True,
    )
    for (marker, encoder, seed, target_mpp), group in tile_groups:
        by_tiles = group.set_index("tiles_per_slide", drop=False)
        if not {16, 64}.issubset(set(by_tiles.index)) or not set(by_tiles.index).issubset(
            {16, 32, 64}
        ):
            raise StabilityGridIntegrityError(
                f"tile contrast group {(marker, encoder, seed, target_mpp)!r} must contain 16 and 64"
            )
        pair_id = (
            f"tile64_vs16__{marker}__{str(encoder).lower()}__s{seed}__mpp{target_mpp}"
        )
        rows.append(
            _contrast_row(
                "tile64_vs16", pair_id, by_tiles.loc[16], by_tiles.loc[64]
            )
        )

    contrast_order = {
        "native_vs_1.76": 0,
        "virchow_vs_conch_at_1.76": 1,
        "tile64_vs16": 2,
    }
    return pd.DataFrame(rows).assign(
        _contrast_order=lambda frame: frame["contrast"].map(contrast_order)
    ).sort_values(["_contrast_order", "pair_id"], kind="stable").drop(
        columns="_contrast_order"
    ).reset_index(drop=True)


def _validate_runner_ownership(spec: pd.DataFrame, raw_cells: pd.DataFrame) -> None:
    for _, cell in raw_cells.iterrows():
        runner = _runner_name(cell["raw_runner_dir"])
        config = RUNNER_SPECS.get(runner)
        if config is None:
            raise StabilityGridIntegrityError(f"unexpected runner directory: {runner}")
        cell_id = cell["cell_id"]
        spec_row = spec.loc[spec["cell_id"] == cell_id]
        if len(spec_row) != 1:
            continue
        spec_row = spec_row.iloc[0]
        if (
            cell["marker"] not in config["markers"]
            or cell["encoder"] != config["encoder"]
            or spec_row["canonical_cohort"] != config["canonical_cohort"]
        ):
            raise StabilityGridIntegrityError(
                f"runner metadata disagreement for cell {cell_id!r} in {runner}"
            )


def _validate_full_grid(spec: pd.DataFrame, raw_cells: pd.DataFrame, raw_folds: pd.DataFrame) -> None:
    if len(spec) != 360 or len(raw_cells) != 360 or len(raw_folds) != 1800:
        raise StabilityGridIntegrityError("full grid must contain exactly 360 cells and 1,800 folds")
    actual_runners = set(raw_cells["raw_runner_dir"].map(_runner_name))
    if actual_runners != set(RUNNER_SPECS):
        raise StabilityGridIntegrityError("full grid runner directories do not exactly match RUNNER_SPECS")
    for runner, config in RUNNER_SPECS.items():
        owned = raw_cells[raw_cells["raw_runner_dir"].map(_runner_name) == runner]
        if len(owned) != config["cell_count"]:
            raise StabilityGridIntegrityError(f"full grid {runner} has incorrect cell cardinality")
    if set(spec["sampling_seed"].map(lambda value: _integer(value, "sampling_seed"))) != set(range(5)):
        raise StabilityGridIntegrityError("full grid sampling-seed axis must be exactly 0 through 4")
    if set(spec["tiles_per_slide"].map(lambda value: _integer(value, "tiles_per_slide"))) != {16, 32, 64}:
        raise StabilityGridIntegrityError("full grid tiles-per-slide axis must be exactly 16, 32, 64")
    expected_mpp = {"CONCH": {"0.88", "1.76"}, "Virchow": {"0.44", "1.76"}}
    for encoder, mpps in expected_mpp.items():
        observed = set(spec.loc[spec["encoder"] == encoder, "target_mpp"].map(_mpp))
        if observed != mpps:
            raise StabilityGridIntegrityError(f"full grid {encoder} MPP axis is incorrect")


def reconcile_cells_and_folds(
    spec: pd.DataFrame,
    assignments: pd.DataFrame,
    raw_cells: pd.DataFrame,
    raw_folds: pd.DataFrame,
    *,
    require_full_grid: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Reconcile raw runner rows to frozen cells and their five fixed folds."""
    _require_columns(spec, SPEC_COLUMNS, "spec")
    _require_columns(assignments, ASSIGNMENT_COLUMNS, "assignments")
    _require_columns(
        raw_cells,
        (
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
            "n_patients", "patient_metric", "status", "raw_runner_dir",
            "raw_cell_results_path", "raw_cell_results_sha256",
        ),
        "raw cells",
    )
    _require_columns(
        raw_folds,
        (
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide", "target_mpp",
            "fold", "n_patients", "patient_metric", "raw_runner_dir",
            "raw_fold_results_path", "raw_fold_results_sha256",
        ),
        "raw folds",
    )
    spec = spec.copy()
    assignments = assignments.copy()
    raw_cells = raw_cells.copy()
    raw_folds = raw_folds.copy()
    if spec["cell_id"].duplicated().any():
        raise StabilityGridIntegrityError("spec contains duplicate cell IDs")
    if raw_cells["cell_id"].duplicated().any():
        raise StabilityGridIntegrityError("raw results contain duplicate cell IDs")
    if not raw_cells["status"].eq("complete").all():
        raise StabilityGridIntegrityError("all raw cells must have status complete")
    _validate_runner_ownership(spec, raw_cells)
    reconstructed = raw_cells.apply(_reconstructed_cell_id, axis=1)
    if not reconstructed.eq(raw_cells["cell_id"]).all():
        raise StabilityGridIntegrityError("raw cell ID disagrees with reconstructed raw metadata")
    if set(raw_cells["cell_id"]) != set(spec["cell_id"]):
        raise StabilityGridIntegrityError("raw result cell IDs do not exactly match the frozen spec")
    for column in ("marker", "encoder", "sampling_seed", "tiles_per_slide"):
        raw_values = raw_cells.set_index("cell_id")[column]
        spec_values = spec.set_index("cell_id").loc[raw_values.index, column]
        if column in {"sampling_seed", "tiles_per_slide"}:
            agrees = [
                _integer(left, column) == _integer(right, column)
                for left, right in zip(raw_values, spec_values, strict=True)
            ]
        else:
            agrees = raw_values.eq(spec_values).tolist()
        if not all(agrees):
            raise StabilityGridIntegrityError(f"spec/result metadata disagreement in {column}")
    raw_mpps = raw_cells.set_index("cell_id")["target_mpp"]
    spec_mpps = spec.set_index("cell_id").loc[raw_mpps.index, "target_mpp"]
    if not all(_mpp(left) == _mpp(right) for left, right in zip(raw_mpps, spec_mpps, strict=True)):
        raise StabilityGridIntegrityError("spec/result metadata disagreement in target_mpp")
    _require_finite(raw_cells, "patient_metric", "cell")
    if "slide_metric" in raw_cells.columns:
        standard = raw_cells[raw_cells["raw_runner_dir"].map(_runner_name).map(lambda name: not name.startswith("marker7_"))]
        if not standard.empty:
            _require_finite(standard, "slide_metric", "cell")

    raw_folds["fold"] = raw_folds["fold"].map(lambda value: _integer(value, "fold"))
    fold_keys = ["cell_id", "fold"]
    if raw_folds.duplicated(fold_keys).any():
        raise StabilityGridIntegrityError("raw results contain duplicate fold keys")
    if len(raw_folds) != 5 * len(spec):
        raise StabilityGridIntegrityError("raw folds must contain exactly five rows per spec cell")
    _require_finite(raw_folds, "patient_metric", "fold")
    if not raw_folds.apply(_reconstructed_cell_id, axis=1).eq(raw_folds["cell_id"]).all():
        raise StabilityGridIntegrityError("raw fold cell ID disagrees with reconstructed raw metadata")
    expected_fold_keys = {(cell_id, fold) for cell_id in spec["cell_id"] for fold in range(5)}
    observed_fold_keys = set(raw_folds.loc[:, fold_keys].itertuples(index=False, name=None))
    if observed_fold_keys != expected_fold_keys:
        raise StabilityGridIntegrityError("raw fold keys do not exactly cover five folds per cell")
    cell_runner = raw_cells.set_index("cell_id")["raw_runner_dir"]
    if not raw_folds.apply(
        lambda row: _runner_name(row["raw_runner_dir"]) == _runner_name(cell_runner.loc[row["cell_id"]]), axis=1
    ).all():
        raise StabilityGridIntegrityError("raw fold runner ownership disagrees with its cell")

    spec_by_cell = spec.set_index("cell_id")
    for column in ("marker", "encoder", "sampling_seed", "tiles_per_slide"):
        agrees = []
        for row in raw_folds.itertuples(index=False):
            left, right = getattr(row, column), spec_by_cell.loc[row.cell_id, column]
            agrees.append(
                _integer(left, column) == _integer(right, column)
                if column in {"sampling_seed", "tiles_per_slide"} else left == right
            )
        if not all(agrees):
            raise StabilityGridIntegrityError(f"fold metadata disagreement in {column}")
    if not all(
        _mpp(row.target_mpp) == _mpp(spec_by_cell.loc[row.cell_id, "target_mpp"])
        for row in raw_folds.itertuples(index=False)
    ):
        raise StabilityGridIntegrityError("fold metadata disagreement in target_mpp")

    assignment_counts = assignments.groupby(["marker", "canonical_cohort", "fold"], dropna=False).size()
    fold_rows = raw_folds.merge(
        spec[["cell_id", "canonical_cohort"]], on="cell_id", how="left", validate="many_to_one"
    )
    expected_counts = [
        assignment_counts.get((row.marker, row.canonical_cohort, _integer(row.fold, "fold")))
        for row in fold_rows.itertuples(index=False)
    ]
    if any(count is None for count in expected_counts):
        raise StabilityGridIntegrityError("fold assignment is missing a marker/cohort/fold count")
    observed_counts = pd.to_numeric(fold_rows["n_patients"], errors="coerce")
    if not observed_counts.eq(expected_counts).all():
        raise StabilityGridIntegrityError("fold assignment patient-count disagreement")

    cells_joined = spec.merge(raw_cells, on="cell_id", how="left", suffixes=("", "_raw"), validate="one_to_one")
    canonical_cells = pd.DataFrame({column: cells_joined[column] for column in SPEC_COLUMNS})
    for column in ("raw_runner_dir", "raw_cell_results_path", "raw_cell_results_sha256"):
        canonical_cells[column] = cells_joined[column]
    canonical_cells["raw_status"] = cells_joined["status_raw"]
    canonical_cells["reconciliation_status"] = "reconciled"
    for column in ("n_slides", "n_source_patients", "n_patients", "n_events", "slide_metric", "patient_metric"):
        canonical_cells[column] = cells_joined[column] if column in cells_joined else pd.NA
    canonical_cells = canonical_cells.loc[:, CELL_CANONICAL_COLUMNS]

    fold_output = fold_rows.merge(
        spec.drop(columns=["canonical_cohort"]), on="cell_id", how="left", suffixes=("_raw", ""), validate="many_to_one"
    )
    fold_output = fold_output.merge(
        raw_cells[["cell_id", "status"]].rename(columns={"status": "raw_status"}),
        on="cell_id",
        how="left",
        validate="many_to_one",
    )
    canonical_folds = pd.DataFrame({column: fold_output[column] for column in SPEC_COLUMNS})
    for column in ("raw_runner_dir", "raw_fold_results_path", "raw_fold_results_sha256"):
        canonical_folds[column] = fold_output[column]
    canonical_folds["raw_status"] = fold_output["raw_status"]
    canonical_folds["reconciliation_status"] = "reconciled"
    canonical_folds["fold"] = fold_output["fold"]
    canonical_folds["fold_n_patients"] = fold_output["n_patients"]
    canonical_folds["fold_patient_metric"] = fold_output["patient_metric"]
    canonical_folds["assignment_n_patients"] = expected_counts
    canonical_folds["fold_assignment_reconciled"] = True
    canonical_folds = canonical_folds.loc[:, FOLD_CANONICAL_COLUMNS]
    cell_order = {cell_id: index for index, cell_id in enumerate(spec["cell_id"])}
    canonical_folds = canonical_folds.assign(_order=canonical_folds["cell_id"].map(cell_order)).sort_values(
        ["_order", "fold"], kind="stable"
    ).drop(columns="_order").reset_index(drop=True)
    canonical_cells = canonical_cells.reset_index(drop=True)

    if require_full_grid:
        _validate_full_grid(spec, raw_cells, raw_folds)
    qc = {
        "spec_cells": int(len(spec)),
        "raw_cells": int(len(raw_cells)),
        "raw_folds": int(len(raw_folds)),
        "reconciled_cells": int(len(canonical_cells)),
        "reconciled_folds": int(len(canonical_folds)),
    }
    return canonical_cells, canonical_folds, qc


def _sorted_unique_paths(paths: Sequence[Path]) -> list[Path]:
    return sorted({Path(path) for path in paths}, key=lambda path: path.as_posix())


def _derive_nadt_tiff_paths(coordinate_manifest: pd.DataFrame) -> list[Path]:
    paths: set[Path] = set()
    nadt = coordinate_manifest[
        coordinate_manifest["raw_runner_dir"].isin(["nadt_conch", "nadt_virchow"])
    ]
    for value in nadt["raw_metadata_path"].dropna().unique():
        metadata_path = Path(str(value))
        metadata = _read_exact_csv_strict(
            metadata_path, NADT_METADATA_COLUMNS, "NADT TIFF-path metadata"
        )
        for raw_path in metadata["path"]:
            path = Path(_nonblank(raw_path, "NADT TIFF path"))
            try:
                relative = path.relative_to(REPO_ROOT / "opendataset")
            except ValueError:
                pass
            else:
                path = REPO_ROOT / "resources/data/shared/opendataset" / relative
            paths.add(path)
    return _sorted_unique_paths(paths)


def _json_native(value):
    if isinstance(value, dict):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_native(item) for item in value)
    if isinstance(value, Path):
        return value.as_posix()
    if value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        return _json_native(value.item())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_all_frames(
    spec_path: Path,
    assignments_path: Path,
    run_root: Path,
    log_root: Path,
    *,
    scan_tiffs: bool,
    require_full_grid: bool,
) -> dict:
    """Build all canonical frames and JSON-native QC without writing outputs."""
    spec_path = Path(spec_path)
    assignments_path = Path(assignments_path)
    run_root = Path(run_root)
    log_root = Path(log_root)
    spec = load_spec(spec_path)
    assignments = load_assignments(assignments_path)
    relevant_runner_names = {
        path.name
        for path in run_root.iterdir()
        if path.is_dir()
        and (path.name in RUNNER_SPECS or any(path.glob("*results.csv")))
    }
    if require_full_grid and relevant_runner_names != set(RUNNER_SPECS):
        raise StabilityGridIntegrityError(
            "full grid must contain exactly the six runner directories"
        )
    unexpected_runners = relevant_runner_names - set(RUNNER_SPECS)
    if unexpected_runners:
        raise StabilityGridIntegrityError(
            f"unexpected result runner directories: {sorted(unexpected_runners)}"
        )
    runner_dirs = sorted(
        [path for path in run_root.iterdir() if path.is_dir() and path.name in RUNNER_SPECS],
        key=lambda path: path.name,
    )
    if require_full_grid and {path.name for path in runner_dirs} != set(RUNNER_SPECS):
        raise StabilityGridIntegrityError("full grid must contain the exact six runner directories")
    if not runner_dirs:
        raise StabilityGridIntegrityError("no recognized runner directories found")
    raw_cells_parts = []
    raw_folds_parts = []
    runner_input_paths: list[Path] = []
    for runner_dir in runner_dirs:
        runner_cells, runner_folds, paths = load_runner_results(runner_dir)
        raw_cells_parts.append(runner_cells)
        raw_folds_parts.append(runner_folds)
        runner_input_paths.extend(paths)
    raw_cells = pd.concat(raw_cells_parts, ignore_index=True)
    raw_folds = pd.concat(raw_folds_parts, ignore_index=True)
    cells, folds, reconciliation_qc = reconcile_cells_and_folds(
        spec,
        assignments,
        raw_cells,
        raw_folds,
        require_full_grid=require_full_grid,
    )
    summary = build_stability_summary(cells)
    contrasts = build_stability_contrasts(cells)
    coordinate_manifest, coordinate_qc, coordinate_paths = build_coordinate_manifest(
        run_root, require_full_grid=require_full_grid
    )
    log_summary, log_qc, log_paths = summarize_logs(log_root)
    if require_full_grid and set(log_summary["log_name"]) != FULL_LOG_NAMES:
        raise StabilityGridIntegrityError("full grid log basenames must match the exact six-name set")

    tiff_input_paths: list[Path] = []
    if scan_tiffs:
        tiff_input_paths = _derive_nadt_tiff_paths(coordinate_manifest)
        if require_full_grid and len(tiff_input_paths) != 463:
            raise StabilityGridIntegrityError("full grid must contain exactly 463 unique NADT TIFFs")
        tiff_scan = scan_nadt_tiff_headers(tiff_input_paths)
        if require_full_grid and not tiff_scan["scan_complete"]:
            raise StabilityGridIntegrityError("full NADT TIFF header scan must complete")
        affected_paths = [Path(row["path"]) for row in tiff_scan["affected_slides"]]
        nadt_coordinate_paths = [
            Path(value)
            for value in coordinate_manifest.loc[
                coordinate_manifest["raw_runner_dir"].isin(["nadt_conch", "nadt_virchow"]),
                "raw_coordinate_path",
            ]
        ]
        warning_retention = _build_warning_slide_retention(
            affected_paths,
            nadt_coordinate_paths,
            require_full_grid=require_full_grid,
        )
        tiff_scan = {"status": "complete", **tiff_scan}
    else:
        tiff_scan = {
            "status": "not_scanned",
            "requested_paths": [],
            "requested_path_count": 0,
            "scanned_path_count": 0,
            "scan_failure_count": None,
            "scan_complete": False,
            "header_message_count": None,
            "affected_slide_count": None,
            "affected_slides": None,
            "scan_failures": None,
            "limitation": "NADT TIFF header and immutability gates were not executed.",
        }
        warning_retention = {
            "status": "not_scanned",
            "warning_slide_count": None,
            "nadt_coordinate_shards": None,
            "retention_details": None,
            "all_warning_slides_retained_in_all_shards": False,
        }

    chance_values = cells["primary_metric"].map(_null_value)
    chance_or_worse_cells = int(
        pd.to_numeric(cells["patient_metric"]).le(chance_values).sum()
    )
    native_crossings = int(
        contrasts.loc[contrasts["contrast"].eq("native_vs_1.76"), "null_crossing"].sum()
    )
    shared_crossings = int(
        contrasts.loc[
            contrasts["contrast"].eq("virchow_vs_conch_at_1.76"), "null_crossing"
        ].sum()
    )
    seed_straddles = int(summary["seed_null_straddle"].sum())
    qc = {
        "reconciliation": reconciliation_qc,
        "summary_qc": {
            "rows": int(len(summary)),
            "chance_or_worse_cells": chance_or_worse_cells,
            "seed_null_straddles": seed_straddles,
        },
        "contrast_qc": {
            "rows": int(len(contrasts)),
            "native_null_crossings": native_crossings,
            "shared_encoder_null_crossings": shared_crossings,
        },
        "coordinate_qc": coordinate_qc,
        "log_qc": log_qc,
        "tiff_header_scan": tiff_scan,
        "warning_slide_retention": warning_retention,
        "chance_or_worse_cells": chance_or_worse_cells,
        "native_null_crossings": native_crossings,
        "shared_encoder_null_crossings": shared_crossings,
        "seed_null_straddles": seed_straddles,
        "marker7_common_source_patients": coordinate_qc.get(
            "marker7_common_source_patients"
        ),
        "invalid_page_offset_log_lines": int(
            log_summary["invalid_page_offset_lines"].sum()
        ),
    }
    if require_full_grid:
        literal_counts = {
            "cells": len(cells) == 360,
            "folds": len(folds) == 1800,
            "summary": len(summary) == 72,
            "contrasts": len(contrasts) == 390,
            "coordinates": len(coordinate_manifest) == 60,
            "chance_or_worse": chance_or_worse_cells == 26,
            "native_crossings": native_crossings == 20,
            "shared_crossings": shared_crossings == 4,
            "seed_straddles": seed_straddles == 9,
            "source_common": coordinate_qc.get("marker7_common_source_patients") == 498,
            "invalid_offsets": qc["invalid_page_offset_log_lines"] == 26,
        }
        if not all(literal_counts.values()):
            raise StabilityGridIntegrityError(f"full Gate A assertions failed: {literal_counts}")
        if scan_tiffs and not (
            tiff_scan["requested_path_count"] == 463
            and tiff_scan["scanned_path_count"] == 463
            and tiff_scan["scan_failure_count"] == 0
            and tiff_scan["affected_slide_count"] == 2
            and warning_retention["all_warning_slides_retained_in_all_shards"]
        ):
            raise StabilityGridIntegrityError("full TIFF and warning-slide Gate A assertions failed")
        qc["assertions"] = {key: True for key in literal_counts}
    else:
        qc["assertions"] = {"reduced_mode": True}
    raw_input_paths = _sorted_unique_paths(
        [spec_path, assignments_path, *runner_input_paths, *coordinate_paths, *log_paths]
    )
    if require_full_grid and len(raw_input_paths) != 160:
        raise StabilityGridIntegrityError("full aggregation must consume exactly 160 frozen inputs")
    return {
        "cells": cells,
        "folds": folds,
        "summary": summary,
        "contrasts": contrasts,
        "coordinate_manifest": coordinate_manifest,
        "log_summary": log_summary,
        "qc": _json_native(qc),
        "raw_input_paths": raw_input_paths,
        "runner_input_paths": _sorted_unique_paths(runner_input_paths),
        "coordinate_input_paths": _sorted_unique_paths(coordinate_paths),
        "log_input_paths": _sorted_unique_paths(log_paths),
        "tiff_input_paths": tiff_input_paths,
    }


def _enumerate_declared_inputs(
    spec_path: Path,
    assignments_path: Path,
    run_root: Path,
    log_root: Path,
    *,
    require_full_grid: bool,
) -> list[Path]:
    """Enumerate the bounded inputs that the pure builder is allowed to consume."""
    spec_path = Path(spec_path)
    assignments_path = Path(assignments_path)
    run_root = Path(run_root)
    log_root = Path(log_root)
    paths = [spec_path, assignments_path]
    if not run_root.is_dir():
        raise StabilityGridIntegrityError(f"missing run root: {run_root}")
    relevant_runner_dirs = {
        path.name
        for path in run_root.iterdir()
        if path.is_dir()
        and (path.name in RUNNER_SPECS or any(path.glob("*results.csv")))
    }
    if require_full_grid and relevant_runner_dirs != set(RUNNER_SPECS):
        raise StabilityGridIntegrityError("full grid must contain exactly the six runner directories")
    for runner in sorted(relevant_runner_dirs):
        if runner not in RUNNER_SPECS:
            raise StabilityGridIntegrityError(f"unexpected result runner directory: {runner}")
        paths.extend(
            [run_root / runner / "cell_results.csv", run_root / runner / "fold_results.csv"]
        )
    _, coordinate_paths = _discover_coordinate_inputs(
        run_root, require_full_grid=require_full_grid
    )
    paths.extend(coordinate_paths)
    if not log_root.is_dir():
        raise StabilityGridIntegrityError(f"missing log root: {log_root}")
    log_paths = sorted(log_root.glob("*.log"), key=lambda path: path.as_posix())
    if require_full_grid and {path.name for path in log_paths} != FULL_LOG_NAMES:
        raise StabilityGridIntegrityError("full grid log basenames must match the exact six-name set")
    if not log_paths:
        raise StabilityGridIntegrityError(f"no log files found under: {log_root}")
    paths.extend(log_paths)
    result = _sorted_unique_paths(paths)
    missing = [path for path in result if not path.is_file()]
    if missing:
        raise StabilityGridIntegrityError(f"missing declared inputs: {[str(path) for path in missing]}")
    if require_full_grid and len(result) != 160:
        raise StabilityGridIntegrityError("full aggregation must declare exactly 160 frozen inputs")
    return result


def _provenance_paths() -> list[Path]:
    paths = [REPO_ROOT / relative for relative in PROVENANCE_RELATIVE_PATHS]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise StabilityGridIntegrityError(
            f"missing code/environment provenance inputs: {[str(path) for path in missing]}"
        )
    return paths


def _derive_nadt_tiff_paths_from_declared_inputs(paths: Sequence[Path]) -> list[Path]:
    metadata_paths = [
        Path(path)
        for path in paths
        if Path(path).parent.name in {"nadt_conch", "nadt_virchow"}
        and Path(path).name.startswith("meta_s")
    ]
    result: set[Path] = set()
    for metadata_path in metadata_paths:
        metadata = _read_exact_csv_strict(
            metadata_path, NADT_METADATA_COLUMNS, "NADT TIFF-path metadata"
        )
        for value in metadata["path"]:
            path = Path(_nonblank(value, "NADT TIFF path"))
            # Frozen runner metadata used the former root-level ``opendataset``
            # location. Preserve that immutable CSV and resolve only its exact
            # repository-local prefix to the canonical shared-data root.
            historical_root = REPO_ROOT / "opendataset"
            try:
                relative = path.relative_to(historical_root)
            except ValueError:
                pass
            else:
                path = REPO_ROOT / "resources/data/shared/opendataset" / relative
            result.add(path)
    return _sorted_unique_paths(result)


def _snapshot_paths(paths: Sequence[Path]) -> dict[Path, dict]:
    snapshots = {}
    for path in _sorted_unique_paths(paths):
        try:
            stat = path.stat()
            digest = _sha256(path)
        except OSError as error:
            raise StabilityGridIntegrityError(f"cannot hash required input: {path}") from error
        snapshots[path] = {
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": digest,
        }
    return snapshots


def _assert_snapshots_reconcile(before: dict[Path, dict], after: dict[Path, dict]) -> None:
    if set(before) != set(after):
        raise StabilityGridIntegrityError("input path set changed during aggregation")
    changed = [path for path in before if before[path] != after[path]]
    if changed:
        raise StabilityGridIntegrityError(
            f"input content or metadata changed during aggregation: {[str(path) for path in changed]}"
        )


def _display_path(path: Path) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _software_versions() -> dict:
    packages = ("pandas", "numpy", "scipy", "scikit-learn", "tifffile")
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "packages": versions,
    }


def _validate_publishable_frames(frames: dict, *, require_full_grid: bool) -> None:
    schemas = {
        "cells": CELL_CANONICAL_COLUMNS,
        "folds": FOLD_CANONICAL_COLUMNS,
        "summary": SUMMARY_COLUMNS,
        "contrasts": CONTRAST_COLUMNS,
        "coordinate_manifest": COORDINATE_MANIFEST_COLUMNS,
    }
    for name, columns in schemas.items():
        if list(frames[name].columns) != list(columns):
            raise StabilityGridIntegrityError(f"{name} output schema drift")
    key_specs = {
        "cells": ["cell_id"],
        "folds": ["cell_id", "fold"],
        "summary": ["marker", "encoder", "tiles_per_slide", "target_mpp"],
        "contrasts": ["pair_id"],
        "coordinate_manifest": ["raw_runner_dir", "sampling_seed", "target_mpp"],
    }
    for name, keys in key_specs.items():
        if frames[name].duplicated(keys).any():
            raise StabilityGridIntegrityError(f"{name} output contains duplicate keys")
    cells = frames["cells"]
    folds = frames["folds"]
    summary = frames["summary"]
    contrasts = frames["contrasts"]
    coordinates = frames["coordinate_manifest"]
    cell_order = {cell_id: index for index, cell_id in enumerate(cells["cell_id"])}
    observed_fold_order = list(folds[["cell_id", "fold"]].itertuples(index=False, name=None))
    expected_fold_order = sorted(
        observed_fold_order, key=lambda key: (cell_order.get(key[0], len(cell_order)), int(key[1]))
    )
    if observed_fold_order != expected_fold_order:
        raise StabilityGridIntegrityError("fold output does not preserve frozen-cell/fold order")
    for name, keys in {
        "summary": ["marker", "encoder", "tiles_per_slide", "target_mpp"],
        "coordinate_manifest": ["raw_runner_dir", "sampling_seed", "target_mpp"],
    }.items():
        observed = list(frames[name][keys].itertuples(index=False, name=None))
        if observed != sorted(observed):
            raise StabilityGridIntegrityError(f"{name} output key order is not stable")
    contrast_order = {
        "native_vs_1.76": 0,
        "virchow_vs_conch_at_1.76": 1,
        "tile64_vs16": 2,
    }
    observed_contrast_order = list(contrasts[["contrast", "pair_id"]].itertuples(index=False, name=None))
    if observed_contrast_order != sorted(
        observed_contrast_order, key=lambda key: (contrast_order.get(key[0], 99), key[1])
    ):
        raise StabilityGridIntegrityError("contrast output family/pair order is not stable")
    if not cells["status"].eq("pending").all():
        raise StabilityGridIntegrityError("published frozen cell status must remain pending")
    if not cells["raw_status"].eq("complete").all():
        raise StabilityGridIntegrityError("published raw cell status must be complete")
    if not cells["reconciliation_status"].eq("reconciled").all():
        raise StabilityGridIntegrityError("published cells must be reconciled")
    if not folds["raw_status"].eq("complete").all() or not folds[
        "reconciliation_status"
    ].eq("reconciled").all():
        raise StabilityGridIntegrityError("published folds must be complete and reconciled")
    if not folds["fold_assignment_reconciled"].eq(True).all():
        raise StabilityGridIntegrityError("published fold assignments must reconcile")
    if not set(folds["cell_id"]).issubset(set(cells["cell_id"])):
        raise StabilityGridIntegrityError("published folds reference unknown cell IDs")
    if not summary["metric"].eq(summary["primary_metric"]).all():
        raise StabilityGridIntegrityError("summary metric alias disagrees with primary_metric")
    if not pd.to_numeric(summary["chance_value"]).eq(
        pd.to_numeric(summary["null_value"])
    ).all():
        raise StabilityGridIntegrityError("summary chance/null aliases disagree")
    expected_rates = pd.to_numeric(summary["n_chance_or_worse"]) / pd.to_numeric(
        summary["n_seeds"]
    )
    if not all(
        math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-12)
        for left, right in zip(summary["chance_or_worse_rate"], expected_rates, strict=True)
    ):
        raise StabilityGridIntegrityError("summary chance-or-worse rates disagree")
    cell_index = cells.set_index("cell_id", drop=False)
    if not set(contrasts["cell_id_a"]) | set(contrasts["cell_id_b"]) <= set(cell_index.index):
        raise StabilityGridIntegrityError("contrast endpoint IDs are absent from canonical cells")
    allowed_contrasts = {"native_vs_1.76", "virchow_vs_conch_at_1.76", "tile64_vs16"}
    if not set(contrasts["contrast"]).issubset(allowed_contrasts):
        raise StabilityGridIntegrityError("unsupported contrast family in publication")
    for row in contrasts.itertuples(index=False):
        metric_a = float(row.patient_metric_a)
        metric_b = float(row.patient_metric_b)
        null_value = float(row.null_value)
        if row.metric_direction != "higher_is_better":
            raise StabilityGridIntegrityError("contrast metric direction must be higher_is_better")
        if not math.isclose(float(row.delta_b_minus_a), metric_b - metric_a, rel_tol=0, abs_tol=1e-12):
            raise StabilityGridIntegrityError("contrast delta does not match saved endpoints")
        if row.relation_a != _null_relation(metric_a, null_value) or row.relation_b != _null_relation(
            metric_b, null_value
        ):
            raise StabilityGridIntegrityError("contrast null relation disagrees with endpoint metric")
        crossing = {row.relation_a, row.relation_b} == {"below_null", "above_null"}
        if bool(row.null_crossing) != crossing or bool(row.exact_tie) != (metric_a == metric_b):
            raise StabilityGridIntegrityError("contrast crossing/tie flags disagree")
        saved_a, saved_b = cell_index.loc[row.cell_id_a], cell_index.loc[row.cell_id_b]
        endpoint_metadata_agrees = (
            saved_a.marker == saved_b.marker == row.marker
            and saved_a.outcome_type == saved_b.outcome_type == row.outcome_type
            and saved_a.primary_metric == saved_b.primary_metric == row.primary_metric
            and int(saved_a.sampling_seed) == int(saved_b.sampling_seed) == int(row.sampling_seed)
            and saved_a.encoder == row.encoder_a
            and saved_b.encoder == row.encoder_b
            and int(saved_a.tiles_per_slide) == int(row.tiles_per_slide_a)
            and int(saved_b.tiles_per_slide) == int(row.tiles_per_slide_b)
            and _mpp(saved_a.target_mpp) == _mpp(row.target_mpp_a)
            and _mpp(saved_b.target_mpp) == _mpp(row.target_mpp_b)
            and math.isclose(
                null_value, _null_value(row.primary_metric), rel_tol=0, abs_tol=1e-12
            )
        )
        if not endpoint_metadata_agrees:
            raise StabilityGridIntegrityError(
                "contrast endpoint metadata disagrees with canonical cells"
            )
        if not math.isclose(float(saved_a.patient_metric), metric_a, rel_tol=0, abs_tol=1e-12):
            raise StabilityGridIntegrityError("contrast endpoint A metric disagrees with cells")
        if not math.isclose(float(saved_b.patient_metric), metric_b, rel_tol=0, abs_tol=1e-12):
            raise StabilityGridIntegrityError("contrast endpoint B metric disagrees with cells")
    if not coordinates["n_rank_violations"].eq(0).all() or not coordinates[
        "coordinate_metadata_reconciled"
    ].eq(True).all():
        raise StabilityGridIntegrityError("coordinate manifest contains reconciliation failures")
    for row in coordinates.itertuples(index=False):
        for path_field, hash_field in (
            ("raw_coordinate_path", "raw_coordinate_sha256"),
            ("raw_metadata_path", "raw_metadata_sha256"),
            ("raw_source_metadata_path", "raw_source_metadata_sha256"),
            ("raw_target_metadata_path", "raw_target_metadata_sha256"),
        ):
            value = getattr(row, path_field)
            digest = getattr(row, hash_field)
            if pd.isna(value) or str(value).strip() == "":
                if not (pd.isna(digest) or str(digest).strip() == ""):
                    raise StabilityGridIntegrityError("coordinate path/hash structural missingness disagrees")
                continue
            candidate = Path(str(value))
            hash_path = candidate if candidate.is_absolute() else REPO_ROOT / candidate
            if _sha256(hash_path) != str(digest):
                raise StabilityGridIntegrityError("coordinate manifest path/hash disagreement")
    if require_full_grid:
        expected = {
            "cells": 360, "folds": 1800, "summary": 72,
            "contrasts": 390, "coordinate_manifest": 60,
        }
        observed = {name: len(frames[name]) for name in expected}
        if observed != expected:
            raise StabilityGridIntegrityError(
                f"full publication row counts disagree: {observed}"
            )
        if not summary["n_seeds"].eq(5).all():
            raise StabilityGridIntegrityError("full summary rows must contain five seeds")
        family_counts = contrasts["contrast"].value_counts().to_dict()
        if family_counts != {
            "native_vs_1.76": 180,
            "tile64_vs16": 120,
            "virchow_vs_conch_at_1.76": 90,
        }:
            raise StabilityGridIntegrityError("full contrast family counts disagree")


def _normalize_publication_frames(frames: dict) -> dict:
    normalized = dict(frames)
    path_columns = {
        "cells": ("raw_cell_results_path",),
        "folds": ("raw_fold_results_path",),
        "coordinate_manifest": tuple(
            column for column in COORDINATE_MANIFEST_COLUMNS if column.endswith("_path")
        ),
    }
    for name in ("cells", "folds", "summary", "contrasts", "coordinate_manifest"):
        normalized[name] = frames[name].copy()
    for name, columns in path_columns.items():
        for column in columns:
            normalized[name][column] = normalized[name][column].map(
                lambda value: value
                if pd.isna(value) or str(value).strip() == ""
                else _display_path(Path(str(value)))
            )
    return normalized


def _write_deterministic_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path, index=False, encoding="utf-8", lineterminator="\n",
        float_format="%.15g", na_rep="",
    )


def _write_json(value: dict, path: Path) -> None:
    path.write_bytes(_canonical_json_bytes(value))


def _canonical_json_bytes(value: dict) -> bytes:
    return (
        json.dumps(
            _json_native(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _assert_artifact_stats(
    paths: dict[str, Path], expected: dict[str, dict[str, int]], label: str
) -> None:
    observed = {
        name: {
            "size_bytes": int(path.stat().st_size),
            "mtime_ns": int(path.stat().st_mtime_ns),
        }
        for name, path in paths.items()
    }
    if observed != expected:
        raise StabilityGridIntegrityError(
            f"{label} size/mtime provenance disagrees with the validated manifest"
        )


def _fsync_file(path: Path) -> None:
    try:
        with Path(path).open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(Path(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _release_publication_lock(lock_path: Path, owner_token: str, owner_inode: int) -> bool:
    """Release only the lock file acquired by this publication owner."""
    lock_path = Path(lock_path)
    try:
        if lock_path.stat().st_ino != owner_inode:
            return False
        if lock_path.read_text(encoding="utf-8") != owner_token:
            return False
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return False


def _remove_lock_inode(lock_path: Path, expected_inode: int) -> bool:
    """Remove a partially initialized lock only if its created inode is still present."""
    lock_path = Path(lock_path)
    try:
        if lock_path.stat().st_ino != expected_inode:
            return False
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return False


def _output_targets(output_dir: Path, figure_data_dir: Path) -> dict[str, Path]:
    return {
        "stability_cell_results.csv": output_dir / "stability_cell_results.csv",
        "stability_fold_results.csv": output_dir / "stability_fold_results.csv",
        "stability_summary.csv": output_dir / "stability_summary.csv",
        "stability_contrast_summary.csv": output_dir / "stability_contrast_summary.csv",
        "stability_tile_coordinate_manifest.csv": output_dir / "stability_tile_coordinate_manifest.csv",
        "stability_qc_report.json": output_dir / "stability_qc_report.json",
        "stability_run_manifest.csv": output_dir / "stability_run_manifest.csv",
        "fig9_stability_grid.csv": figure_data_dir / "fig9_stability_grid.csv",
        "fig9_stability_contrasts.csv": figure_data_dir / "fig9_stability_contrasts.csv",
    }


def _validate_output_locations(
    targets: dict[str, Path], run_root: Path, log_root: Path
) -> None:
    model_root = targets["stability_cell_results.csv"].parent.resolve()
    figure_root = targets["fig9_stability_grid.csv"].parent.resolve()
    if (
        model_root == figure_root
        or model_root in figure_root.parents
        or figure_root in model_root.parents
    ):
        raise StabilityGridIntegrityError(
            "model and figure output roots must be distinct and non-overlapping"
        )
    resolved = [path.resolve() for path in targets.values()]
    if len(set(resolved)) != len(resolved):
        raise StabilityGridIntegrityError("publication output paths must be unique")
    for target in resolved:
        for raw_root in (Path(run_root).resolve(), Path(log_root).resolve()):
            if target == raw_root or raw_root in target.parents:
                raise StabilityGridIntegrityError("publication output overlaps an immutable input root")


def _manifest_frame(
    input_snapshots: dict[Path, dict],
    raw_paths: set[Path],
    provenance_paths: set[Path],
    tiff_paths: set[Path],
    targets: dict[str, Path],
    output_sha256: dict[str, str],
    output_stats: dict[str, dict[str, int]],
) -> pd.DataFrame:
    rows = []
    for path, snapshot in input_snapshots.items():
        if path in provenance_paths:
            kind, role = "provenance", "code_or_environment"
        elif path in tiff_paths:
            kind, role = "input", "nadt_tiff"
        else:
            kind, role = "input", "frozen_analysis_input"
        rows.append(
            {
                "artifact_kind": kind, "artifact_role": role,
                "runner": path.parent.name if path.parent.name in RUNNER_SPECS else "",
                "artifact_path": _display_path(path),
                "size_bytes": snapshot["size_bytes"], "mtime_ns": snapshot["mtime_ns"],
                "sha256_before": snapshot["sha256"], "sha256_after": snapshot["sha256"],
                "hash_reconciled": True, "software_version": "",
                "included_in_output_sha256": False, "hash_exclusion_reason": "not_an_output",
                "volatile_fields": "mtime_ns",
            }
        )
    for name, target in targets.items():
        included = name in output_sha256
        reason = "" if included else (
            "self_referential_manifest" if name == "stability_run_manifest.csv"
            else "contains_volatile_provenance_and_output_hashes"
        )
        is_manifest = name == "stability_run_manifest.csv"
        staged_stat_size = (
            pd.NA if is_manifest else output_stats[name]["size_bytes"]
        )
        staged_mtime_ns = pd.NA if is_manifest else output_stats[name]["mtime_ns"]
        rows.append(
            {
                "artifact_kind": "output", "artifact_role": name,
                "runner": "", "artifact_path": _display_path(target),
                "size_bytes": staged_stat_size, "mtime_ns": staged_mtime_ns,
                "sha256_before": "", "sha256_after": output_sha256.get(name, ""),
                "hash_reconciled": pd.NA, "software_version": "",
                "included_in_output_sha256": included, "hash_exclusion_reason": reason,
                "volatile_fields": (
                    "generated_at_utc;elapsed_seconds" if is_manifest
                    else (
                        "mtime_ns;generated_at_utc;elapsed_seconds"
                        if name == "stability_qc_report.json" else "mtime_ns"
                    )
                ),
            }
        )
    kind_order = {"input": 0, "provenance": 1, "output": 2}
    return pd.DataFrame(rows, columns=RUN_MANIFEST_COLUMNS).assign(
        _kind=lambda frame: frame["artifact_kind"].map(kind_order)
    ).sort_values(["_kind", "artifact_role", "artifact_path"], kind="stable").drop(
        columns="_kind"
    ).reset_index(drop=True)


def _serialized_string_frame(frame: pd.DataFrame) -> pd.DataFrame:
    buffer = io.StringIO()
    frame.to_csv(
        buffer, index=False, lineterminator="\n", float_format="%.15g", na_rep=""
    )
    return pd.read_csv(io.StringIO(buffer.getvalue()), dtype=str, keep_default_na=False)


def _validate_staged_manifest(
    staged: pd.DataFrame,
    expected: pd.DataFrame,
    targets: dict[str, Path],
    output_sha256: dict[str, str],
) -> None:
    expected_strings = _serialized_string_frame(expected)
    if not staged.equals(expected_strings):
        raise StabilityGridIntegrityError(
            "staged manifest semantics disagree with the validated in-memory manifest"
        )
    if staged.duplicated(["artifact_kind", "artifact_path"]).any():
        raise StabilityGridIntegrityError("staged manifest contains duplicate artifact keys")
    input_rows = staged.loc[staged["artifact_kind"].isin(["input", "provenance"])]
    if (
        input_rows.empty
        or not input_rows["sha256_before"].str.fullmatch(r"[0-9a-f]{64}").all()
        or not input_rows["sha256_before"].eq(input_rows["sha256_after"]).all()
        or not input_rows["hash_reconciled"].eq("True").all()
        or not input_rows["included_in_output_sha256"].eq("False").all()
    ):
        raise StabilityGridIntegrityError("staged manifest input hash reconciliation is invalid")
    output_rows = staged.loc[staged["artifact_kind"].eq("output")].set_index(
        "artifact_role", drop=False
    )
    if set(output_rows.index) != set(targets):
        raise StabilityGridIntegrityError("staged manifest output role set is invalid")
    if set(output_sha256) != {
        name for name in targets
        if name not in {"stability_run_manifest.csv", "stability_qc_report.json"}
    }:
        raise StabilityGridIntegrityError("staged manifest expected output hash scope is invalid")
    for name, digest in output_sha256.items():
        row = output_rows.loc[name]
        if (
            row["included_in_output_sha256"] != "True"
            or row["sha256_after"] != digest
            or row["hash_exclusion_reason"] != ""
        ):
            raise StabilityGridIntegrityError("staged manifest included output row is invalid")
    exclusions = {
        "stability_run_manifest.csv": "self_referential_manifest",
        "stability_qc_report.json": "contains_volatile_provenance_and_output_hashes",
    }
    for name, reason in exclusions.items():
        row = output_rows.loc[name]
        if (
            row["included_in_output_sha256"] != "False"
            or row["sha256_before"] != ""
            or row["sha256_after"] != ""
            or row["hash_exclusion_reason"] != reason
        ):
            raise StabilityGridIntegrityError("staged manifest excluded output row is invalid")


def _validate_staged_qc(
    staged: dict,
    expected: dict,
    output_sha256: dict[str, str],
) -> None:
    required_keys = {
        "schema_version", "generated_at_utc", "elapsed_seconds", "require_full_grid",
        "scan_tiffs", "input_counts", "output_counts", "reconciliation", "summary_qc",
        "contrast_qc", "coordinate_qc", "log_qc", "tiff_header_scan",
        "warning_slide_retention", "assertions", "software", "lineage_limitations",
        "output_sha256", "output_hash_exclusions", "volatile_fields",
    }
    if not required_keys.issubset(staged):
        raise StabilityGridIntegrityError("staged QC is missing required keys")
    if staged != _json_native(expected):
        raise StabilityGridIntegrityError(
            "staged QC semantics disagree with the validated in-memory report"
        )
    exclusions = {
        "stability_run_manifest.csv": "self_referential_manifest",
        "stability_qc_report.json": "contains_volatile_provenance_and_output_hashes",
    }
    if staged["output_hash_exclusions"] != exclusions:
        raise StabilityGridIntegrityError("staged QC hash exclusions are invalid")
    if staged["output_sha256"] != output_sha256 or set(output_sha256) & set(exclusions):
        raise StabilityGridIntegrityError("staged QC output hash scope is invalid")
    if staged["output_counts"].get("approved_files") != 9 or staged["output_counts"].get(
        "content_hashed_files"
    ) != 7:
        raise StabilityGridIntegrityError("staged QC output counts are invalid")
    assertions = staged.get("assertions", {})
    if not assertions or not all(bool(value) for value in assertions.values()):
        raise StabilityGridIntegrityError("staged QC assertions are not all true")


def _run_aggregation_locked(
    spec_path: Path,
    assignments_path: Path,
    run_root: Path,
    log_root: Path,
    output_dir: Path,
    figure_data_dir: Path,
    *,
    generated_at_utc=None,
    scan_tiffs: bool = True,
    require_full_grid: bool = True,
    elapsed_seconds_override=None,
) -> dict:
    """Fail-closed, deterministic, transactional publication of the nine artifacts."""
    started = time.monotonic()
    output_dir = Path(output_dir)
    figure_data_dir = Path(figure_data_dir)
    targets = _output_targets(output_dir, figure_data_dir)
    _validate_output_locations(targets, Path(run_root), Path(log_root))
    early_journal_path = output_dir / ".stability-transaction-journal.json"
    early_stale = [early_journal_path]
    for parent in {output_dir, figure_data_dir}:
        if parent.exists():
            early_stale.extend(parent.glob(".stability-stage-*"))
            early_stale.extend(parent.glob(".stability-backup-*"))
    if any(path.exists() for path in early_stale):
        raise StabilityGridIntegrityError("stale stability publication transaction state exists")
    raw_paths = _enumerate_declared_inputs(
        spec_path, assignments_path, run_root, log_root,
        require_full_grid=require_full_grid,
    )
    provenance_paths = _provenance_paths()
    initial_paths = _sorted_unique_paths([*raw_paths, *provenance_paths])
    initial_snapshots = _snapshot_paths(initial_paths)
    tiff_paths = (
        _derive_nadt_tiff_paths_from_declared_inputs(raw_paths) if scan_tiffs else []
    )
    if require_full_grid and scan_tiffs and len(tiff_paths) != 463:
        raise StabilityGridIntegrityError("full publication must hash exactly 463 NADT TIFF inputs")
    pre_snapshots = {
        **initial_snapshots,
        **_snapshot_paths(tiff_paths),
    }
    frames = build_all_frames(
        Path(spec_path), Path(assignments_path), Path(run_root), Path(log_root),
        scan_tiffs=scan_tiffs, require_full_grid=require_full_grid,
    )
    if set(map(Path, frames["raw_input_paths"])) != set(raw_paths):
        raise StabilityGridIntegrityError("builder consumed-path set disagrees with prehashed inputs")
    if set(map(Path, frames["tiff_input_paths"])) != set(tiff_paths):
        raise StabilityGridIntegrityError("builder TIFF-path set disagrees with prehashed inputs")
    assertions = frames.get("qc", {}).get("assertions", {})
    if not assertions or not all(bool(value) for value in assertions.values()):
        raise StabilityGridIntegrityError("one or more required QC assertions failed")
    frames = _normalize_publication_frames(frames)
    _validate_publishable_frames(frames, require_full_grid=require_full_grid)

    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    elapsed = (
        float(elapsed_seconds_override)
        if elapsed_seconds_override is not None else float(time.monotonic() - started)
    )
    software = _software_versions()
    qc_report = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "elapsed_seconds": elapsed,
        "require_full_grid": bool(require_full_grid),
        "scan_tiffs": bool(scan_tiffs),
        "input_counts": {
            "raw": len(raw_paths), "provenance": len(provenance_paths),
            "tiffs": len(tiff_paths), "total": len(pre_snapshots),
        },
        "output_counts": {
            "approved_files": 9, "content_hashed_files": 7,
            "cells": len(frames["cells"]), "folds": len(frames["folds"]),
            "summary": len(frames["summary"]), "contrasts": len(frames["contrasts"]),
            "coordinate_manifest": len(frames["coordinate_manifest"]),
        },
        **frames["qc"],
        "software": software,
        "output_hash_exclusions": {
            "stability_run_manifest.csv": "self_referential_manifest",
            "stability_qc_report.json": "contains_volatile_provenance_and_output_hashes",
        },
        "volatile_fields": ["generated_at_utc", "elapsed_seconds", "mtime_ns"],
        "lineage_limitations": [
            "Historical per-run command/config manifests were not available.",
            "TIFF header findings do not establish pixel-level impact.",
        ],
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    figure_data_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_data_dir.mkdir(parents=True, exist_ok=True)
    journal_path = output_dir / ".stability-transaction-journal.json"
    stale = [journal_path]
    for parent in {output_dir, figure_data_dir}:
        stale.extend(parent.glob(".stability-stage-*"))
        stale.extend(parent.glob(".stability-backup-*"))
    if any(path.exists() for path in stale):
        raise StabilityGridIntegrityError("stale stability publication transaction state exists")
    stage_output = Path(tempfile.mkdtemp(prefix=".stability-stage-", dir=output_dir))
    stage_figure = Path(tempfile.mkdtemp(prefix=".stability-stage-", dir=figure_data_dir))
    backup_output = Path(tempfile.mkdtemp(prefix=".stability-backup-", dir=output_dir))
    backup_figure = Path(tempfile.mkdtemp(prefix=".stability-backup-", dir=figure_data_dir))
    stage_targets = {
        name: (stage_output if target.parent == output_dir else stage_figure) / name
        for name, target in targets.items()
    }
    backup_targets = {
        name: (backup_output if target.parent == output_dir else backup_figure) / name
        for name, target in targets.items()
    }
    installed: list[str] = []
    backed_up: list[str] = []
    committed = False
    rollback_complete = False
    previous_output_sha256 = {
        name: _sha256(target) for name, target in targets.items() if target.exists()
    }
    try:
        _write_deterministic_csv(frames["cells"], stage_targets["stability_cell_results.csv"])
        _write_deterministic_csv(frames["folds"], stage_targets["stability_fold_results.csv"])
        _write_deterministic_csv(frames["summary"], stage_targets["stability_summary.csv"])
        _write_deterministic_csv(frames["contrasts"], stage_targets["stability_contrast_summary.csv"])
        _write_deterministic_csv(
            frames["coordinate_manifest"], stage_targets["stability_tile_coordinate_manifest.csv"]
        )
        shutil.copyfile(
            stage_targets["stability_summary.csv"], stage_targets["fig9_stability_grid.csv"]
        )
        shutil.copyfile(
            stage_targets["stability_contrast_summary.csv"],
            stage_targets["fig9_stability_contrasts.csv"],
        )
        output_sha256 = {
            name: _sha256(stage_targets[name])
            for name in targets
            if name not in {"stability_run_manifest.csv", "stability_qc_report.json"}
        }
        qc_report["output_sha256"] = output_sha256
        expected_qc_bytes = _canonical_json_bytes(qc_report)
        _write_json(qc_report, stage_targets["stability_qc_report.json"])
        output_stats = {
            name: {
                "size_bytes": int(path.stat().st_size),
                "mtime_ns": int(path.stat().st_mtime_ns),
            }
            for name, path in stage_targets.items()
            if name != "stability_run_manifest.csv"
        }
        manifest = _manifest_frame(
            pre_snapshots, set(raw_paths), set(provenance_paths), set(tiff_paths),
            targets, output_sha256, output_stats,
        )
        if require_full_grid:
            expected_manifest_rows = 640 if scan_tiffs else 177
            if len(manifest) != expected_manifest_rows:
                raise StabilityGridIntegrityError("full run-manifest row count disagrees")
        _write_deterministic_csv(manifest, stage_targets["stability_run_manifest.csv"])
        expected_manifest_bytes = stage_targets["stability_run_manifest.csv"].read_bytes()
        for name, expected_columns in {
            "stability_cell_results.csv": CELL_CANONICAL_COLUMNS,
            "stability_fold_results.csv": FOLD_CANONICAL_COLUMNS,
            "stability_summary.csv": SUMMARY_COLUMNS,
            "stability_contrast_summary.csv": CONTRAST_COLUMNS,
            "stability_tile_coordinate_manifest.csv": COORDINATE_MANIFEST_COLUMNS,
            "stability_run_manifest.csv": RUN_MANIFEST_COLUMNS,
        }.items():
            with stage_targets[name].open("r", encoding="utf-8", newline="") as handle:
                if next(csv.reader(handle), None) != list(expected_columns):
                    raise StabilityGridIntegrityError(f"staged schema read-back failed for {name}")
        staged_frames = {
            "cells": pd.read_csv(stage_targets["stability_cell_results.csv"]),
            "folds": pd.read_csv(stage_targets["stability_fold_results.csv"]),
            "summary": pd.read_csv(stage_targets["stability_summary.csv"]),
            "contrasts": pd.read_csv(stage_targets["stability_contrast_summary.csv"]),
            "coordinate_manifest": pd.read_csv(
                stage_targets["stability_tile_coordinate_manifest.csv"]
            ),
        }
        _validate_publishable_frames(
            staged_frames, require_full_grid=require_full_grid
        )
        staged_manifest = pd.read_csv(
            stage_targets["stability_run_manifest.csv"], dtype=str, keep_default_na=False
        )
        _validate_staged_manifest(staged_manifest, manifest, targets, output_sha256)
        if stage_targets["stability_summary.csv"].read_bytes() != stage_targets[
            "fig9_stability_grid.csv"
        ].read_bytes() or stage_targets["stability_contrast_summary.csv"].read_bytes() != stage_targets[
            "fig9_stability_contrasts.csv"
        ].read_bytes():
            raise StabilityGridIntegrityError("staged figure data is not byte-identical")
        with stage_targets["stability_qc_report.json"].open("r", encoding="utf-8") as handle:
            staged_qc = json.load(handle)
        if stage_targets["stability_qc_report.json"].read_bytes() != expected_qc_bytes:
            raise StabilityGridIntegrityError(
                "staged QC bytes disagree with canonical deterministic JSON"
            )
        _validate_staged_qc(staged_qc, qc_report, output_sha256)
        if any(_sha256(stage_targets[name]) != digest for name, digest in output_sha256.items()):
            raise StabilityGridIntegrityError("staged output hash validation failed")
        manifest_inputs = staged_manifest.loc[
            staged_manifest["artifact_kind"].isin(["input", "provenance"])
        ].set_index("artifact_path")
        for row in staged_frames["coordinate_manifest"].itertuples(index=False):
            for path_field, hash_field in (
                ("raw_coordinate_path", "raw_coordinate_sha256"),
                ("raw_metadata_path", "raw_metadata_sha256"),
                ("raw_source_metadata_path", "raw_source_metadata_sha256"),
                ("raw_target_metadata_path", "raw_target_metadata_sha256"),
            ):
                value = getattr(row, path_field)
                if pd.isna(value) or str(value).strip() == "":
                    continue
                manifest_path = _display_path(Path(str(value)))
                if manifest_path not in manifest_inputs.index or str(
                    manifest_inputs.loc[manifest_path, "sha256_before"]
                ) != str(getattr(row, hash_field)):
                    raise StabilityGridIntegrityError(
                        "coordinate manifest provenance is absent from the run manifest"
                    )
        for path in stage_targets.values():
            _fsync_file(path)
        _fsync_directory(stage_output)
        _fsync_directory(stage_figure)
        journal_path.write_text(
            json.dumps({"state": "prepared", "targets": sorted(targets)}) + "\n",
            encoding="utf-8",
        )
        _fsync_file(journal_path)
        _fsync_directory(output_dir)
        _assert_artifact_stats(
            {name: stage_targets[name] for name in output_stats},
            output_stats,
            "staged output",
        )
        for name, target in targets.items():
            if target.exists():
                os.replace(target, backup_targets[name])
                backed_up.append(name)
        payload_order = [
            name for name in targets if name != "stability_run_manifest.csv"
        ]
        for name in payload_order:
            os.replace(stage_targets[name], targets[name])
            installed.append(name)
        installed_hashes = {
            name: _sha256(targets[name]) for name in output_sha256
        }
        if installed_hashes != output_sha256:
            raise StabilityGridIntegrityError(
                "installed output hashes disagree with the validated staged payloads"
            )
        for name in payload_order:
            _fsync_file(targets[name])
        _fsync_directory(output_dir)
        _fsync_directory(figure_data_dir)
        if targets["stability_qc_report.json"].read_bytes() != expected_qc_bytes:
            raise StabilityGridIntegrityError(
                "installed QC bytes disagree with canonical deterministic JSON"
            )
        _assert_artifact_stats(
            {name: targets[name] for name in output_stats},
            output_stats,
            "installed output",
        )
        post_snapshots = _snapshot_paths(list(pre_snapshots))
        _assert_snapshots_reconcile(pre_snapshots, post_snapshots)
        installed_hashes = {
            name: _sha256(targets[name]) for name in output_sha256
        }
        if installed_hashes != output_sha256:
            raise StabilityGridIntegrityError(
                "installed output hashes disagree with the validated staged payloads"
            )
        if targets["stability_qc_report.json"].read_bytes() != expected_qc_bytes:
            raise StabilityGridIntegrityError(
                "installed QC bytes disagree with canonical deterministic JSON"
            )
        _assert_artifact_stats(
            {name: targets[name] for name in output_stats},
            output_stats,
            "installed output",
        )
        final_manifest_bytes = stage_targets["stability_run_manifest.csv"].read_bytes()
        if final_manifest_bytes != expected_manifest_bytes:
            raise StabilityGridIntegrityError(
                "staged manifest bytes disagree with the validated canonical manifest"
            )
        final_staged_manifest = pd.read_csv(
            io.BytesIO(final_manifest_bytes), dtype=str, keep_default_na=False
        )
        _validate_staged_manifest(
            final_staged_manifest, manifest, targets, output_sha256
        )
        os.replace(
            stage_targets["stability_run_manifest.csv"], targets["stability_run_manifest.csv"]
        )
        installed.append("stability_run_manifest.csv")
        _fsync_file(targets["stability_run_manifest.csv"])
        _fsync_directory(output_dir)
        committed = True
        return {
            "output_sha256": output_sha256,
            "output_paths": {name: path for name, path in targets.items()},
            "qc": qc_report,
            "manifest": manifest,
        }
    except Exception as publication_error:
        rollback_errors = []
        for name in reversed(installed):
            try:
                targets[name].unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                rollback_errors.append(f"remove {name}: {type(error).__name__}: {error}")
        for name in reversed(backed_up):
            if backup_targets[name].exists():
                try:
                    os.replace(backup_targets[name], targets[name])
                except OSError as error:
                    rollback_errors.append(
                        f"restore {name}: {type(error).__name__}: {error}"
                    )
        for name, expected_digest in previous_output_sha256.items():
            final_matches = targets[name].is_file() and _sha256(targets[name]) == expected_digest
            backup_matches = (
                backup_targets[name].is_file()
                and _sha256(backup_targets[name]) == expected_digest
            )
            if not (final_matches or backup_matches):
                rollback_errors.append(f"previous bytes unavailable for {name}")
        for name in set(targets) - set(previous_output_sha256):
            if targets[name].exists():
                rollback_errors.append(f"new output remains at final path for {name}")
        if rollback_errors:
            recovery = {
                "state": "recovery_required",
                "publication_error": f"{type(publication_error).__name__}: {publication_error}",
                "rollback_errors": rollback_errors,
                "backup_directories": [backup_output.as_posix(), backup_figure.as_posix()],
                "targets": {name: path.as_posix() for name, path in targets.items()},
            }
            _write_json(recovery, journal_path)
            _fsync_file(journal_path)
            _fsync_directory(output_dir)
            raise StabilityGridIntegrityError(
                "publication rollback incomplete; recovery required"
            ) from publication_error
        rollback_complete = True
        raise
    finally:
        if committed or rollback_complete:
            with contextlib.suppress(FileNotFoundError):
                journal_path.unlink()
            for directory in (stage_output, stage_figure, backup_output, backup_figure):
                shutil.rmtree(directory, ignore_errors=True)
        _fsync_directory(output_dir)
        _fsync_directory(figure_data_dir)


def run_aggregation(
    spec_path: Path,
    assignments_path: Path,
    run_root: Path,
    log_root: Path,
    output_dir: Path,
    figure_data_dir: Path,
    *,
    generated_at_utc=None,
    scan_tiffs: bool = True,
    require_full_grid: bool = True,
    elapsed_seconds_override=None,
) -> dict:
    """Acquire the publication lock before any frozen input is enumerated or read."""
    output_dir = Path(output_dir)
    figure_data_dir = Path(figure_data_dir)
    targets = _output_targets(output_dir, figure_data_dir)
    _validate_output_locations(targets, Path(run_root), Path(log_root))
    journal_path = output_dir / ".stability-transaction-journal.json"
    stale = [journal_path]
    for parent in {output_dir, figure_data_dir}:
        if parent.exists():
            stale.extend(parent.glob(".stability-stage-*"))
            stale.extend(parent.glob(".stability-backup-*"))
    if any(path.exists() for path in stale):
        raise StabilityGridIntegrityError("stale stability publication transaction state exists")
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".stability-aggregation.lock"
    owner_token = os.urandom(16).hex() + "\n"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise StabilityGridIntegrityError("another stability publication holds the lock") from error
    created_inode = None
    try:
        created_inode = os.fstat(lock_fd).st_ino
        owner_inode = created_inode
        owner_token_bytes = owner_token.encode("ascii")
        written = os.write(lock_fd, owner_token_bytes)
        if written != len(owner_token_bytes):
            raise StabilityGridIntegrityError("lock token write was incomplete")
    except Exception:
        os.close(lock_fd)
        if created_inode is not None:
            _remove_lock_inode(lock_path, created_inode)
        _fsync_directory(output_dir)
        raise
    else:
        os.close(lock_fd)
    try:
        visible_lock_owned = (
            lock_path.stat().st_ino == owner_inode
            and lock_path.read_text(encoding="utf-8") == owner_token
        )
    except (OSError, UnicodeError):
        visible_lock_owned = False
    if not visible_lock_owned:
        raise StabilityGridIntegrityError(
            "visible publication lock ownership changed during initialization"
        )
    _fsync_file(lock_path)
    try:
        return _run_aggregation_locked(
            spec_path, assignments_path, run_root, log_root, output_dir, figure_data_dir,
            generated_at_utc=generated_at_utc, scan_tiffs=scan_tiffs,
            require_full_grid=require_full_grid,
            elapsed_seconds_override=elapsed_seconds_override,
        )
    finally:
        _release_publication_lock(lock_path, owner_token, owner_inode)
        _fsync_directory(output_dir)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate the frozen stability grid")
    parser.add_argument("--spec", type=Path, default=Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv"))
    parser.add_argument(
        "--fold-assignments", type=Path,
        default=Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv"),
    )
    parser.add_argument("--run-root", type=Path, default=Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full"))
    parser.add_argument("--log-root", type=Path, default=Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs"))
    parser.add_argument("--output-dir", type=Path, default=Path("resources/projects/prostate_biomarker_validation/model_workspace"))
    parser.add_argument(
        "--figure-data-dir", type=Path,
        default=Path("projects/prostate_biomarker_validation/paper/figure_data"),
    )
    parser.add_argument("--no-scan-tiffs", action="store_true")
    parser.add_argument("--no-require-full-grid", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_aggregation(
        args.spec, args.fold_assignments, args.run_root, args.log_root,
        args.output_dir, args.figure_data_dir,
        scan_tiffs=not args.no_scan_tiffs,
        require_full_grid=not args.no_require_full_grid,
    )
    print(json.dumps({"status": "complete", "output_sha256": result["output_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
