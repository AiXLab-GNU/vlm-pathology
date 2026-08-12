"""Contract tests for frozen stability-grid reconciliation."""

from __future__ import annotations

import tempfile
import unittest
import hashlib
import json
import logging
import os
import contextlib
import io
from pathlib import Path
from unittest.mock import patch as _stdlib_patch

import numpy as np
import pandas as pd
import tifffile
from projects.prostate_biomarker_validation.code.legacy import aggregate_stability_grid as aggregation

from projects.prostate_biomarker_validation.code.legacy.aggregate_stability_grid import (
    StabilityGridIntegrityError,
    build_coordinate_manifest,
    build_all_frames,
    build_stability_contrasts,
    build_stability_summary,
    load_assignments,
    load_runner_results,
    load_spec,
    parse_args,
    reconcile_cells_and_folds,
    run_aggregation,
    scan_nadt_tiff_headers,
    summarize_logs,
)

ROOT = Path(__file__).resolve().parents[3]
FULL_SPEC = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv"
FULL_RUN_ROOT = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full"


def patch(target, *args, **kwargs):
    """Resolve frozen test mock targets through the canonical project namespace."""
    target = target.replace(
        "models.aggregate_stability_grid",
        "projects.prostate_biomarker_validation.code.legacy.aggregate_stability_grid",
    )
    return _stdlib_patch(target, *args, **kwargs)


class PublicationTests(unittest.TestCase):
    """Protect read-only orchestration and fail-closed nine-file publication."""

    def publication_frames(self, root):
        root = Path(root)
        raw = root / "raw.csv"
        raw.write_text("frozen\n", encoding="utf-8")
        cell_row = {
                    **{column: pd.NA for column in aggregation.CELL_CANONICAL_COLUMNS},
                    "cell_id": "spop-cell", "marker": "spop",
                    "canonical_cohort": "TCGA-PRAD", "outcome_type": "binary",
                    "primary_metric": "patient_auroc", "encoder": "CONCH",
                    "sampling_seed": 0, "tiles_per_slide": 16, "target_mpp": 0.88,
                    "fold_file": "fold.csv", "status": "pending",
                    "raw_runner_dir": "conch", "raw_cell_results_path": str(raw),
                    "raw_cell_results_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                    "raw_status": "complete", "reconciliation_status": "reconciled",
                    "n_slides": 2, "n_patients": 2, "patient_metric": 0.75,
                }
        cells = pd.DataFrame(
            [cell_row, {**cell_row, "cell_id": "spop-cell-b", "target_mpp": 1.76}],
            columns=aggregation.CELL_CANONICAL_COLUMNS,
        )
        folds = pd.DataFrame(
            [
                *[
                    {
                    **{column: pd.NA for column in aggregation.FOLD_CANONICAL_COLUMNS},
                    **cells.iloc[index][list(aggregation.SPEC_COLUMNS)].to_dict(),
                    "raw_runner_dir": "conch", "raw_fold_results_path": str(raw),
                    "raw_fold_results_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                    "raw_status": "complete", "reconciliation_status": "reconciled",
                    "fold": 0, "fold_n_patients": 2, "fold_patient_metric": 0.75,
                    "assignment_n_patients": 2, "fold_assignment_reconciled": True,
                    }
                    for index in range(2)
                ]
            ],
            columns=aggregation.FOLD_CANONICAL_COLUMNS,
        )
        summary = pd.DataFrame(
            [["spop", "patient_auroc", 0.5, "CONCH", 16, 0.88, 1, 0.75,
              pd.NA, pd.NA, pd.NA, 0.75, 0.75, 0, 0.0, False, 0,
              "binary", "patient_auroc", 0.5]],
            columns=aggregation.SUMMARY_COLUMNS,
        )
        contrasts = pd.DataFrame(
            [["native_vs_1.76", "pair", "spop-cell", "spop-cell-b", "spop",
              "binary", "patient_auroc", 0, "CONCH", "CONCH", 16, 16,
              0.88, 1.76, 0.75, 0.75, 0.0, 0.5, "higher_is_better",
              "above_null", "above_null", False, True]],
            columns=aggregation.CONTRAST_COLUMNS,
        )
        coordinates = pd.DataFrame(
            [{**{column: pd.NA for column in aggregation.COORDINATE_MANIFEST_COLUMNS},
              "raw_runner_dir": "conch", "encoder": "CONCH", "sampling_seed": 0,
              "target_mpp": 0.88, "raw_coordinate_path": str(raw),
              "raw_coordinate_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
              "n_coordinate_rows": 64, "n_slides": 1, "n_patients": 1,
              "pyramid_levels": "0", "tile_rank_min": 0, "tile_rank_max": 63,
              "n_rank_violations": 0, "coordinate_metadata_reconciled": True}],
            columns=aggregation.COORDINATE_MANIFEST_COLUMNS,
        )
        return {
            "cells": cells, "folds": folds, "summary": summary,
            "contrasts": contrasts, "coordinate_manifest": coordinates,
            "log_summary": pd.DataFrame(columns=aggregation.LOG_SUMMARY_COLUMNS),
            "qc": {
                "reconciliation": {}, "summary_qc": {}, "contrast_qc": {},
                "coordinate_qc": {}, "log_qc": {},
                "tiff_header_scan": {"status": "not_scanned"},
                "warning_slide_retention": {"status": "not_scanned"},
                "assertions": {"reduced_mode": True},
            },
            "raw_input_paths": [raw], "runner_input_paths": [raw],
            "coordinate_input_paths": [], "log_input_paths": [],
            "tiff_input_paths": [],
        }

    def test_publication_writes_exact_deterministic_output_contract(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            figure_dir = root / "figures"
            frames = self.publication_frames(root)
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
            ):
                first = run_aggregation(
                    root / "spec.csv", root / "assign.csv", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0.0,
                )
                first_bytes = {path.name: path.read_bytes() for path in [*output_dir.iterdir(), *figure_dir.iterdir()]}
                second = run_aggregation(
                    root / "spec.csv", root / "assign.csv", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0.0,
                )
            expected = {
                "stability_cell_results.csv", "stability_fold_results.csv",
                "stability_summary.csv", "stability_contrast_summary.csv",
                "stability_tile_coordinate_manifest.csv", "stability_run_manifest.csv",
                "stability_qc_report.json", "fig9_stability_grid.csv",
                "fig9_stability_contrasts.csv",
            }
            actual = {path.name for path in [*output_dir.iterdir(), *figure_dir.iterdir()]}
            self.assertEqual(actual, expected)
            self.assertEqual(set(first["output_sha256"]), expected - {
                "stability_run_manifest.csv", "stability_qc_report.json"})
            self.assertEqual(first["output_sha256"], second["output_sha256"])
            qc = json.loads((output_dir / "stability_qc_report.json").read_text(encoding="utf-8"))
            self.assertEqual(qc["output_sha256"], first["output_sha256"])
            manifest = pd.read_csv(output_dir / "stability_run_manifest.csv")
            self.assertEqual(qc["input_counts"]["tiffs"], 0)
            self.assertEqual(qc["tiff_header_scan"]["status"], "not_scanned")
            self.assertEqual(
                len(manifest.loc[manifest["artifact_role"].eq("nadt_tiff")]), 0
            )
            included = manifest.loc[manifest["included_in_output_sha256"], "artifact_role"]
            self.assertEqual(set(included), set(first["output_sha256"]))
            excluded = manifest.loc[
                manifest["artifact_role"].isin(
                    ["stability_run_manifest.csv", "stability_qc_report.json"]
                )
            ]
            self.assertFalse(excluded["included_in_output_sha256"].any())
            for name, digest in first["output_sha256"].items():
                path = output_dir / name if name.startswith("stability_") else figure_dir / name
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            self.assertEqual(
                (output_dir / "stability_summary.csv").read_bytes(),
                (figure_dir / "fig9_stability_grid.csv").read_bytes(),
            )
            self.assertEqual(
                (output_dir / "stability_contrast_summary.csv").read_bytes(),
                (figure_dir / "fig9_stability_contrasts.csv").read_bytes(),
            )
            second_bytes = {
                path.name: path.read_bytes()
                for path in [*output_dir.iterdir(), *figure_dir.iterdir()]
            }
            for name in expected - {"stability_run_manifest.csv"}:
                self.assertEqual(first_bytes[name], second_bytes[name], name)
            first_manifest = pd.read_csv(
                io.BytesIO(first_bytes["stability_run_manifest.csv"]),
                dtype=str,
                keep_default_na=False,
            )
            second_manifest = pd.read_csv(
                io.BytesIO(second_bytes["stability_run_manifest.csv"]),
                dtype=str,
                keep_default_na=False,
            )
            first_manifest["mtime_ns"] = ""
            second_manifest["mtime_ns"] = ""
            pd.testing.assert_frame_equal(first_manifest, second_manifest)

    def test_manifest_records_eight_nonself_output_sizes_and_mtimes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
            ):
                run_aggregation(
                    root / "spec", root / "assign", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                )
            manifest = pd.read_csv(
                output_dir / "stability_run_manifest.csv", dtype=str, keep_default_na=False
            )
            output_rows = manifest.loc[manifest["artifact_kind"].eq("output")].set_index(
                "artifact_role"
            )
            targets = aggregation._output_targets(output_dir, figure_dir)
            for name, target in targets.items():
                row = output_rows.loc[name]
                if name == "stability_run_manifest.csv":
                    self.assertEqual(row["size_bytes"], "")
                    self.assertEqual(row["mtime_ns"], "")
                else:
                    stat = target.stat()
                    self.assertRegex(row["size_bytes"], r"^[0-9]+$")
                    self.assertRegex(row["mtime_ns"], r"^[0-9]+$")
                    self.assertEqual(int(row["size_bytes"]), stat.st_size)
                    self.assertEqual(int(row["mtime_ns"]), stat.st_mtime_ns)
                    self.assertIn("mtime_ns", row["volatile_fields"].split(";"))

    def test_staged_manifest_semantic_corruption_fails_before_final_mutation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            real_write_csv = aggregation._write_deterministic_csv

            def corrupt_manifest(frame, path):
                real_write_csv(frame, path)
                if Path(path).name == "stability_run_manifest.csv":
                    saved = pd.read_csv(path, dtype=str, keep_default_na=False)
                    saved.loc[
                        saved["artifact_role"].eq("stability_summary.csv"),
                        "sha256_after",
                    ] = "corrupt-manifest-hash"
                    real_write_csv(saved, path)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._write_deterministic_csv",
                      side_effect=corrupt_manifest),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "staged manifest"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertFalse(any(path.exists() for path in
                                 aggregation._output_targets(output_dir, figure_dir).values()))

    def test_staged_qc_semantic_corruption_fails_before_final_mutation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            real_write_json = aggregation._write_json

            def corrupt_qc(value, path):
                real_write_json(value, path)
                if Path(path).name == "stability_qc_report.json":
                    saved = json.loads(Path(path).read_text(encoding="utf-8"))
                    saved["output_hash_exclusions"] = {}
                    real_write_json(saved, path)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._write_json", side_effect=corrupt_qc),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "staged QC"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertFalse(any(path.exists() for path in
                                 aggregation._output_targets(output_dir, figure_dir).values()))

    def test_staged_qc_trailing_lf_fails_before_final_mutation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                if index % 2 == 0:
                    target.write_bytes(f"previous-{index}\n".encode())
            before = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            real_write_csv = aggregation._write_deterministic_csv

            def append_qc_lf_after_manifest_snapshot(frame, path):
                real_write_csv(frame, path)
                if Path(path).name == "stability_run_manifest.csv":
                    qc_path = Path(path).parent / "stability_qc_report.json"
                    with qc_path.open("ab") as handle:
                        handle.write(b"\n")

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._write_deterministic_csv",
                      side_effect=append_qc_lf_after_manifest_snapshot),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "staged QC bytes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            after = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            self.assertEqual(before, after)

    def test_build_all_frames_is_read_only_and_scan_false_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            spec_path = root / "spec.csv"
            assignments_path = root / "assignments.csv"
            run_root = root / "runs"
            log_root = root / "logs"
            runner = run_root / "conch"
            runner.mkdir(parents=True)
            log_root.mkdir()
            for path in (spec_path, assignments_path, runner / "cell_results.csv",
                         runner / "fold_results.csv", log_root / "one.log"):
                path.write_text("fixture\n", encoding="utf-8")
            cells = pd.DataFrame(
                [{"cell_id": "spop-cell", "marker": "spop", "primary_metric": "patient_auroc",
                  "patient_metric": 0.4}]
            )
            folds = pd.DataFrame([{"cell_id": "spop-cell", "fold": 0}])
            summary = pd.DataFrame([{"seed_null_straddle": True}])
            contrasts = pd.DataFrame(
                [{"contrast": "native_vs_1.76", "null_crossing": True}]
            )
            coordinate_manifest = pd.DataFrame(columns=aggregation.COORDINATE_MANIFEST_COLUMNS)
            log_summary = pd.DataFrame([{"invalid_page_offset_lines": 2}])
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            with (
                patch("models.aggregate_stability_grid.load_spec", return_value=pd.DataFrame()),
                patch("models.aggregate_stability_grid.load_assignments", return_value=pd.DataFrame()),
                patch(
                    "models.aggregate_stability_grid.load_runner_results",
                    return_value=(pd.DataFrame(), pd.DataFrame(),
                                  [runner / "cell_results.csv", runner / "fold_results.csv"]),
                ),
                patch(
                    "models.aggregate_stability_grid.reconcile_cells_and_folds",
                    return_value=(cells, folds, {"reconciled_cells": 1, "reconciled_folds": 1}),
                ),
                patch("models.aggregate_stability_grid.build_stability_summary", return_value=summary),
                patch("models.aggregate_stability_grid.build_stability_contrasts", return_value=contrasts),
                patch(
                    "models.aggregate_stability_grid.build_coordinate_manifest",
                    return_value=(coordinate_manifest, {"marker7_common_source_patients": None}, []),
                ),
                patch(
                    "models.aggregate_stability_grid.summarize_logs",
                    return_value=(log_summary, {"total_invalid_page_offset_lines": 2},
                                  [log_root / "one.log"]),
                ),
            ):
                result = build_all_frames(
                    spec_path,
                    assignments_path,
                    run_root,
                    log_root,
                    scan_tiffs=False,
                    require_full_grid=False,
                )
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(result["cells"].iloc[0]["cell_id"], "spop-cell")
            self.assertEqual(result["qc"]["tiff_header_scan"]["status"], "not_scanned")
            self.assertFalse(result["qc"]["tiff_header_scan"]["scan_complete"])
            self.assertEqual(result["tiff_input_paths"], [])

    def test_full_build_rejects_seventh_result_runner_before_reading_results(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_root = root / "runs"
            log_root = root / "logs"
            log_root.mkdir()
            for runner in [*aggregation.RUNNER_SPECS, "unexpected_runner"]:
                runner_dir = run_root / runner
                runner_dir.mkdir(parents=True)
                (runner_dir / "cell_results.csv").write_text("fixture\n", encoding="utf-8")
            with (
                patch("models.aggregate_stability_grid.load_spec", return_value=pd.DataFrame()),
                patch("models.aggregate_stability_grid.load_assignments", return_value=pd.DataFrame()),
                patch("models.aggregate_stability_grid.load_runner_results",
                      side_effect=AssertionError("must reject before reading results")),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "runner directories"):
                    build_all_frames(
                        root / "spec.csv", root / "assignments.csv", run_root, log_root,
                        scan_tiffs=False, require_full_grid=True,
                    )

    def test_cli_defaults_are_strict_and_weakening_flags_are_explicit(self):
        defaults = parse_args([])
        self.assertEqual(defaults.spec, Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv"))
        self.assertEqual(defaults.fold_assignments, Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv"))
        self.assertEqual(defaults.run_root, Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full"))
        self.assertEqual(defaults.log_root, Path("resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs"))
        self.assertEqual(defaults.output_dir, Path("resources/projects/prostate_biomarker_validation/model_workspace"))
        self.assertEqual(
            defaults.figure_data_dir,
            Path("projects/prostate_biomarker_validation/paper/figure_data"),
        )
        self.assertFalse(defaults.no_scan_tiffs)
        self.assertFalse(defaults.no_require_full_grid)
        weakened = parse_args(["--no-scan-tiffs", "--no-require-full-grid"])
        self.assertTrue(weakened.no_scan_tiffs)
        self.assertTrue(weakened.no_require_full_grid)

    def test_installed_payload_corruption_rolls_back_before_manifest_commit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            figure_dir = root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for target in targets.values():
                target.write_bytes(b"previous-generation\n")
            before = {name: path.read_bytes() for name, path in targets.items()}
            real_replace = os.replace
            corrupted = False

            def corrupting_replace(source, destination):
                nonlocal corrupted
                real_replace(source, destination)
                destination = Path(destination)
                if (destination.parent == output_dir
                        and destination.name == "stability_summary.csv" and not corrupted):
                    destination.write_bytes(b"corrupt-installed-payload\n")
                    corrupted = True

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.replace", side_effect=corrupting_replace),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "installed output"):
                    run_aggregation(
                        root / "spec.csv", root / "assign.csv", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0.0,
                    )
            self.assertEqual(before, {name: path.read_bytes() for name, path in targets.items()})

    def test_late_installed_qc_mutation_rolls_back_before_manifest_commit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                target.write_bytes(f"previous-{index}\n".encode())
            before = {name: path.read_bytes() for name, path in targets.items()}
            real_replace = os.replace
            qc_mutated = False

            def mutate_installed_qc(source, destination):
                nonlocal qc_mutated
                real_replace(source, destination)
                destination = Path(destination)
                if (destination == output_dir / "stability_qc_report.json"
                        and not qc_mutated):
                    with destination.open("ab") as handle:
                        handle.write(b"\n")
                    qc_mutated = True

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.replace",
                      side_effect=mutate_installed_qc),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "installed QC bytes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertTrue(qc_mutated)
            self.assertEqual(before, {name: path.read_bytes() for name, path in targets.items()})

    def test_equal_or_nested_output_roots_are_rejected_before_input_reads(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for figure_dir in (root / "published", root / "published" / "figures"):
                with self.subTest(figure_dir=figure_dir):
                    with (
                        patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                              side_effect=AssertionError("must reject output roots first")),
                    ):
                        with self.assertRaisesRegex(StabilityGridIntegrityError, "output roots"):
                            run_aggregation(
                                root / "spec", root / "assign", root / "runs", root / "logs",
                                root / "published", figure_dir,
                                scan_tiffs=False, require_full_grid=False,
                            )

    def test_existing_publication_lock_stops_before_input_reads(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            output_dir.mkdir(parents=True)
            (output_dir / ".stability-aggregation.lock").write_text(
                "held\n", encoding="utf-8"
            )
            with patch(
                "models.aggregate_stability_grid._enumerate_declared_inputs",
                side_effect=AssertionError("locked run must not read inputs"),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "holds the lock"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )

    def test_lock_token_write_failure_leaves_no_orphan_lock(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            with (
                patch("models.aggregate_stability_grid.os.write",
                      side_effect=OSError("injected lock token write failure")),
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      side_effect=AssertionError("lock initialization failed before inputs")),
            ):
                with self.assertRaisesRegex(OSError, "lock token write failure"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertFalse((output_dir / ".stability-aggregation.lock").exists())

    def test_short_lock_token_write_is_initialization_failure_without_orphan(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            with (
                patch("models.aggregate_stability_grid.os.write", return_value=0),
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      side_effect=AssertionError("short lock write must stop before inputs")),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "lock token write"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertFalse((output_dir / ".stability-aggregation.lock").exists())

    def test_short_lock_write_preserves_successor_replaced_after_creation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            lock_path = output_dir / ".stability-aggregation.lock"
            real_open = os.open
            successor_inode = None

            def replace_created_lock(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal successor_inode
                fd = real_open(path, flags, mode, dir_fd=dir_fd)
                if Path(path) == lock_path:
                    lock_path.unlink()
                    lock_path.write_bytes(b"successor-owner\n")
                    successor_inode = lock_path.stat().st_ino
                return fd

            with (
                patch("models.aggregate_stability_grid.os.open",
                      side_effect=replace_created_lock),
                patch("models.aggregate_stability_grid.os.write", return_value=0),
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      side_effect=AssertionError("short lock write must stop before inputs")),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "lock token write"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertEqual(lock_path.read_bytes(), b"successor-owner\n")
            self.assertEqual(lock_path.stat().st_ino, successor_inode)

    def test_lock_write_exception_preserves_successor_replaced_after_creation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            lock_path = output_dir / ".stability-aggregation.lock"
            real_open = os.open
            successor_inode = None

            def replace_created_lock(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal successor_inode
                fd = real_open(path, flags, mode, dir_fd=dir_fd)
                if Path(path) == lock_path:
                    lock_path.unlink()
                    lock_path.write_bytes(b"successor-owner\n")
                    successor_inode = lock_path.stat().st_ino
                return fd

            with (
                patch("models.aggregate_stability_grid.os.open",
                      side_effect=replace_created_lock),
                patch("models.aggregate_stability_grid.os.write",
                      side_effect=OSError("injected lock token write failure")),
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      side_effect=AssertionError("lock initialization failed before inputs")),
            ):
                with self.assertRaisesRegex(OSError, "lock token write failure"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertEqual(lock_path.read_bytes(), b"successor-owner\n")
            self.assertEqual(lock_path.stat().st_ino, successor_inode)

    def test_successful_lock_write_rejects_successor_before_input_enumeration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            lock_path = output_dir / ".stability-aggregation.lock"
            real_open = os.open
            successor_inode = None

            def replace_created_lock(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal successor_inode
                fd = real_open(path, flags, mode, dir_fd=dir_fd)
                if Path(path) == lock_path:
                    lock_path.unlink()
                    lock_path.write_bytes(b"successor-owner\n")
                    successor_inode = lock_path.stat().st_ino
                return fd

            with (
                patch("models.aggregate_stability_grid.os.open",
                      side_effect=replace_created_lock),
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      side_effect=AssertionError("visible lock is not owned")) as enumerate_inputs,
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError,
                                            "visible publication lock ownership"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            enumerate_inputs.assert_not_called()
            self.assertEqual(lock_path.read_bytes(), b"successor-owner\n")
            self.assertEqual(lock_path.stat().st_ino, successor_inode)

    def test_successor_lock_created_at_release_boundary_survives(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            lock_path = output_dir / ".stability-aggregation.lock"
            real_unlink = Path.unlink
            successor_created = False

            def boundary_unlink(path, *args, **kwargs):
                nonlocal successor_created
                result = real_unlink(path, *args, **kwargs)
                if Path(path) == lock_path and not successor_created:
                    lock_path.write_text("successor-owner\n", encoding="utf-8")
                    successor_created = True
                return result

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("pathlib.Path.unlink", new=boundary_unlink),
            ):
                run_aggregation(
                    root / "spec", root / "assign", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                )
            self.assertTrue(successor_created)
            successor_bytes = lock_path.read_bytes() if lock_path.exists() else None
            self.assertEqual(successor_bytes, b"successor-owner\n")

    def test_stale_journal_stops_without_discarding_recovery_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace"
            output_dir.mkdir(parents=True)
            journal = output_dir / ".stability-transaction-journal.json"
            journal.write_text('{"state":"interrupted"}\n', encoding="utf-8")
            with patch(
                "models.aggregate_stability_grid._enumerate_declared_inputs",
                side_effect=AssertionError("stale transaction must stop before input reads"),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "stale"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertTrue(journal.exists())

    def test_false_qc_assertion_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frames = self.publication_frames(root)
            frames["qc"]["assertions"]["reduced_mode"] = False
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "QC assertion"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            self.assertFalse((root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv").exists())

    def test_contrast_endpoint_metadata_drift_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frames = self.publication_frames(root)
            frames["contrasts"].loc[0, "encoder_b"] = "Virchow"
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "endpoint metadata"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )

    def test_malformed_raw_failure_creates_no_approved_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw = root / "raw.csv"
            raw.write_text("broken_header\n", encoding="utf-8")
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=[raw]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames",
                      side_effect=StabilityGridIntegrityError("malformed raw header")),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "malformed raw"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures", scan_tiffs=False,
                        require_full_grid=False,
                    )
            approved = aggregation._output_targets(root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures")
            self.assertFalse(any(path.exists() for path in approved.values()))
            self.assertFalse((root / "resources/projects/prostate_biomarker_validation/model_workspace/.stability-aggregation.lock").exists())

    def test_fsync_oserror_is_tolerated_and_lock_is_cleaned(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.fsync",
                      side_effect=OSError("unsupported fsync")),
            ):
                run_aggregation(
                    root / "spec", root / "assign", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                )
            self.assertFalse((output_dir / ".stability-aggregation.lock").exists())

    def test_main_prints_success_only_after_run_returns(self):
        output = io.StringIO()
        with (
            patch("models.aggregate_stability_grid.run_aggregation",
                  return_value={"output_sha256": {"one.csv": "abc"}}),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(aggregation.main([]), 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"status": "complete", "output_sha256": {"one.csv": "abc"}},
        )
        output = io.StringIO()
        with (
            patch("models.aggregate_stability_grid.run_aggregation",
                  side_effect=StabilityGridIntegrityError("failure")),
            contextlib.redirect_stdout(output),
        ):
            with self.assertRaises(StabilityGridIntegrityError):
                aggregation.main([])
        self.assertEqual(output.getvalue(), "")

    def test_replace_failure_restores_mixed_previous_output_set(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                if index % 2 == 0:
                    target.write_bytes(f"old-{index}\n".encode())
            before = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            real_replace = os.replace

            def failing_replace(source, destination):
                if Path(destination) == figure_dir / "fig9_stability_grid.csv":
                    raise OSError("injected replacement failure")
                real_replace(source, destination)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.replace", side_effect=failing_replace),
            ):
                with self.assertRaisesRegex(OSError, "injected replacement"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            after = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            self.assertEqual(before, after)

    def test_restore_failure_retains_every_previous_byte_in_recovery_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            before = {}
            for index, (name, target) in enumerate(targets.items()):
                before[name] = f"previous-{index}\n".encode()
                target.write_bytes(before[name])
            real_replace = os.replace
            forward_failed = False
            restore_failed = False

            def compound_failure(source, destination):
                nonlocal forward_failed, restore_failed
                source, destination = Path(source), Path(destination)
                if destination == figure_dir / "fig9_stability_grid.csv" and not forward_failed:
                    forward_failed = True
                    raise OSError("injected payload failure")
                if (source.parent.name.startswith(".stability-backup-")
                        and destination == output_dir / "stability_summary.csv"
                        and not restore_failed):
                    restore_failed = True
                    raise OSError("injected restore failure")
                real_replace(source, destination)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.replace", side_effect=compound_failure),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "recovery required"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            journal = output_dir / ".stability-transaction-journal.json"
            self.assertTrue(journal.exists())
            self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["state"],
                             "recovery_required")
            recovery_dirs = [
                *output_dir.glob(".stability-backup-*"),
                *figure_dir.glob(".stability-backup-*"),
            ]
            self.assertTrue(recovery_dirs)
            for name, expected_bytes in before.items():
                candidates = [targets[name], *[directory / name for directory in recovery_dirs]]
                self.assertTrue(
                    any(path.is_file() and path.read_bytes() == expected_bytes for path in candidates),
                    name,
                )

    def test_input_mutation_after_payload_installation_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for target in targets.values():
                target.write_bytes(b"old-generation\n")
            before = {name: path.read_bytes() for name, path in targets.items()}
            real_snapshot = aggregation._snapshot_paths
            snapshot_calls = 0

            def mutating_snapshot(paths):
                nonlocal snapshot_calls
                snapshot_calls += 1
                if snapshot_calls == 3:
                    frames["raw_input_paths"][0].write_bytes(b"mutated\n")
                return real_snapshot(paths)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._snapshot_paths",
                      side_effect=mutating_snapshot),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "input content"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertEqual(before, {name: path.read_bytes() for name, path in targets.items()})

    def test_qc_mutation_during_input_posthash_rolls_back_before_manifest_commit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                if index % 2:
                    target.write_bytes(f"previous-{index}\n".encode())
            before = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            real_snapshot = aggregation._snapshot_paths
            snapshot_calls = 0

            def mutate_qc_after_posthash(paths):
                nonlocal snapshot_calls
                snapshot_calls += 1
                snapshots = real_snapshot(paths)
                if snapshot_calls == 3:
                    with targets["stability_qc_report.json"].open("ab") as handle:
                        handle.write(b"\n")
                return snapshots

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._snapshot_paths",
                      side_effect=mutate_qc_after_posthash),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError,
                                            "installed QC bytes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertEqual(3, snapshot_calls)
            self.assertEqual(
                before,
                {
                    name: path.read_bytes() if path.exists() else None
                    for name, path in targets.items()
                },
            )

    def test_hashed_csv_mutation_during_input_posthash_rolls_back_before_manifest_commit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                target.write_bytes(f"previous-{index}\n".encode())
            before = {name: path.read_bytes() for name, path in targets.items()}
            real_snapshot = aggregation._snapshot_paths
            snapshot_calls = 0

            def mutate_csv_after_posthash(paths):
                nonlocal snapshot_calls
                snapshot_calls += 1
                snapshots = real_snapshot(paths)
                if snapshot_calls == 3:
                    with targets["stability_summary.csv"].open("ab") as handle:
                        handle.write(b"mutated-after-posthash\n")
                return snapshots

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._snapshot_paths",
                      side_effect=mutate_csv_after_posthash),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError,
                                            "installed output hashes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertEqual(3, snapshot_calls)
            self.assertEqual(before, {name: path.read_bytes() for name, path in targets.items()})

    def test_manifest_trailing_content_during_posthash_rolls_back_without_new_marker(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                if index % 2:
                    target.write_bytes(f"previous-{index}\n".encode())
            before = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            real_snapshot = aggregation._snapshot_paths
            snapshot_calls = 0

            def append_manifest_content_after_posthash(paths):
                nonlocal snapshot_calls
                snapshot_calls += 1
                snapshots = real_snapshot(paths)
                if snapshot_calls == 3:
                    staged_manifest = next(
                        output_dir.glob(".stability-stage-*/stability_run_manifest.csv")
                    )
                    with staged_manifest.open("ab") as handle:
                        handle.write(b"\n")
                return snapshots

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._snapshot_paths",
                      side_effect=append_manifest_content_after_posthash),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError,
                                            "staged manifest bytes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertEqual(3, snapshot_calls)
            self.assertEqual(
                before,
                {
                    name: path.read_bytes() if path.exists() else None
                    for name, path in targets.items()
                },
            )
            self.assertFalse(targets["stability_run_manifest.csv"].exists())

    def test_manifest_semantic_corruption_during_posthash_rolls_back_without_new_marker(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            output_dir.mkdir(parents=True)
            figure_dir.mkdir()
            frames = self.publication_frames(root)
            targets = aggregation._output_targets(output_dir, figure_dir)
            for index, target in enumerate(targets.values()):
                if index % 2:
                    target.write_bytes(f"previous-{index}\n".encode())
            before = {
                name: path.read_bytes() if path.exists() else None
                for name, path in targets.items()
            }
            real_snapshot = aggregation._snapshot_paths
            snapshot_calls = 0

            def corrupt_manifest_semantics_after_posthash(paths):
                nonlocal snapshot_calls
                snapshot_calls += 1
                snapshots = real_snapshot(paths)
                if snapshot_calls == 3:
                    staged_manifest = next(
                        output_dir.glob(".stability-stage-*/stability_run_manifest.csv")
                    )
                    corrupted = pd.read_csv(
                        staged_manifest, dtype=str, keep_default_na=False
                    )
                    corrupted.loc[0, "artifact_kind"] = "corrupted"
                    corrupted.to_csv(staged_manifest, index=False, lineterminator="\n")
                return snapshots

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid._snapshot_paths",
                      side_effect=corrupt_manifest_semantics_after_posthash),
            ):
                with self.assertRaisesRegex(StabilityGridIntegrityError,
                                            "staged manifest bytes"):
                    run_aggregation(
                        root / "spec", root / "assign", root / "runs", root / "logs",
                        output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                        scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                    )
            self.assertEqual(3, snapshot_calls)
            self.assertEqual(
                before,
                {
                    name: path.read_bytes() if path.exists() else None
                    for name, path in targets.items()
                },
            )
            self.assertFalse(targets["stability_run_manifest.csv"].exists())

    def test_manifest_is_installed_last(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir, figure_dir = root / "resources/projects/prostate_biomarker_validation/model_workspace", root / "figures"
            frames = self.publication_frames(root)
            replacements = []
            real_replace = os.replace

            def recording_replace(source, destination):
                replacements.append((Path(source), Path(destination)))
                real_replace(source, destination)

            with (
                patch("models.aggregate_stability_grid._enumerate_declared_inputs",
                      return_value=frames["raw_input_paths"]),
                patch("models.aggregate_stability_grid._provenance_paths", return_value=[]),
                patch("models.aggregate_stability_grid.build_all_frames", return_value=frames),
                patch("models.aggregate_stability_grid.os.replace", side_effect=recording_replace),
            ):
                run_aggregation(
                    root / "spec", root / "assign", root / "runs", root / "logs",
                    output_dir, figure_dir, generated_at_utc="2026-08-06T00:00:00Z",
                    scan_tiffs=False, require_full_grid=False, elapsed_seconds_override=0,
                )
            self.assertEqual(
                replacements[-1][1], output_dir / "stability_run_manifest.csv"
            )
            self.assertTrue(
                all(source.parent.parent == destination.parent
                    for source, destination in replacements)
            )

    @unittest.skipUnless(
        FULL_SPEC.is_file() and FULL_RUN_ROOT.is_dir(), "local full grid is unavailable"
    )
    def test_full_repository_grid_reconciles_without_writing(self):
        nadt_metadata = FULL_RUN_ROOT / "nadt_conch/meta_s0_mpp0.88.csv"
        representative_tiff = Path(pd.read_csv(nadt_metadata).iloc[0]["path"])
        representative_tiff = (
            ROOT / "resources/data/shared/opendataset"
            / representative_tiff.relative_to(ROOT / "opendataset")
        )
        representative_inputs = [
            FULL_SPEC,
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
            FULL_RUN_ROOT / "conch/cell_results.csv",
            FULL_RUN_ROOT / "conch/fold_results.csv",
            FULL_RUN_ROOT / "conch/coordinates_s0_mpp0.88.csv",
            FULL_RUN_ROOT / "conch/meta_s0_mpp0.88.csv",
            nadt_metadata,
            FULL_RUN_ROOT / "marker7_conch/source_meta_s0_mpp0.88.csv",
            FULL_RUN_ROOT / "marker7_conch/target_meta_s0_mpp0.88.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs/tcga_conch.log",
            representative_tiff,
        ]
        representative_hashes = {
            path: aggregation._sha256(path) for path in representative_inputs
        }
        approved_outputs = [
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_results.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_tile_coordinate_manifest.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_run_manifest.csv",
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_qc_report.json",
            ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_grid.csv",
            ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_contrasts.csv",
        ]
        output_state = {
            path: path.read_bytes() if path.exists() else None for path in approved_outputs
        }
        result = build_all_frames(
            FULL_SPEC,
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
            FULL_RUN_ROOT,
            ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs",
            scan_tiffs=True,
            require_full_grid=True,
        )
        aggregation._validate_publishable_frames(
            aggregation._normalize_publication_frames(result), require_full_grid=True
        )
        self.assertEqual(
            (len(result["cells"]), len(result["folds"]), len(result["summary"]),
             len(result["contrasts"]), len(result["coordinate_manifest"])),
            (360, 1800, 72, 390, 60),
        )
        self.assertEqual(
            (len(result["runner_input_paths"]), len(result["coordinate_input_paths"]),
             len(result["log_input_paths"]), len(result["tiff_input_paths"])),
            (12, 140, 6, 463),
        )
        self.assertEqual(result["qc"]["chance_or_worse_cells"], 26)
        self.assertEqual(result["qc"]["native_null_crossings"], 20)
        self.assertEqual(result["qc"]["shared_encoder_null_crossings"], 4)
        self.assertEqual(result["qc"]["seed_null_straddles"], 9)
        self.assertEqual(result["qc"]["marker7_common_source_patients"], 498)
        self.assertEqual(result["qc"]["invalid_page_offset_log_lines"], 26)
        scan = result["qc"]["tiff_header_scan"]
        self.assertEqual(
            (scan["requested_path_count"], scan["scanned_path_count"],
             scan["scan_failure_count"], scan["affected_slide_count"]),
            (463, 463, 0, 2),
        )
        for name, expected_count in {
            "raw_input_paths": 160,
            "runner_input_paths": 12,
            "coordinate_input_paths": 140,
            "log_input_paths": 6,
            "tiff_input_paths": 463,
        }.items():
            paths = result[name]
            self.assertEqual(len(paths), expected_count, name)
            self.assertEqual(len(set(paths)), expected_count, name)
            self.assertEqual(paths, sorted(paths), name)
        retention = result["qc"]["warning_slide_retention"]
        self.assertEqual(retention["warning_slide_count"], 2)
        self.assertEqual(retention["nadt_coordinate_shards"], 20)
        self.assertTrue(retention["all_warning_slides_retained_in_all_shards"])
        details = retention["retention_details"]
        self.assertEqual(len(details), 40)
        self.assertEqual(
            pd.DataFrame(details).groupby("file_name").size().to_dict(),
            {
                "1004.Prostate.Bx5A.slide.04.HE.tiff": 20,
                "1004.Prostate.Bx7A.slide.04.HE.tiff": 20,
            },
        )
        self.assertEqual(
            {
                (row["raw_runner_dir"], f'{float(row["target_mpp"]):.2f}'):
                    row["used_pyramid_level"]
                for row in details
            },
            {
                ("nadt_conch", "0.88"): 2,
                ("nadt_conch", "1.76"): 3,
                ("nadt_virchow", "0.44"): 1,
                ("nadt_virchow", "1.76"): 3,
            },
        )
        json.dumps(result["qc"], allow_nan=False)
        self.assertEqual(
            representative_hashes,
            {path: aggregation._sha256(path) for path in representative_inputs},
        )
        self.assertEqual(
            output_state,
            {path: path.read_bytes() if path.exists() else None for path in approved_outputs},
        )


class CoordinateAndLogTests(unittest.TestCase):
    """Protect coordinate, metadata, log, and TIFF QC boundaries."""

    STANDARD_COORDINATE_COLUMNS = [
        "file_name", "case_id", "encoder", "sampling_seed", "target_mpp",
        "pyramid_level", "level_mpp", "x", "y", "crop_size_native_px",
        "tissue_fraction", "tile_rank",
    ]
    MARKER_COORDINATE_COLUMNS = ["cohort", *STANDARD_COORDINATE_COLUMNS]

    def write_standard_shard(self, root, runner="conch", seed=0, target_mpp=0.88):
        runner_root = Path(root) / runner
        runner_root.mkdir(parents=True, exist_ok=True)
        encoder = "Virchow" if "virchow" in runner else "CONCH"
        suffix = f"s{seed}_mpp{target_mpp:.2f}"
        coordinate_path = runner_root / f"coordinates_{suffix}.csv"
        metadata_path = runner_root / f"meta_{suffix}.csv"
        is_nadt = runner.startswith("nadt_")
        file_name = "slide.tiff" if is_nadt else "slide.svs"
        case_id = "1001" if is_nadt else "case-1"
        coordinates = pd.DataFrame(
            [
                {
                    "file_name": file_name,
                    "case_id": case_id,
                    "encoder": encoder,
                    "sampling_seed": seed,
                    "target_mpp": target_mpp,
                    "pyramid_level": 0,
                    "level_mpp": 0.25,
                    "x": rank,
                    "y": rank + 1,
                    "crop_size_native_px": 1577,
                    "tissue_fraction": 0.75,
                    "tile_rank": rank,
                }
                for rank in range(64)
            ]
        )
        coordinates.to_csv(coordinate_path, index=False)
        if is_nadt:
            metadata = pd.DataFrame(
                [{"file_name": file_name, "patient_id": case_id, "phenotype": 1,
                  "gleason": 7, "path": f"/slides/{file_name}"}]
            )
        else:
            metadata = pd.DataFrame(
                [{"file_name": file_name, "case_id": case_id, "gleason_sum": 7,
                  "pten": 0, "spop": 1, "ar": 2.5}]
            )
        metadata.to_csv(metadata_path, index=False)
        return coordinate_path, metadata_path

    def write_marker_shard(self, root, seed=0, target_mpp=0.88):
        runner_root = Path(root) / "marker7_conch"
        runner_root.mkdir(parents=True, exist_ok=True)
        suffix = f"s{seed}_mpp{target_mpp:.2f}"
        coordinate_path = runner_root / f"coordinates_{suffix}.csv"
        source_path = runner_root / f"source_meta_{suffix}.csv"
        target_path = runner_root / f"target_meta_{suffix}.csv"
        entities = (
            ("LEOPARD", "source.tif", "source-case", 0),
            ("TCGA-PRAD", "target.svs", "target-case", 1),
        )
        pd.DataFrame(
            [
                {
                    "cohort": cohort,
                    "file_name": file_name,
                    "case_id": case_id,
                    "encoder": "CONCH",
                    "sampling_seed": seed,
                    "target_mpp": target_mpp,
                    "pyramid_level": 0,
                    "level_mpp": 0.25,
                    "x": rank,
                    "y": rank,
                    "crop_size_native_px": 1577,
                    "tissue_fraction": 0.75,
                    "tile_rank": rank,
                }
                for cohort, file_name, case_id, _ in entities
                for rank in range(64)
            ],
            columns=self.MARKER_COORDINATE_COLUMNS,
        ).to_csv(coordinate_path, index=False)
        pd.DataFrame(
            [{"case_id": "source-case", "event": 0, "follow_up_years": 3.5,
              "n_tiles": 64, "file_name": "source.tif", "path": "/source.tif"}]
        ).to_csv(source_path, index=False)
        pd.DataFrame(
            [{"file_name": "target.svs", "case_id": "target-case", "path": "/target.svs",
              "event": 1, "follow_up_y": 2.0}]
        ).to_csv(target_path, index=False)
        return coordinate_path, source_path, target_path

    def write_full_discovery_placeholders(self, root):
        runner_axes = {
            "conch": ("0.88", "1.76"),
            "virchow": ("0.44", "1.76"),
            "nadt_conch": ("0.88", "1.76"),
            "nadt_virchow": ("0.44", "1.76"),
            "marker7_conch": ("0.88", "1.76"),
            "marker7_virchow": ("0.44", "1.76"),
        }
        for runner, mpps in runner_axes.items():
            runner_root = Path(root) / runner
            runner_root.mkdir(parents=True, exist_ok=True)
            for seed in range(5):
                for mpp in mpps:
                    suffix = f"s{seed}_mpp{mpp}"
                    coordinate_header = (
                        self.MARKER_COORDINATE_COLUMNS
                        if runner.startswith("marker7_")
                        else self.STANDARD_COORDINATE_COLUMNS
                    )
                    (runner_root / f"coordinates_{suffix}.csv").write_text(
                        ",".join(coordinate_header) + "\n", encoding="utf-8"
                    )
                    if runner.startswith("marker7_"):
                        (runner_root / f"source_meta_{suffix}.csv").write_text(
                            "case_id,event,follow_up_years,n_tiles,file_name,path\n",
                            encoding="utf-8",
                        )
                        (runner_root / f"target_meta_{suffix}.csv").write_text(
                            "file_name,case_id,path,event,follow_up_y\n", encoding="utf-8"
                        )
                    else:
                        header = (
                            "file_name,patient_id,phenotype,gleason,path\n"
                            if runner.startswith("nadt_")
                            else "file_name,case_id,gleason_sum,pten,spop,ar\n"
                        )
                        (runner_root / f"meta_{suffix}.csv").write_text(header, encoding="utf-8")

    def full_coordinate_invariant_fixture(self):
        rows = []
        source_sets = []
        axes = {
            "conch": ("0.88", "1.76"),
            "virchow": ("0.44", "1.76"),
            "nadt_conch": ("0.88", "1.76"),
            "nadt_virchow": ("0.44", "1.76"),
            "marker7_conch": ("0.88", "1.76"),
            "marker7_virchow": ("0.44", "1.76"),
        }
        common = {f"case-{index}" for index in range(498)}
        marker_index = 0
        for runner, mpps in axes.items():
            for seed in range(5):
                for mpp in mpps:
                    row = {
                        "raw_runner_dir": runner,
                        "sampling_seed": seed,
                        "target_mpp": float(mpp),
                        "n_coordinate_rows": 0,
                        "n_slides": 0,
                        "n_patients": 0,
                        "n_phenotype_evaluable_slides": pd.NA,
                        "n_gleason_evaluable_slides": pd.NA,
                        "n_gleason_evaluable_patients": pd.NA,
                        "marker7_source_patients": pd.NA,
                        "marker7_target_slides": pd.NA,
                        "marker7_target_patients": pd.NA,
                        "marker7_target_events": pd.NA,
                    }
                    if runner in {"conch", "virchow"}:
                        row.update(n_coordinate_rows=19200, n_slides=300, n_patients=273)
                    elif runner.startswith("nadt_"):
                        row.update(
                            n_coordinate_rows=29632,
                            n_slides=463,
                            n_patients=39,
                            n_phenotype_evaluable_slides=463,
                            n_gleason_evaluable_slides=334,
                            n_gleason_evaluable_patients=39,
                        )
                    else:
                        if runner == "marker7_conch":
                            count = 498 if marker_index % 2 == 0 else 500
                        else:
                            count = 499 if marker_index % 2 == 0 else 502
                        extras = {
                            f"extra-{marker_index}-{index}" for index in range(count - 498)
                        }
                        source_sets.append(common | extras)
                        row.update(
                            marker7_source_patients=count,
                            marker7_target_slides=297,
                            marker7_target_patients=270,
                            marker7_target_events=57,
                        )
                        marker_index += 1
                    rows.append(row)
        return pd.DataFrame(rows), source_sets

    def write_warning_coordinate_shards(self, root):
        warning_names = (
            "1004.Prostate.Bx5A.slide.04.HE.tiff",
            "1004.Prostate.Bx7A.slide.04.HE.tiff",
        )
        axes = (
            ("nadt_conch", "CONCH", 0.88, 2),
            ("nadt_conch", "CONCH", 1.76, 3),
            ("nadt_virchow", "Virchow", 0.44, 1),
            ("nadt_virchow", "Virchow", 1.76, 3),
        )
        paths = []
        for runner, encoder, mpp, level in axes:
            runner_root = Path(root) / runner
            runner_root.mkdir(parents=True, exist_ok=True)
            for seed in range(5):
                path = runner_root / f"coordinates_s{seed}_mpp{mpp:.2f}.csv"
                pd.DataFrame(
                    [
                        {
                            "file_name": file_name,
                            "case_id": "1004",
                            "encoder": encoder,
                            "sampling_seed": seed,
                            "target_mpp": mpp,
                            "pyramid_level": level,
                            "level_mpp": 0.25,
                            "x": rank,
                            "y": rank,
                            "crop_size_native_px": 1577,
                            "tissue_fraction": 0.8,
                            "tile_rank": rank,
                        }
                        for file_name in warning_names
                        for rank in range(64)
                    ],
                    columns=self.STANDARD_COORDINATE_COLUMNS,
                ).to_csv(path, index=False)
                paths.append(path)
        return warning_names, paths

    def test_coordinate_manifest_reconciles_one_exact_standard_shard(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            coordinate_path, metadata_path = self.write_standard_shard(temporary_directory)
            metadata_before = metadata_path.read_bytes()
            manifest, qc, paths = build_coordinate_manifest(
                Path(temporary_directory), require_full_grid=False
            )
            self.assertEqual(len(manifest), 1)
            row = manifest.iloc[0]
            self.assertEqual(row["raw_runner_dir"], "conch")
            self.assertEqual(row["encoder"], "CONCH")
            self.assertEqual(row["sampling_seed"], 0)
            self.assertEqual(row["target_mpp"], 0.88)
            self.assertEqual(row["raw_coordinate_sha256"], hashlib.sha256(coordinate_path.read_bytes()).hexdigest())
            self.assertEqual(row["n_coordinate_rows"], 64)
            self.assertEqual(row["n_slides"], 1)
            self.assertEqual(row["n_patients"], 1)
            self.assertEqual(row["tile_rank_min"], 0)
            self.assertEqual(row["tile_rank_max"], 63)
            self.assertEqual(row["n_rank_violations"], 0)
            self.assertTrue(row["coordinate_metadata_reconciled"])
            self.assertEqual(qc["coordinate_shards"], 1)
            self.assertEqual(
                paths,
                sorted([coordinate_path, metadata_path], key=lambda path: path.as_posix()),
            )
            self.assertEqual(metadata_path.read_bytes(), metadata_before)

    def test_coordinate_manifest_rejects_missing_duplicate_and_extra_ranks(self):
        mutations = ("missing", "duplicate", "extra")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                coordinate_path, _ = self.write_standard_shard(temporary_directory)
                frame = pd.read_csv(coordinate_path, dtype=str)
                if mutation == "missing":
                    frame = frame.loc[frame["tile_rank"].ne("63")]
                elif mutation == "duplicate":
                    duplicate = frame.iloc[[0]].copy()
                    duplicate["tile_rank"] = "0.0"
                    frame = pd.concat([frame, duplicate], ignore_index=True)
                else:
                    extra = frame.iloc[[0]].copy()
                    extra["tile_rank"] = "64"
                    frame = pd.concat([frame, extra], ignore_index=True)
                frame.to_csv(coordinate_path, index=False)
                with self.assertRaisesRegex(StabilityGridIntegrityError, "rank|64 rows|duplicate"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_manifest_rejects_metadata_set_and_duplicate_key_breaks(self):
        for mutation in ("set_mismatch", "duplicate"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                _, metadata_path = self.write_standard_shard(temporary_directory)
                metadata = pd.read_csv(metadata_path, dtype=str)
                if mutation == "set_mismatch":
                    metadata.loc[0, "case_id"] = "wrong-case"
                else:
                    metadata = pd.concat([metadata, metadata], ignore_index=True)
                metadata.to_csv(metadata_path, index=False)
                with self.assertRaisesRegex(StabilityGridIntegrityError, "metadata"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_manifest_rejects_exact_schema_and_row_width_breaks(self):
        for mutation in ("reordered_coordinate", "extra_coordinate", "malformed_width"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                coordinate_path, _ = self.write_standard_shard(temporary_directory)
                lines = coordinate_path.read_text(encoding="utf-8").splitlines()
                if mutation == "reordered_coordinate":
                    lines[0] = ",".join(reversed(self.STANDARD_COORDINATE_COLUMNS))
                elif mutation == "extra_coordinate":
                    lines[0] += ",unexpected"
                    lines[1] += ",x"
                else:
                    lines[1] = lines[1].rsplit(",", 1)[0]
                coordinate_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(StabilityGridIntegrityError, "header|field"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_marker7_coordinate_header_is_exact(self):
        for mutation in ("reordered", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                coordinate_path, _, _ = self.write_marker_shard(temporary_directory)
                lines = coordinate_path.read_text(encoding="utf-8").splitlines()
                if mutation == "reordered":
                    lines[0] = ",".join(reversed(self.MARKER_COORDINATE_COLUMNS))
                else:
                    lines[0] += ",unexpected"
                    lines[1] += ",x"
                coordinate_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(StabilityGridIntegrityError, "header"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_manifest_rejects_each_exact_metadata_header_break(self):
        fixtures = (
            ("conch", self.write_standard_shard, 1),
            ("nadt_conch", self.write_standard_shard, 1),
            ("marker7_source", self.write_marker_shard, 1),
            ("marker7_target", self.write_marker_shard, 2),
        )
        for label, writer, path_index in fixtures:
            for mutation in ("reordered", "extra"):
                with self.subTest(label=label, mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                    if label == "conch":
                        paths = writer(temporary_directory, runner="conch")
                    elif label == "nadt_conch":
                        paths = writer(temporary_directory, runner="nadt_conch")
                    else:
                        paths = writer(temporary_directory)
                    metadata_path = paths[path_index]
                    lines = metadata_path.read_text(encoding="utf-8").splitlines()
                    header = lines[0].split(",")
                    if mutation == "reordered":
                        lines[0] = ",".join(reversed(header))
                    else:
                        lines[0] += ",unexpected"
                        lines[1] += ",x"
                    metadata_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(StabilityGridIntegrityError, "header"):
                        build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_manifest_rejects_row_provenance_and_filename_breaks(self):
        for mutation in ("encoder", "seed", "mpp", "filename"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                coordinate_path, metadata_path = self.write_standard_shard(temporary_directory)
                if mutation == "filename":
                    coordinate_path.rename(coordinate_path.with_name("coordinates_seed0_mpp0.88.csv"))
                    metadata_path.rename(metadata_path.with_name("meta_seed0_mpp0.88.csv"))
                else:
                    frame = pd.read_csv(coordinate_path, dtype=str)
                    column, value = {
                        "encoder": ("encoder", "Virchow"),
                        "seed": ("sampling_seed", "1"),
                        "mpp": ("target_mpp", "1.76"),
                    }[mutation]
                    frame.loc[0, column] = value
                    frame.to_csv(coordinate_path, index=False)
                with self.assertRaisesRegex(StabilityGridIntegrityError, "filename|encoder|seed|MPP|mpp"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_nadt_patient_id_normalizes_only_in_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, metadata_path = self.write_standard_shard(temporary_directory, runner="nadt_conch")
            before = metadata_path.read_bytes()
            manifest, _, _ = build_coordinate_manifest(
                Path(temporary_directory), require_full_grid=False
            )
            self.assertTrue(manifest.iloc[0]["coordinate_metadata_reconciled"])
            self.assertEqual(metadata_path.read_bytes(), before)
            self.assertEqual(metadata_path.read_text(encoding="utf-8").splitlines()[0],
                             "file_name,patient_id,phenotype,gleason,path")

    def test_marker7_reconciles_both_cohorts_and_rejects_collisions_or_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, source_path, target_path = self.write_marker_shard(temporary_directory)
            manifest, _, paths = build_coordinate_manifest(
                Path(temporary_directory), require_full_grid=False
            )
            row = manifest.iloc[0]
            self.assertEqual(row["marker7_source_slides"], 1)
            self.assertEqual(row["marker7_target_slides"], 1)
            self.assertEqual(paths, sorted(paths, key=lambda path: path.as_posix()))
            self.assertIn(source_path, paths)
            self.assertIn(target_path, paths)
        for mutation in ("coordinate_wrong_cohort", "metadata_collision", "target_mismatch"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                coordinate_path, source_path, target_path = self.write_marker_shard(temporary_directory)
                if mutation == "coordinate_wrong_cohort":
                    coordinates = pd.read_csv(coordinate_path, dtype=str)
                    coordinates.loc[coordinates["cohort"].eq("LEOPARD"), "cohort"] = "TCGA-PRAD"
                    coordinates.to_csv(coordinate_path, index=False)
                elif mutation == "metadata_collision":
                    target = pd.read_csv(target_path, dtype=str)
                    target.loc[0, ["file_name", "case_id"]] = ["source.tif", "source-case"]
                    target.to_csv(target_path, index=False)
                else:
                    target = pd.read_csv(target_path, dtype=str)
                    target.loc[0, "case_id"] = "wrong-target"
                    target.to_csv(target_path, index=False)
                with self.assertRaisesRegex(StabilityGridIntegrityError, "cohort|collision|metadata"):
                    build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_manifest_is_deterministic_for_reversed_creation_order(self):
        manifests = []
        relative_paths = []
        for seeds in ((1, 0), (0, 1)):
            with tempfile.TemporaryDirectory() as temporary_directory:
                for seed in seeds:
                    self.write_standard_shard(temporary_directory, seed=seed)
                manifest, _, paths = build_coordinate_manifest(
                    Path(temporary_directory), require_full_grid=False
                )
                manifests.append(
                    manifest[["raw_runner_dir", "sampling_seed", "target_mpp"]].to_dict("records")
                )
                root = Path(temporary_directory)
                relative_paths.append([path.relative_to(root).as_posix() for path in paths])
        self.assertEqual(manifests[0], manifests[1])
        self.assertEqual(relative_paths[0], relative_paths[1])

    def test_coordinate_discovery_rejects_unexpected_runner_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            coordinate_path, metadata_path = self.write_standard_shard(temporary_directory)
            rogue = Path(temporary_directory) / "rogue_runner"
            rogue.mkdir()
            (rogue / coordinate_path.name).write_bytes(coordinate_path.read_bytes())
            (rogue / metadata_path.name).write_bytes(metadata_path.read_bytes())
            with self.assertRaisesRegex(StabilityGridIntegrityError, "unexpected.*runner"):
                build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_coordinate_discovery_rejects_exact_full_filename_set_drift(self):
        mutations = (
            "missing_coordinate",
            "unexpected_coordinate",
            "missing_metadata",
            "unexpected_metadata",
            "wrong_axis",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                self.write_full_discovery_placeholders(temporary_directory)
                root = Path(temporary_directory)
                if mutation == "missing_coordinate":
                    (root / "conch/coordinates_s0_mpp0.88.csv").unlink()
                elif mutation == "unexpected_coordinate":
                    (root / "conch/coordinates_s5_mpp0.88.csv").write_text(
                        ",".join(self.STANDARD_COORDINATE_COLUMNS) + "\n", encoding="utf-8"
                    )
                elif mutation == "missing_metadata":
                    (root / "conch/meta_s0_mpp0.88.csv").unlink()
                elif mutation == "unexpected_metadata":
                    (root / "conch/meta_s5_mpp0.88.csv").write_text(
                        "file_name,case_id,gleason_sum,pten,spop,ar\n", encoding="utf-8"
                    )
                else:
                    (root / "virchow/coordinates_s0_mpp0.44.csv").rename(
                        root / "virchow/coordinates_s0_mpp0.88.csv"
                    )
                with self.assertRaisesRegex(StabilityGridIntegrityError, "filename set"):
                    build_coordinate_manifest(root, require_full_grid=True)

    def test_coordinate_discovery_rejects_wrong_family_metadata_in_reduced_mode(self):
        cases = (
            ("marker7", "meta_s0_mpp0.88.csv"),
            ("standard_source", "source_meta_s0_mpp0.88.csv"),
            ("standard_target", "target_meta_s0_mpp0.88.csv"),
        )
        for label, wrong_name in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary_directory:
                if label == "marker7":
                    self.write_marker_shard(temporary_directory)
                    runner_root = Path(temporary_directory) / "marker7_conch"
                else:
                    self.write_standard_shard(temporary_directory)
                    runner_root = Path(temporary_directory) / "conch"
                (runner_root / wrong_name).write_text("wrong_family\n", encoding="utf-8")
                with self.assertRaisesRegex(StabilityGridIntegrityError, "metadata paths"):
                    build_coordinate_manifest(
                        Path(temporary_directory), require_full_grid=False
                    )

    def test_coordinate_discovery_rejects_wrong_family_metadata_in_full_mode(self):
        cases = (
            ("marker7_conch", "meta_s0_mpp0.88.csv"),
            ("conch", "source_meta_s0_mpp0.88.csv"),
            ("conch", "target_meta_s0_mpp0.88.csv"),
        )
        for runner, wrong_name in cases:
            with self.subTest(runner=runner, wrong_name=wrong_name), tempfile.TemporaryDirectory() as temporary_directory:
                self.write_full_discovery_placeholders(temporary_directory)
                (Path(temporary_directory) / runner / wrong_name).write_text(
                    "wrong_family\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(StabilityGridIntegrityError, "metadata filename set"):
                    build_coordinate_manifest(
                        Path(temporary_directory), require_full_grid=True
                    )

    def test_coordinate_manifest_rejects_header_only_empty_shard_cleanly(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            coordinate_path, _ = self.write_standard_shard(temporary_directory)
            coordinate_path.write_text(
                ",".join(self.STANDARD_COORDINATE_COLUMNS) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(StabilityGridIntegrityError, "empty coordinate"):
                build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_full_coordinate_invariants_record_source_variation_and_common_intersection(self):
        manifest, source_sets = self.full_coordinate_invariant_fixture()
        qc = aggregation._validate_full_coordinate_invariants(manifest, source_sets)
        self.assertEqual(qc["marker7_source_min_patients"], 498)
        self.assertEqual(qc["marker7_source_max_patients"], 502)
        self.assertEqual(qc["marker7_common_source_patients"], 498)
        self.assertTrue(qc["marker7_source_retention_varies"])
        self.assertNotIn("source_constant", qc)

    def test_full_coordinate_invariants_reject_each_cohort_count_break(self):
        mutations = (
            ("conch", "n_slides", 299, "TCGA"),
            ("conch", "n_patients", 272, "TCGA"),
            ("nadt_conch", "n_slides", 462, "NADT"),
            ("nadt_conch", "n_patients", 38, "NADT"),
            ("nadt_conch", "n_phenotype_evaluable_slides", 462, "NADT"),
            ("nadt_conch", "n_gleason_evaluable_slides", 333, "NADT"),
            ("nadt_conch", "n_gleason_evaluable_patients", 38, "NADT"),
            ("marker7_conch", "marker7_target_slides", 296, "marker7 target"),
            ("marker7_conch", "marker7_target_patients", 269, "marker7 target"),
            ("marker7_conch", "marker7_target_events", 56, "marker7 target"),
        )
        for runner, column, value, message in mutations:
            with self.subTest(column=column):
                manifest, source_sets = self.full_coordinate_invariant_fixture()
                index = manifest.index[manifest["raw_runner_dir"].eq(runner)][0]
                manifest.loc[index, column] = value
                with self.assertRaisesRegex(StabilityGridIntegrityError, message):
                    aggregation._validate_full_coordinate_invariants(manifest, source_sets)

    def test_full_coordinate_invariants_reject_source_range_and_common_breaks(self):
        manifest, source_sets = self.full_coordinate_invariant_fixture()
        source_sets[0] = set(list(source_sets[0])[:-1])
        with self.assertRaisesRegex(StabilityGridIntegrityError, "498 through 502"):
            aggregation._validate_full_coordinate_invariants(manifest, source_sets)
        manifest, source_sets = self.full_coordinate_invariant_fixture()
        removed = sorted(source_sets[0])[0]
        source_sets[0].remove(removed)
        source_sets[0].add("replacement-case")
        with self.assertRaisesRegex(StabilityGridIntegrityError, "common source"):
            aggregation._validate_full_coordinate_invariants(manifest, source_sets)

    def test_marker7_rejects_inconsistent_repeated_target_event_labels(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            coordinate_path, _, target_path = self.write_marker_shard(temporary_directory)
            coordinates = pd.read_csv(coordinate_path, dtype=str)
            extra = coordinates.loc[coordinates["cohort"].eq("TCGA-PRAD")].copy()
            extra["file_name"] = "target-two.svs"
            coordinates = pd.concat([coordinates, extra], ignore_index=True)
            coordinates.to_csv(coordinate_path, index=False)
            target = pd.read_csv(target_path, dtype=str)
            target = pd.concat(
                [
                    target,
                    pd.DataFrame(
                        [{"file_name": "target-two.svs", "case_id": "target-case",
                          "path": "/target-two.svs", "event": 0, "follow_up_y": 2.0}]
                    ),
                ],
                ignore_index=True,
            )
            target.to_csv(target_path, index=False)
            with self.assertRaisesRegex(StabilityGridIntegrityError, "event labels"):
                build_coordinate_manifest(Path(temporary_directory), require_full_grid=False)

    def test_warning_slide_retention_requires_twenty_shards_and_literal_levels(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            warning_names, coordinate_paths = self.write_warning_coordinate_shards(
                temporary_directory
            )
            affected = [Path("/slides") / name for name in warning_names]
            result = aggregation._build_warning_slide_retention(
                affected, coordinate_paths, require_full_grid=True
            )
            self.assertEqual(result["warning_slide_count"], 2)
            self.assertEqual(result["nadt_coordinate_shards"], 20)
            self.assertEqual(len(result["retention_details"]), 40)
            self.assertTrue(result["all_warning_slides_retained_in_all_shards"])
            self.assertEqual(
                sorted({detail["used_pyramid_level"] for detail in result["retention_details"]}),
                [1, 2, 3],
            )

    def test_warning_slide_retention_rejects_missing_rows_and_wrong_level(self):
        for mutation in ("missing", "level"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_directory:
                warning_names, coordinate_paths = self.write_warning_coordinate_shards(
                    temporary_directory
                )
                path = coordinate_paths[0]
                frame = pd.read_csv(path, dtype=str)
                affected_rows = frame["file_name"].eq(warning_names[0])
                if mutation == "missing":
                    frame = frame.loc[~(affected_rows & frame["tile_rank"].eq("63"))]
                else:
                    frame.loc[affected_rows, "pyramid_level"] = "9"
                frame.to_csv(path, index=False)
                with self.assertRaisesRegex(StabilityGridIntegrityError, "warning slide|level|64"):
                    aggregation._build_warning_slide_retention(
                        [Path(name) for name in warning_names],
                        coordinate_paths,
                        require_full_grid=True,
                    )

    def test_full_warning_slide_retention_rejects_zero_one_and_three_affected_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            warning_names, coordinate_paths = self.write_warning_coordinate_shards(
                temporary_directory
            )
            cases = (
                ("zero", []),
                ("one", [Path(warning_names[0])]),
                ("three", [Path(name) for name in warning_names] + [Path("third.tiff")]),
            )
            for label, affected in cases:
                with self.subTest(label=label):
                    with self.assertRaisesRegex(
                        StabilityGridIntegrityError, "exact two frozen affected"
                    ):
                        aggregation._build_warning_slide_retention(
                            affected, coordinate_paths, require_full_grid=True
                        )

    def test_full_warning_slide_retention_rejects_wrong_two_basenames(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            warning_names, coordinate_paths = self.write_warning_coordinate_shards(
                temporary_directory
            )
            replacements = {
                warning_names[0]: "wrong-a.tiff",
                warning_names[1]: "wrong-b.tiff",
            }
            for path in coordinate_paths:
                frame = pd.read_csv(path, dtype=str)
                frame["file_name"] = frame["file_name"].replace(replacements)
                frame.to_csv(path, index=False)
            with self.assertRaisesRegex(
                StabilityGridIntegrityError, "frozen affected TIFF basenames"
            ):
                aggregation._build_warning_slide_retention(
                    [Path("wrong-a.tiff"), Path("wrong-b.tiff")],
                    coordinate_paths,
                    require_full_grid=True,
                )

    def test_log_summary_keeps_physical_lines_and_events_distinct(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "synthetic.log"
            log_path.write_text(
                "ERROR:tifffile invalid page offset 10\n"
                "tifffile invalid page offset 20\n"
                "/tmp/run.py:1: FutureWarning: changed\n"
                "  warnings.warn('changed', FutureWarning)\n"
                "[resume] continuing\n",
                encoding="utf-8",
            )
            summary, qc, paths = summarize_logs(Path(temporary_directory))
            row = summary.iloc[0]
            self.assertEqual(row["total_lines"], 5)
            self.assertEqual(row["invalid_page_offset_lines"], 2)
            self.assertEqual(row["invalid_page_offset_error_prefixed_lines"], 1)
            self.assertEqual(row["invalid_page_offset_unprefixed_lines"], 1)
            self.assertEqual(row["futurewarning_lines"], 2)
            self.assertEqual(row["futurewarning_events"], 1)
            self.assertEqual(row["error_prefixed_lines"], 1)
            self.assertEqual(row["resume_lines"], 1)
            self.assertEqual(row["traceback_lines"], 0)
            self.assertEqual(row["log_sha256"], hashlib.sha256(log_path.read_bytes()).hexdigest())
            self.assertEqual(paths, [log_path])
            self.assertTrue(qc["historical_log_observations_nonfatal"])
            self.assertIn("append/resume", qc["log_count_limitation"])

    def test_log_summary_keeps_unrelated_error_and_warning_categories_separate(self):
        contents = (
            "ERROR:worker unrelated failure\n",
            "WARNING:worker unrelated warning\n",
        )
        for content in contents:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary_directory:
                path = Path(temporary_directory) / "one.log"
                path.write_text(content, encoding="utf-8")
                summary, _, _ = summarize_logs(Path(temporary_directory))
                row = summary.iloc[0]
                self.assertEqual(row["invalid_page_offset_lines"], 0)
                self.assertEqual(row["futurewarning_events"], 0)
                if content.startswith("ERROR:"):
                    self.assertEqual(row["error_prefixed_lines"], 1)
                else:
                    self.assertEqual(row["warning_token_lines"], 1)

    def test_log_summary_rejects_missing_empty_and_invalid_utf8_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing"
            with self.assertRaisesRegex(StabilityGridIntegrityError, "missing log root"):
                summarize_logs(missing)
            with self.assertRaisesRegex(StabilityGridIntegrityError, "no log files"):
                summarize_logs(Path(temporary_directory))
            invalid = Path(temporary_directory) / "invalid.log"
            invalid.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(StabilityGridIntegrityError, "UTF-8"):
                summarize_logs(Path(temporary_directory))

    def test_tiff_header_scan_reads_valid_header_without_affected_slide(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "valid.tiff"
            tifffile.imwrite(path, np.zeros((4, 4), dtype=np.uint8))
            result = scan_nadt_tiff_headers([path])
            self.assertEqual(result["requested_path_count"], 1)
            self.assertEqual(result["scanned_path_count"], 1)
            self.assertEqual(result["scan_failure_count"], 0)
            self.assertTrue(result["scan_complete"])
            self.assertEqual(result["affected_slide_count"], 0)
            self.assertEqual(result["affected_slides"], [])
            self.assertIn("pixel-level impact was not assessed", result["limitation"])

    def test_tiff_header_messages_are_associated_per_path_and_logger_is_restored(self):
        class FakePage:
            shape = (2, 2)
            tags = {}

        class FakeTiffFile:
            def __init__(self, path):
                self.path = Path(path)

            def __enter__(self):
                if self.path.name == "second.tiff":
                    logging.getLogger("tifffile").error("invalid page offset 222")
                self.pages = [FakePage()]
                return self

            def __exit__(self, *_):
                return False

        logger = logging.getLogger("tifffile")
        before = (logger.level, logger.disabled, logger.propagate, list(logger.handlers))
        paths = [Path("second.tiff"), Path("first.tiff"), Path("second.tiff")]
        with patch("models.aggregate_stability_grid.tifffile.TiffFile", FakeTiffFile):
            result = scan_nadt_tiff_headers(paths)
        self.assertEqual(result["requested_path_count"], 2)
        self.assertEqual(result["affected_slide_count"], 1)
        self.assertEqual(result["affected_slides"][0]["path"], "second.tiff")
        self.assertIn("invalid page offset 222", result["affected_slides"][0]["messages"])
        self.assertEqual((logger.level, logger.disabled, logger.propagate, list(logger.handlers)), before)

    def test_tiff_header_scan_reports_missing_path_as_incomplete(self):
        result = scan_nadt_tiff_headers([Path("missing-slide.tiff")])
        self.assertEqual(result["scanned_path_count"], 0)
        self.assertEqual(result["scan_failure_count"], 1)
        self.assertFalse(result["scan_complete"])
        self.assertNotIn("no pixel impact", result["limitation"].lower())
        self.assertNotIn("no pixel effect", result["limitation"].lower())

    def test_tiff_header_scan_deduplicates_and_sorts_requested_paths(self):
        class FakePage:
            shape = (1, 1)
            tags = {}

        calls = []

        class FakeTiffFile:
            def __init__(self, path):
                calls.append(Path(path).as_posix())
                self.pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("models.aggregate_stability_grid.tifffile.TiffFile", FakeTiffFile):
            result = scan_nadt_tiff_headers(
                [Path("b.tiff"), Path("a.tiff"), Path("b.tiff")]
            )
        self.assertEqual(calls, ["a.tiff", "b.tiff"])
        self.assertEqual(result["requested_paths"], ["a.tiff", "b.tiff"])
        self.assertEqual(result["requested_path_count"], 2)
        limitation = result["limitation"].lower()
        self.assertIn("pixel-level impact was not assessed", limitation)
        self.assertNotIn("no pixel impact", limitation)
        self.assertNotIn("no pixel effect", limitation)


class SummaryAndContrastTests(unittest.TestCase):
    """Protect five-seed summaries and paired contrast semantics."""

    def spop_five_seed_cells(self):
        return pd.DataFrame(
            [
                {
                    "marker": "spop",
                    "outcome_type": "binary",
                    "primary_metric": "patient_auroc",
                    "encoder": "CONCH",
                    "sampling_seed": seed,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "patient_metric": metric,
                }
                for seed, metric in enumerate([0.40, 0.45, 0.50, 0.55, 0.60])
            ]
        )

    def spop_paired_cells(self):
        values = {
            ("CONCH", 16, 0.88): 0.40,
            ("CONCH", 16, 1.76): 0.60,
            ("CONCH", 64, 0.88): 0.40,
            ("CONCH", 64, 1.76): 0.50,
            ("Virchow", 16, 0.44): 0.55,
            ("Virchow", 16, 1.76): 0.45,
            ("Virchow", 64, 0.44): 0.55,
            ("Virchow", 64, 1.76): 0.55,
        }
        return pd.DataFrame(
            [
                {
                    "cell_id": (
                        f"spop__{encoder.lower()}__s0__t{tiles}__mpp{target_mpp:.2f}"
                    ),
                    "marker": "spop",
                    "outcome_type": "binary",
                    "primary_metric": "patient_auroc",
                    "encoder": encoder,
                    "sampling_seed": 0,
                    "tiles_per_slide": tiles,
                    "target_mpp": target_mpp,
                    "patient_metric": metric,
                }
                for (encoder, tiles, target_mpp), metric in values.items()
            ]
        )

    def five_seed_cells(self, marker, outcome_type, primary_metric, values):
        return pd.DataFrame(
            [
                {
                    "marker": marker,
                    "outcome_type": outcome_type,
                    "primary_metric": primary_metric,
                    "encoder": "CONCH",
                    "sampling_seed": seed,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "patient_metric": value,
                }
                for seed, value in enumerate(values)
            ]
        )

    def spop_full_five_seed_grid(self):
        one_seed = self.spop_paired_cells()
        tile32 = one_seed.loc[one_seed["tiles_per_slide"].eq(16)].copy()
        tile32["tiles_per_slide"] = 32
        one_seed = pd.concat([one_seed, tile32], ignore_index=True)
        return pd.concat(
            [
                one_seed.assign(
                    sampling_seed=seed,
                    cell_id=lambda frame: frame["cell_id"].str.replace(
                        "__s0__", f"__s{seed}__", regex=False
                    ),
                )
                for seed in range(5)
            ],
            ignore_index=True,
        )

    def test_summary_labels_seed_variability_and_chance_ties(self):
        summary = build_stability_summary(self.spop_five_seed_cells())
        row = summary.iloc[0]
        self.assertAlmostEqual(row["mean"], 0.5)
        self.assertAlmostEqual(row["sample_sd"], 0.07905694150420947)
        self.assertAlmostEqual(row["sampling_seed_t_ci_low"], 0.40183784192612215)
        self.assertAlmostEqual(row["sampling_seed_t_ci_high"], 0.5981621580738778)
        self.assertEqual(row["n_chance_or_worse"], 3)
        self.assertEqual(row["n_ties"], 1)
        self.assertTrue(row["seed_null_straddle"])

    def test_summary_emits_minimum_publication_contract(self):
        summary = build_stability_summary(self.spop_five_seed_cells())
        row = summary.iloc[0]
        self.assertTrue(
            {
                "marker",
                "metric",
                "chance_value",
                "encoder",
                "tiles_per_slide",
                "target_mpp",
                "n_seeds",
                "mean",
                "sample_sd",
                "sampling_seed_t_ci_low",
                "sampling_seed_t_ci_high",
                "min",
                "max",
                "n_chance_or_worse",
                "chance_or_worse_rate",
                "seed_null_straddle",
                "n_ties",
            }.issubset(summary.columns)
        )
        self.assertEqual(row["metric"], "patient_auroc")
        self.assertEqual(row["chance_value"], 0.5)
        self.assertEqual(row["min"], 0.40)
        self.assertEqual(row["max"], 0.60)
        self.assertEqual(row["chance_or_worse_rate"], 0.60)

    def test_contrasts_emit_exact_frozen_pair_families_and_ids(self):
        contrasts = build_stability_contrasts(self.spop_paired_cells())
        self.assertEqual(
            contrasts["contrast"].value_counts().to_dict(),
            {
                "native_vs_1.76": 4,
                "virchow_vs_conch_at_1.76": 2,
                "tile64_vs16": 4,
            },
        )

    def test_contrasts_preserve_raw_endpoint_ids_and_metric_direction(self):
        contrasts = build_stability_contrasts(self.spop_paired_cells()).set_index(
            "pair_id", drop=False
        )
        native = contrasts.loc["native_vs_1.76__spop__conch__s0__t16"]
        self.assertEqual(native["cell_id_a"], "spop__conch__s0__t16__mpp0.88")
        self.assertEqual(native["cell_id_b"], "spop__conch__s0__t16__mpp1.76")
        self.assertEqual(native["metric_direction"], "higher_is_better")
        shared = contrasts.loc["virchow_vs_conch_at_1.76__spop__s0__t16"]
        self.assertEqual(shared["cell_id_a"], "spop__conch__s0__t16__mpp1.76")
        self.assertEqual(shared["cell_id_b"], "spop__virchow__s0__t16__mpp1.76")
        tile = contrasts.loc["tile64_vs16__spop__conch__s0__mpp0.88"]
        self.assertEqual(tile["cell_id_a"], "spop__conch__s0__t16__mpp0.88")
        self.assertEqual(tile["cell_id_b"], "spop__conch__s0__t64__mpp0.88")
        self.assertEqual(
            contrasts["pair_id"].tolist(),
            [
                "native_vs_1.76__spop__conch__s0__t16",
                "native_vs_1.76__spop__conch__s0__t64",
                "native_vs_1.76__spop__virchow__s0__t16",
                "native_vs_1.76__spop__virchow__s0__t64",
                "virchow_vs_conch_at_1.76__spop__s0__t16",
                "virchow_vs_conch_at_1.76__spop__s0__t64",
                "tile64_vs16__spop__conch__s0__mpp0.88",
                "tile64_vs16__spop__conch__s0__mpp1.76",
                "tile64_vs16__spop__virchow__s0__mpp0.44",
                "tile64_vs16__spop__virchow__s0__mpp1.76",
            ],
        )

    def test_native_and_shared_scale_contrasts_preserve_direction_and_null_relations(self):
        contrasts = build_stability_contrasts(self.spop_paired_cells()).set_index("pair_id")
        native = contrasts.loc["native_vs_1.76__spop__conch__s0__t16"]
        self.assertAlmostEqual(native["delta_b_minus_a"], 0.20)
        self.assertEqual(native["relation_a"], "below_null")
        self.assertEqual(native["relation_b"], "above_null")
        self.assertTrue(native["null_crossing"])
        self.assertFalse(native["exact_tie"])
        shared = contrasts.loc["virchow_vs_conch_at_1.76__spop__s0__t16"]
        self.assertAlmostEqual(shared["delta_b_minus_a"], -0.15)
        self.assertEqual(shared["relation_a"], "above_null")
        self.assertEqual(shared["relation_b"], "below_null")
        self.assertTrue(shared["null_crossing"])
        self.assertFalse(shared["exact_tie"])

    def test_tile64_minus16_contrast_records_exact_pair_ties(self):
        contrasts = build_stability_contrasts(self.spop_paired_cells()).set_index("pair_id")
        crossing = contrasts.loc["tile64_vs16__spop__virchow__s0__mpp1.76"]
        self.assertAlmostEqual(crossing["delta_b_minus_a"], 0.10)
        self.assertEqual(crossing["relation_a"], "below_null")
        self.assertEqual(crossing["relation_b"], "above_null")
        self.assertTrue(crossing["null_crossing"])
        self.assertFalse(crossing["exact_tie"])
        tied = contrasts.loc["tile64_vs16__spop__conch__s0__mpp0.88"]
        self.assertAlmostEqual(tied["delta_b_minus_a"], 0.0)
        self.assertEqual(tied["relation_a"], "below_null")
        self.assertEqual(tied["relation_b"], "below_null")
        self.assertFalse(tied["null_crossing"])
        self.assertTrue(tied["exact_tie"])

    def test_both_aggregations_reject_marker_metadata_drift_confined_to_tile32(self):
        cells = self.spop_full_five_seed_grid()
        cells.loc[cells["tiles_per_slide"].eq(32), ["outcome_type", "primary_metric"]] = [
            "survival",
            "patient_c_index",
        ]
        for build in (build_stability_summary, build_stability_contrasts):
            with self.subTest(build=build.__name__):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "marker.*metadata"):
                    build(cells)

    def test_both_aggregations_reject_literal_marker_metric_mapping_drift(self):
        cells = self.spop_full_five_seed_grid()
        cells[["outcome_type", "primary_metric"]] = [
            "continuous",
            "patient_spearman_rho",
        ]
        for build in (build_stability_summary, build_stability_contrasts):
            with self.subTest(build=build.__name__):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "frozen marker metadata"):
                    build(cells)

    def test_summary_uses_c_index_and_spearman_nulls(self):
        cases = (
            (
                "marker7",
                "survival",
                "patient_c_index",
                [0.40, 0.45, 0.50, 0.55, 0.60],
                0.5,
            ),
            (
                "ar",
                "continuous",
                "patient_spearman_rho",
                [-0.20, -0.10, 0.00, 0.10, 0.20],
                0.0,
            ),
        )
        for marker, outcome, metric, values, expected_null in cases:
            with self.subTest(metric=metric):
                row = build_stability_summary(
                    self.five_seed_cells(marker, outcome, metric, values)
                ).iloc[0]
                self.assertEqual(row["null_value"], expected_null)
                self.assertEqual(row["n_chance_or_worse"], 3)
                self.assertEqual(row["n_ties"], 1)
                self.assertTrue(row["seed_null_straddle"])

    def test_contrasts_label_endpoint_at_null_without_strict_crossing(self):
        contrasts = build_stability_contrasts(self.spop_paired_cells()).set_index("pair_id")
        native = contrasts.loc["native_vs_1.76__spop__conch__s0__t64"]
        self.assertEqual(native["relation_a"], "below_null")
        self.assertEqual(native["relation_b"], "at_null")
        self.assertFalse(native["null_crossing"])
        shared = contrasts.loc["virchow_vs_conch_at_1.76__spop__s0__t64"]
        self.assertEqual(shared["relation_a"], "at_null")
        self.assertEqual(shared["relation_b"], "above_null")
        self.assertFalse(shared["null_crossing"])

    def test_contrasts_reject_missing_and_extra_native_endpoints(self):
        base = self.spop_paired_cells()
        missing = base.loc[
            ~(
                base["encoder"].eq("CONCH")
                & base["tiles_per_slide"].eq(16)
                & base["target_mpp"].eq(0.88)
            )
        ].copy()
        extra = pd.concat(
            [
                base,
                base.iloc[[0]].assign(target_mpp=1.32, patient_metric=0.52),
            ],
            ignore_index=True,
        )
        for label, cells in (("missing", missing), ("extra", extra)):
            with self.subTest(label=label):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "native contrast"):
                    build_stability_contrasts(cells)

    def test_contrasts_reject_missing_and_extra_shared_encoder_endpoints(self):
        base = self.spop_paired_cells()
        missing = base.loc[~base["encoder"].eq("Virchow")].copy()
        extra = pd.concat(
            [
                base,
                base.iloc[[1]].assign(encoder="Other", patient_metric=0.52),
            ],
            ignore_index=True,
        )
        for label, cells, message in (
            ("missing", missing, "shared-scale contrast"),
            ("extra", extra, "unsupported encoder"),
        ):
            with self.subTest(label=label):
                with self.assertRaisesRegex(StabilityGridIntegrityError, message):
                    build_stability_contrasts(cells)

    def test_contrasts_reject_missing_and_extra_tile_endpoints(self):
        base = self.spop_paired_cells()
        missing = base.loc[~base["tiles_per_slide"].eq(64)].copy()
        extra_rows = base.loc[base["tiles_per_slide"].eq(16)].assign(
            tiles_per_slide=128, patient_metric=0.52
        )
        extra = pd.concat([base, extra_rows], ignore_index=True)
        for label, cells in (("missing", missing), ("extra", extra)):
            with self.subTest(label=label):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "tile contrast"):
                    build_stability_contrasts(cells)

    def test_contrasts_reject_normalized_duplicate_keys(self):
        base = self.spop_paired_cells()
        duplicate = base.iloc[[0]].assign(target_mpp=0.8801)
        cells = pd.concat([base, duplicate], ignore_index=True)
        with self.assertRaisesRegex(StabilityGridIntegrityError, "duplicate contrast keys"):
            build_stability_contrasts(cells)

    def test_summary_rejects_missing_duplicate_and_extra_seeds(self):
        base = self.spop_five_seed_cells()
        invalid_frames = {
            "missing": base.loc[base["sampling_seed"].ne(4)].copy(),
            "duplicate": base.assign(sampling_seed=[0, 1, 2, 3, 0]),
            "extra": pd.concat(
                [base, base.iloc[[0]].assign(sampling_seed=5)], ignore_index=True
            ),
        }
        for label, cells in invalid_frames.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(StabilityGridIntegrityError, "sampling seeds"):
                    build_stability_summary(cells)

    def test_summary_sort_is_deterministic_after_input_shuffle(self):
        cells = self.spop_full_five_seed_grid().sample(frac=1, random_state=19)
        summary = build_stability_summary(cells)
        self.assertEqual(
            list(
                summary[
                    ["marker", "encoder", "tiles_per_slide", "target_mpp"]
                ].itertuples(index=False, name=None)
            ),
            [
                ("spop", "CONCH", 16, 0.88),
                ("spop", "CONCH", 16, 1.76),
                ("spop", "CONCH", 32, 0.88),
                ("spop", "CONCH", 32, 1.76),
                ("spop", "CONCH", 64, 0.88),
                ("spop", "CONCH", 64, 1.76),
                ("spop", "Virchow", 16, 0.44),
                ("spop", "Virchow", 16, 1.76),
                ("spop", "Virchow", 32, 0.44),
                ("spop", "Virchow", 32, 1.76),
                ("spop", "Virchow", 64, 0.44),
                ("spop", "Virchow", 64, 1.76),
            ],
        )

    def test_aggregations_do_not_mutate_input_or_use_slide_metric(self):
        summary_cells = self.spop_five_seed_cells().assign(
            slide_metric=[0.99, 0.98, 0.97, 0.96, 0.95]
        )
        contrast_cells = self.spop_paired_cells().assign(slide_metric=-999.0)
        summary_original = summary_cells.copy(deep=True)
        contrast_original = contrast_cells.copy(deep=True)
        summary = build_stability_summary(summary_cells)
        contrasts = build_stability_contrasts(contrast_cells).set_index("pair_id")
        pd.testing.assert_frame_equal(summary_cells, summary_original)
        pd.testing.assert_frame_equal(contrast_cells, contrast_original)
        self.assertAlmostEqual(summary.iloc[0]["mean"], 0.5)
        self.assertAlmostEqual(
            contrasts.loc["native_vs_1.76__spop__conch__s0__t16"][
                "delta_b_minus_a"
            ],
            0.20,
        )

    def test_aggregations_emit_no_p_value_columns(self):
        outputs = (
            build_stability_summary(self.spop_five_seed_cells()),
            build_stability_contrasts(self.spop_paired_cells()),
        )
        for output in outputs:
            with self.subTest(columns=list(output.columns)):
                self.assertEqual(
                    [column for column in output.columns if "p_value" in column.lower()], []
                )


class ReconciliationTests(unittest.TestCase):
    """Each test protects one fail-closed reconciliation boundary."""

    def two_cell_fixture(self):
        spec = pd.DataFrame(
            [
                {
                    "cell_id": "pten__conch__s0__t16__mpp0.88",
                    "marker": "pten",
                    "canonical_cohort": "TCGA-PRAD",
                    "outcome_type": "binary",
                    "primary_metric": "patient_auroc",
                    "encoder": "CONCH",
                    "sampling_seed": 0,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "fold_file": "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
                    "status": "pending",
                },
                {
                    "cell_id": "marker7__conch__s0__t16__mpp0.88",
                    "marker": "marker7",
                    "canonical_cohort": "LEOPARD-to-TCGA-PRAD",
                    "outcome_type": "survival",
                    "primary_metric": "patient_c_index",
                    "encoder": "CONCH",
                    "sampling_seed": 0,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "fold_file": "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
                    "status": "pending",
                },
            ]
        )
        assignments = pd.DataFrame(
            [
                {
                    "marker": marker,
                    "canonical_cohort": cohort,
                    "case_id": f"{marker}-{fold}",
                    "fold": fold,
                }
                for marker, cohort in (
                    ("pten", "TCGA-PRAD"),
                    ("marker7", "LEOPARD-to-TCGA-PRAD"),
                )
                for fold in range(5)
            ]
        )
        cells = pd.DataFrame(
            [
                {
                    "cell_id": "pten__conch__s0__t16__mpp0.88",
                    "marker": "pten",
                    "encoder": "CONCH",
                    "sampling_seed": 0,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "n_slides": 300,
                    "n_patients": 273,
                    "slide_metric": 0.61,
                    "patient_metric": 0.62,
                    "status": "complete",
                    "raw_runner_dir": "conch",
                    "raw_cell_results_path": "conch/cell_results.csv",
                    "raw_cell_results_sha256": "cell-sha-conch",
                },
                {
                    "cell_id": "marker7__conch__s0__t16__mpp0.88",
                    "marker": "marker7",
                    "encoder": "CONCH",
                    "sampling_seed": 0,
                    "tiles_per_slide": 16,
                    "target_mpp": 0.88,
                    "n_source_patients": 499,
                    "n_patients": 270,
                    "n_events": 57,
                    "patient_metric": 0.63,
                    "status": "complete",
                    "raw_runner_dir": "marker7_conch",
                    "raw_cell_results_path": "marker7_conch/cell_results.csv",
                    "raw_cell_results_sha256": "cell-sha-marker7",
                },
            ]
        )
        folds = pd.DataFrame(
            [
                {
                    "cell_id": row["cell_id"],
                    "marker": row["marker"],
                    "encoder": row["encoder"],
                    "sampling_seed": row["sampling_seed"],
                    "tiles_per_slide": row["tiles_per_slide"],
                    "target_mpp": row["target_mpp"],
                    "fold": fold,
                    "n_patients": 1,
                    "patient_metric": 0.60 + fold / 100,
                    "raw_runner_dir": row["raw_runner_dir"],
                    "raw_fold_results_path": f"{row['raw_runner_dir']}/fold_results.csv",
                    "raw_fold_results_sha256": f"fold-sha-{row['raw_runner_dir']}",
                }
                for row in cells.to_dict("records")
                for fold in range(5)
            ]
        )
        return spec, assignments, cells, folds

    def full_grid_fixture(self):
        runner_configs = (
            ("conch", ("ar", "pten", "spop"), "CONCH", "TCGA-PRAD", (0.88, 1.76)),
            ("virchow", ("ar", "pten", "spop"), "Virchow", "TCGA-PRAD", (0.44, 1.76)),
            ("nadt_conch", ("gleason", "phenotype"), "CONCH", "NADT-Prostate", (0.88, 1.76)),
            ("nadt_virchow", ("gleason", "phenotype"), "Virchow", "NADT-Prostate", (0.44, 1.76)),
            (
                "marker7_conch", ("marker7",), "CONCH",
                "LEOPARD-to-TCGA-PRAD", (0.88, 1.76),
            ),
            (
                "marker7_virchow", ("marker7",), "Virchow",
                "LEOPARD-to-TCGA-PRAD", (0.44, 1.76),
            ),
        )
        spec_rows = []
        cell_rows = []
        fold_rows = []
        for runner, markers, encoder, cohort, mpps in runner_configs:
            for marker in markers:
                for sampling_seed in range(5):
                    for tiles_per_slide in (16, 32, 64):
                        for target_mpp in mpps:
                            cell_id = (
                                f"{marker}__{encoder.lower()}__s{sampling_seed}"
                                f"__t{tiles_per_slide}__mpp{target_mpp:.2f}"
                            )
                            spec_rows.append(
                                {
                                    "cell_id": cell_id,
                                    "marker": marker,
                                    "canonical_cohort": cohort,
                                    "outcome_type": "survival" if marker == "marker7" else "binary",
                                    "primary_metric": (
                                        "patient_c_index" if marker == "marker7" else "patient_auroc"
                                    ),
                                    "encoder": encoder,
                                    "sampling_seed": sampling_seed,
                                    "tiles_per_slide": tiles_per_slide,
                                    "target_mpp": target_mpp,
                                    "fold_file": "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
                                    "status": "pending",
                                }
                            )
                            cell_row = {
                                "cell_id": cell_id,
                                "marker": marker,
                                "encoder": encoder,
                                "sampling_seed": sampling_seed,
                                "tiles_per_slide": tiles_per_slide,
                                "target_mpp": target_mpp,
                                "n_patients": 5,
                                "patient_metric": 0.62,
                                "status": "complete",
                                "raw_runner_dir": runner,
                                "raw_cell_results_path": f"{runner}/cell_results.csv",
                                "raw_cell_results_sha256": f"cell-sha-{runner}",
                            }
                            if marker == "marker7":
                                cell_row.update(n_source_patients=10, n_events=2)
                            else:
                                cell_row.update(n_slides=6, slide_metric=0.61)
                            cell_rows.append(cell_row)
                            for fold in range(5):
                                fold_rows.append(
                                    {
                                        "cell_id": cell_id,
                                        "marker": marker,
                                        "encoder": encoder,
                                        "sampling_seed": sampling_seed,
                                        "tiles_per_slide": tiles_per_slide,
                                        "target_mpp": target_mpp,
                                        "fold": fold,
                                        "n_patients": 1,
                                        "patient_metric": 0.60 + fold / 100,
                                        "raw_runner_dir": runner,
                                        "raw_fold_results_path": f"{runner}/fold_results.csv",
                                        "raw_fold_results_sha256": f"fold-sha-{runner}",
                                    }
                                )
        assignments = pd.DataFrame(
            [
                {
                    "marker": marker,
                    "canonical_cohort": cohort,
                    "case_id": f"{marker}-{fold}",
                    "fold": fold,
                }
                for marker, cohort in (
                    ("ar", "TCGA-PRAD"),
                    ("pten", "TCGA-PRAD"),
                    ("spop", "TCGA-PRAD"),
                    ("gleason", "NADT-Prostate"),
                    ("phenotype", "NADT-Prostate"),
                    ("marker7", "LEOPARD-to-TCGA-PRAD"),
                )
                for fold in range(5)
            ]
        )
        return (
            pd.DataFrame(spec_rows),
            assignments,
            pd.DataFrame(cell_rows),
            pd.DataFrame(fold_rows),
        )

    def test_reconcile_preserves_structural_missingness_and_spec_status(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        canonical_cells, canonical_folds, qc = reconcile_cells_and_folds(
            spec, assignments, cells, folds, require_full_grid=False
        )
        self.assertEqual(canonical_cells["raw_status"].tolist(), ["complete", "complete"])
        self.assertEqual(canonical_cells["status"].tolist(), ["pending", "pending"])
        self.assertEqual(set(canonical_cells["reconciliation_status"]), {"reconciled"})
        self.assertTrue(pd.isna(canonical_cells.loc[0, "n_source_patients"]))
        self.assertTrue(pd.isna(canonical_cells.loc[1, "n_slides"]))
        self.assertEqual(len(canonical_folds), 10)
        self.assertTrue(canonical_folds["fold_assignment_reconciled"].all())
        self.assertEqual(qc["reconciled_cells"], 2)

    def test_reconcile_rejects_an_incomplete_cell(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells.loc[0, "status"] = "failed"
        with self.assertRaisesRegex(StabilityGridIntegrityError, "complete"):
            reconcile_cells_and_folds(
                spec, assignments, cells, folds, require_full_grid=False
            )

    def test_reconcile_rejects_a_missing_fold(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        folds = folds.iloc[:-1].copy()
        with self.assertRaisesRegex(StabilityGridIntegrityError, "fold"):
            reconcile_cells_and_folds(
                spec, assignments, cells, folds, require_full_grid=False
            )

    def test_reconcile_rejects_duplicate_cell_ids(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells = pd.concat([cells, cells.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(StabilityGridIntegrityError, "duplicate cell"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_missing_cell_ids(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells = cells.iloc[1:].copy()
        with self.assertRaisesRegex(StabilityGridIntegrityError, "cell ID"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_unexpected_cell_ids(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells.loc[1, ["cell_id", "target_mpp"]] = [
            "marker7__conch__s0__t16__mpp1.76",
            1.76,
        ]
        with self.assertRaisesRegex(StabilityGridIntegrityError, "do not exactly match"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_runner_metadata_disagreement(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        spec.loc[0, "canonical_cohort"] = "NADT-Prostate"
        with self.assertRaisesRegex(StabilityGridIntegrityError, "runner metadata"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_spec_result_metadata_disagreement(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        spec.loc[0, "target_mpp"] = 1.76
        with self.assertRaisesRegex(StabilityGridIntegrityError, "spec/result metadata"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_cell_id_not_reconstructed_from_raw_metadata(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells.loc[0, "cell_id"] = "pten__conch__s0__t16__mpp1.76"
        with self.assertRaisesRegex(StabilityGridIntegrityError, "reconstructed"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_nonfinite_cell_metrics(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        cells.loc[0, "patient_metric"] = np.inf
        with self.assertRaisesRegex(StabilityGridIntegrityError, "finite.*cell"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_nonfinite_fold_metrics(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        folds.loc[0, "patient_metric"] = np.nan
        with self.assertRaisesRegex(StabilityGridIntegrityError, "finite.*fold"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_duplicate_fold_keys(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        folds = pd.concat([folds, folds.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(StabilityGridIntegrityError, "duplicate fold"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_duplicate_normalized_fold_keys(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        duplicate = folds.iloc[[0]].copy()
        duplicate["fold"] = "0"
        folds = pd.concat([folds, duplicate], ignore_index=True)
        with self.assertRaisesRegex(StabilityGridIntegrityError, "duplicate fold"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_extra_fold_keys(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        folds.loc[0, "fold"] = 5
        with self.assertRaisesRegex(StabilityGridIntegrityError, "fold"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_rejects_fold_assignment_count_disagreement(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        assignments = assignments.iloc[1:].copy()
        with self.assertRaisesRegex(StabilityGridIntegrityError, "assignment"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=False)

    def test_reconcile_full_grid_rejects_wrong_cardinality(self):
        spec, assignments, cells, folds = self.two_cell_fixture()
        with self.assertRaisesRegex(StabilityGridIntegrityError, "360 cells"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=True)

    def test_reconcile_full_grid_rejects_sampling_seed_axis_drift(self):
        spec, assignments, cells, folds = self.full_grid_fixture()
        old_cell_id = "ar__conch__s0__t16__mpp0.88"
        new_cell_id = "ar__conch__s5__t16__mpp0.88"
        spec_row = spec["cell_id"].eq(old_cell_id)
        cell_row = cells["cell_id"].eq(old_cell_id)
        fold_rows = folds["cell_id"].eq(old_cell_id)
        spec.loc[spec_row, ["cell_id", "sampling_seed"]] = [new_cell_id, 5]
        cells.loc[cell_row, ["cell_id", "sampling_seed"]] = [new_cell_id, 5]
        folds.loc[fold_rows, ["cell_id", "sampling_seed"]] = [new_cell_id, 5]
        with self.assertRaisesRegex(StabilityGridIntegrityError, "sampling-seed axis"):
            reconcile_cells_and_folds(spec, assignments, cells, folds, require_full_grid=True)

    def test_load_standard_runner_rejects_reordered_or_extra_cell_headers(self):
        expected = [
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide",
            "target_mpp", "n_slides", "n_patients", "slide_metric", "patient_metric", "status",
        ]
        for mutated_header in (
            list(reversed(expected)),
            expected + ["unexpected"],
        ):
            with self.subTest(header=mutated_header):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    runner = Path(temporary_directory) / "conch"
                    runner.mkdir()
                    (runner / "cell_results.csv").write_text(
                        ",".join(mutated_header) + "\n", encoding="utf-8"
                    )
                    with self.assertRaisesRegex(StabilityGridIntegrityError, "header"):
                        load_runner_results(runner)

    def test_load_marker7_runner_rejects_reordered_or_extra_cell_headers(self):
        expected = [
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide",
            "target_mpp", "n_source_patients", "n_patients", "n_events",
            "patient_metric", "status",
        ]
        for mutated_header in (list(reversed(expected)), expected + ["unexpected"]):
            with self.subTest(header=mutated_header):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    runner = Path(temporary_directory) / "marker7_conch"
                    runner.mkdir()
                    (runner / "cell_results.csv").write_text(
                        ",".join(mutated_header) + "\n", encoding="utf-8"
                    )
                    with self.assertRaisesRegex(
                        StabilityGridIntegrityError, "marker7_conch cell-results header"
                    ):
                        load_runner_results(runner)

    def test_load_runner_rejects_reordered_or_extra_fold_headers(self):
        cell_header = [
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide",
            "target_mpp", "n_slides", "n_patients", "slide_metric", "patient_metric", "status",
        ]
        expected = [
            "cell_id", "marker", "encoder", "sampling_seed", "tiles_per_slide",
            "target_mpp", "fold", "n_patients", "patient_metric",
        ]
        for mutated_header in (list(reversed(expected)), expected + ["unexpected"]):
            with self.subTest(header=mutated_header):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    runner = Path(temporary_directory) / "conch"
                    runner.mkdir()
                    (runner / "cell_results.csv").write_text(
                        ",".join(cell_header) + "\n", encoding="utf-8"
                    )
                    (runner / "fold_results.csv").write_text(
                        ",".join(mutated_header) + "\n", encoding="utf-8"
                    )
                    with self.assertRaisesRegex(
                        StabilityGridIntegrityError, "conch fold-results header"
                    ):
                        load_runner_results(runner)

    def test_load_spec_rejects_reordered_or_extra_headers(self):
        expected = [
            "cell_id", "marker", "canonical_cohort", "outcome_type", "primary_metric",
            "encoder", "sampling_seed", "tiles_per_slide", "target_mpp", "fold_file", "status",
        ]
        for mutated_header in (list(reversed(expected)), expected + ["unexpected"]):
            with self.subTest(header=mutated_header):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    path = Path(temporary_directory) / "stability_grid.csv"
                    path.write_text(",".join(mutated_header) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(
                        StabilityGridIntegrityError, "stability-grid spec header"
                    ):
                        load_spec(path)

    def test_load_assignments_rejects_reordered_or_extra_headers(self):
        expected = ["marker", "canonical_cohort", "case_id", "fold"]
        for mutated_header in (list(reversed(expected)), expected + ["unexpected"]):
            with self.subTest(header=mutated_header):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    path = Path(temporary_directory) / "stability_fold_assignments.csv"
                    path.write_text(",".join(mutated_header) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(
                        StabilityGridIntegrityError, "stability-fold assignments header"
                    ):
                        load_assignments(path)


if __name__ == "__main__":
    unittest.main()
