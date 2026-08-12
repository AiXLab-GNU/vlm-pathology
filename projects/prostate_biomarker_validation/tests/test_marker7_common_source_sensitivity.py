"""Contract tests for the frozen marker-7 common-source sensitivity audit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "projects/prostate_biomarker_validation/code/legacy/run_marker7_common_source_sensitivity.py"
RUN_ROOT = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full"
HAS_REAL_INPUTS = all(
    path.exists()
    for path in (
        RUN_ROOT / "marker7_conch/source_meta_s0_mpp0.88.csv",
        RUN_ROOT / "marker7_virchow/source_tile_embeddings_s4_mpp1.76.npy",
        ROOT / "projects/prostate_biomarker_validation/outputs/legacy/stability_grid_spec.csv",
        ROOT / "projects/prostate_biomarker_validation/outputs/legacy/stability_fold_assignments.csv",
        ROOT / "projects/prostate_biomarker_validation/outputs/legacy/stability_cell_results.csv",
        ROOT / "projects/prostate_biomarker_validation/outputs/legacy/stability_contrast_summary.csv",
        ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python",
    )
)

if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location("marker7_common", SCRIPT)
    marker7_common = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(marker7_common)
else:
    marker7_common = None


@unittest.skipIf(marker7_common is None, "entry point not implemented yet")
class Marker7CommonUnitTests(unittest.TestCase):
    def make_config_files(self, root: Path, *, rows: int = 3, dim: int = 4):
        """Create the exact 20-config filename universe with small valid shards."""
        source = pd.DataFrame(
            {
                "case_id": [f"source-{index}" for index in range(rows)],
                "event": [0] * (rows - 1) + [1],
                "follow_up_years": np.arange(1, rows + 1, dtype=float),
                "n_tiles": [64] * rows,
                "file_name": [f"source-{index}" for index in range(rows)],
                "path": [f"/source/{index}" for index in range(rows)],
            }
        )
        target = pd.DataFrame(
            {
                "file_name": ["slide-a", "slide-b", "slide-c"],
                "case_id": ["patient-a", "patient-b", "patient-b"],
                "path": ["/target/a", "/target/b", "/target/c"],
                "event": [1, 0, 0],
                "follow_up_y": [1.0, 2.0, 2.0],
            }
        )
        for encoder, mpps, embedding_dim in (
            ("conch", (0.88, 1.76), dim),
            ("virchow", (0.44, 1.76), dim + 1),
        ):
            directory = root / f"marker7_{encoder}"
            directory.mkdir(parents=True)
            for seed in range(5):
                for mpp in mpps:
                    suffix = f"s{seed}_mpp{mpp:.2f}"
                    source.to_csv(directory / f"source_meta_{suffix}.csv", index=False)
                    target.to_csv(directory / f"target_meta_{suffix}.csv", index=False)
                    np.save(
                        directory / f"source_tile_embeddings_{suffix}.npy",
                        np.ones((rows, 64, embedding_dim), dtype=np.float32),
                    )
                    np.save(
                        directory / f"target_tile_embeddings_{suffix}.npy",
                        np.ones((3, 64, embedding_dim), dtype=np.float32),
                    )

    def test_expected_config_and_cell_sets_are_exact(self):
        configs = marker7_common.expected_configs(RUN_ROOT)
        self.assertEqual(len(configs), 20)
        self.assertEqual(
            {config.config_id for config in configs},
            {
                f"{encoder}__s{seed}__mpp{mpp:.2f}"
                for encoder, mpps in (
                    ("conch", (0.88, 1.76)),
                    ("virchow", (0.44, 1.76)),
                )
                for seed in range(5)
                for mpp in mpps
            },
        )
        self.assertEqual(len(marker7_common.expected_cell_ids()), 60)
        self.assertEqual(
            marker7_common.expected_cell_ids(),
            {
                f"marker7__{encoder}__s{seed}__t{tiles}__mpp{mpp:.2f}"
                for encoder, mpps in (
                    ("conch", (0.88, 1.76)),
                    ("virchow", (0.44, 1.76)),
                )
                for seed in range(5)
                for mpp in mpps
                for tiles in (16, 32, 64)
            },
        )

    def test_discovery_requires_exact_complete_20_config_file_set(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_root = Path(temporary_directory)
            self.make_config_files(run_root)
            self.assertEqual(len(marker7_common.discover_configs(run_root)), 20)

            missing = run_root / "marker7_conch/target_meta_s0_mpp0.88.csv"
            missing.unlink()
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "exact config files"):
                marker7_common.discover_configs(run_root)

            pd.DataFrame().to_csv(missing, index=False)
            extra = run_root / "marker7_conch/source_meta_s5_mpp0.88.csv"
            extra.write_text("case_id\n", encoding="utf-8")
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "unexpected source config"):
                marker7_common.discover_configs(run_root)

    def test_schema_alignment_duplicate_missing_and_nonfinite_are_rejected(self):
        mutations = {
            "schema": lambda source, target, array: source.rename(columns={"event": "status"}),
            "duplicate": lambda source, target, array: source.assign(
                case_id=[source.case_id.iloc[0]] * len(source)
            ),
            "missing_outcome": lambda source, target, array: source.assign(
                follow_up_years=[np.nan, *source.follow_up_years.iloc[1:]]
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_root = Path(temporary_directory)
            self.make_config_files(run_root)
            config = marker7_common.discover_configs(run_root)[0]
            marker7_common.validate_config_inputs(config, scan_finite=True)
            pristine = pd.read_csv(config.source_meta)
            target = pd.read_csv(config.target_meta)
            array = np.load(config.source_embeddings)
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    changed = mutate(pristine.copy(), target.copy(), array.copy())
                    changed.to_csv(config.source_meta, index=False)
                    with self.assertRaises(marker7_common.R2IntegrityError):
                        marker7_common.validate_config_inputs(config, scan_finite=True)
                    pristine.to_csv(config.source_meta, index=False)

            np.save(config.source_embeddings, array[:-1])
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "alignment"):
                marker7_common.validate_config_inputs(config, scan_finite=True)
            np.save(config.source_embeddings, array)
            array[0, 0, 0] = np.inf
            np.save(config.source_embeddings, array)
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "non-finite"):
                marker7_common.validate_config_inputs(config, scan_finite=True)

    def test_membership_is_cartesian_and_rejects_outcome_disagreement(self):
        configs = marker7_common.expected_configs(Path("/unused"))
        frames = {}
        for index, config in enumerate(configs):
            ids = ["a", "b", "c", "d"] if index < 8 else ["a", "b", "c"]
            frames[config.config_id] = (
                config,
                pd.DataFrame(
                    {
                        "case_id": ids,
                        "event": [0, 1, 0, 1][: len(ids)],
                        "follow_up_years": [1.0, 2.0, 3.0, 4.0][: len(ids)],
                    }
                ),
            )
        manifest, common_ids, union_ids = marker7_common.build_membership_manifest(
            frames, expected_common=3, expected_union=4, expected_common_events=1
        )
        self.assertEqual(common_ids, ["a", "b", "c"])
        self.assertEqual(union_ids, ["a", "b", "c", "d"])
        self.assertEqual(len(manifest), 80)
        self.assertEqual(int(manifest.retained_in_config.sum()), 68)
        self.assertEqual(int(manifest.common_source_member.sum()), 60)
        self.assertEqual(
            set(manifest.outcome_consistency_status), {"consistent", "not_retained"}
        )

        frames[configs[-1].config_id][1].loc[0, "event"] = 1
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "source outcome"):
            marker7_common.build_membership_manifest(
                frames, expected_common=3, expected_union=4, expected_common_events=1
            )

    def test_common_row_index_matches_row_preserving_worker_filter_order(self):
        configs = marker7_common.expected_configs(Path("/unused"))
        frames = {}
        for index, config in enumerate(configs):
            ids = ["c", "a", "b", "d"] if index < 8 else ["c", "a", "b"]
            frames[config.config_id] = (
                config,
                pd.DataFrame(
                    {
                        "case_id": ids,
                        "event": [0, 1, 0, 1][: len(ids)],
                        "follow_up_years": [1.0, 2.0, 3.0, 4.0][: len(ids)],
                    }
                ),
            )

        manifest, common_ids, _ = marker7_common.build_membership_manifest(
            frames, expected_common=3, expected_union=4, expected_common_events=1
        )

        self.assertEqual(common_ids, ["a", "b", "c"])
        first = manifest.loc[
            manifest.source_configuration_id.eq(configs[0].config_id)
            & manifest.common_source_member
        ].set_index("source_case_id")
        self.assertEqual(first.loc["c", "common_row_index"], 0)
        self.assertEqual(first.loc["a", "common_row_index"], 1)
        self.assertEqual(first.loc["b", "common_row_index"], 2)
        self.assertEqual(
            first.sort_values("common_row_index").index.tolist(), ["c", "a", "b"]
        )

    def test_target_and_fold_validation_rejects_mismatch_and_nonfinite(self):
        configs = marker7_common.expected_configs(Path("/unused"))
        target = pd.DataFrame(
            {
                "file_name": ["slide-a", "slide-b", "slide-c"],
                "case_id": ["patient-a", "patient-b", "patient-b"],
                "path": ["/a", "/b", "/c"],
                "event": [1, 0, 0],
                "follow_up_y": [1.0, 2.0, 2.0],
            }
        )
        targets = {config.config_id: (config, target.copy()) for config in configs}
        folds = pd.DataFrame(
            {
                "marker": ["marker7", "marker7"],
                "canonical_cohort": ["LEOPARD-to-TCGA-PRAD"] * 2,
                "case_id": ["patient-a", "patient-b"],
                "fold": [0, 1],
            }
        )
        result = marker7_common.validate_target_and_folds(
            targets,
            folds,
            expected_slides=3,
            expected_patients=2,
            expected_events=1,
            expected_patient_hash=marker7_common.id_list_sha256(["patient-a", "patient-b"]),
            expected_slide_case_hash=marker7_common.ordered_slide_case_sha256(target),
            require_all_five_folds=False,
        )
        self.assertEqual(result["n_target_patients"], 2)
        self.assertEqual(result["n_target_slides"], 3)

        duplicate_slide = target.copy()
        duplicate_slide.loc[2, "file_name"] = duplicate_slide.loc[1, "file_name"]
        duplicate_targets = {
            config.config_id: (config, duplicate_slide.copy()) for config in configs
        }
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "target file_name"):
            marker7_common.validate_target_and_folds(
                duplicate_targets,
                folds,
                expected_slides=3,
                expected_patients=2,
                expected_events=1,
                expected_patient_hash=marker7_common.id_list_sha256(["patient-a", "patient-b"]),
                expected_slide_case_hash=marker7_common.ordered_slide_case_sha256(target),
                require_all_five_folds=False,
            )

        targets[configs[-1].config_id][1].loc[0, "follow_up_y"] = np.inf
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "non-finite"):
            marker7_common.validate_target_and_folds(
                targets,
                folds,
                expected_slides=3,
                expected_patients=2,
                expected_events=1,
                expected_patient_hash=marker7_common.id_list_sha256(["patient-a", "patient-b"]),
                expected_slide_case_hash=marker7_common.ordered_slide_case_sha256(target),
                require_all_five_folds=False,
            )
        targets[configs[-1].config_id][1].loc[0, "follow_up_y"] = 9.0
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "target outcome"):
            marker7_common.validate_target_and_folds(
                targets,
                folds,
                expected_slides=3,
                expected_patients=2,
                expected_events=1,
                expected_patient_hash=marker7_common.id_list_sha256(["patient-a", "patient-b"]),
                expected_slide_case_hash=marker7_common.ordered_slide_case_sha256(target),
                require_all_five_folds=False,
            )

    def test_r1_manifest_binds_frozen_config_input_hashes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/source_meta_s0_mpp0.88.csv"
            source.parent.mkdir(parents=True)
            source.write_text("case_id\na\n", encoding="utf-8")
            snapshots = marker7_common.snapshot_paths([source], root)
            digest = next(iter(snapshots.values()))["sha256"]
            manifest = pd.DataFrame(
                [{
                    "artifact_kind": "input",
                    "artifact_path": "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/source_meta_s0_mpp0.88.csv",
                    "sha256_before": digest,
                    "sha256_after": digest,
                    "hash_reconciled": True,
                }]
            )
            marker7_common.validate_r1_config_lineage(snapshots, manifest)
            manifest.loc[0, "sha256_after"] = "0" * 64
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "R1 lineage"):
                marker7_common.validate_r1_config_lineage(snapshots, manifest)

            embedding = root / "resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/full/marker7_conch/source_tile_embeddings_s0_mpp0.88.npy"
            np.save(embedding, np.ones((1, 1, 1), dtype=np.float32))
            embedding_snapshot = marker7_common.snapshot_paths([embedding], root)
            digest = marker7_common.configuration_embedding_lineage_sha256(
                embedding_snapshot, expected_count=1
            )
            changed = {path: dict(value) for path, value in embedding_snapshot.items()}
            next(iter(changed.values()))["sha256"] = "0" * 64
            self.assertNotEqual(
                digest,
                marker7_common.configuration_embedding_lineage_sha256(
                    changed, expected_count=1
                ),
            )

    def test_original_reproduction_uses_absolute_1e_minus_15_gate(self):
        rows = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "raw_reproduction_error_vs_saved": [0.0, 5.55e-17],
                "raw_reproduction_error_vs_integrated": [0.0, 5.55e-17],
            }
        )
        marker7_common.validate_reproduction(rows, atol=1e-15)
        rows.loc[1, "raw_reproduction_error_vs_integrated"] = 1.01e-15
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "reproduction tolerance"):
            marker7_common.validate_reproduction(rows, atol=1e-15)

    def test_paired_delta_arithmetic_direction_and_r1_order(self):
        cells = pd.DataFrame(
            [
                {
                    "cell_id": "a",
                    "saved_raw_c_index": 0.6,
                    "common_source_c_index": 0.7,
                },
                {
                    "cell_id": "b",
                    "saved_raw_c_index": 0.8,
                    "common_source_c_index": 0.75,
                },
                {
                    "cell_id": "c",
                    "saved_raw_c_index": 0.55,
                    "common_source_c_index": 0.9,
                },
            ]
        )
        contrasts = pd.DataFrame(
            [
                {
                    "contrast": "native_vs_1.76",
                    "pair_id": "pair-1",
                    "cell_id_a": "a",
                    "cell_id_b": "b",
                    "marker": "marker7",
                    "sampling_seed": 0,
                    "encoder_a": "CONCH",
                    "encoder_b": "CONCH",
                    "tiles_per_slide_a": 16,
                    "tiles_per_slide_b": 16,
                    "target_mpp_a": 0.88,
                    "target_mpp_b": 1.76,
                    "delta_b_minus_a": 0.2,
                },
                {
                    "contrast": "tile64_vs16",
                    "pair_id": "pair-2",
                    "cell_id_a": "a",
                    "cell_id_b": "c",
                    "marker": "marker7",
                    "sampling_seed": 0,
                    "encoder_a": "CONCH",
                    "encoder_b": "CONCH",
                    "tiles_per_slide_a": 16,
                    "tiles_per_slide_b": 64,
                    "target_mpp_a": 0.88,
                    "target_mpp_b": 0.88,
                    "delta_b_minus_a": -0.05,
                },
            ]
        )
        result = marker7_common.build_paired_deltas(cells, contrasts, require_full=False)
        self.assertEqual(result.pair_id.tolist(), ["pair-1", "pair-2"])
        self.assertAlmostEqual(result.iloc[0].raw_delta_b_minus_a, 0.2)
        self.assertAlmostEqual(result.iloc[0].common498_delta_b_minus_a, 0.05)
        self.assertAlmostEqual(result.iloc[0].common_source_adjustment, -0.15)
        self.assertEqual(result.iloc[0].direction_status, "preserved")
        self.assertEqual(result.iloc[1].raw_direction, "negative")
        self.assertEqual(result.iloc[1].common498_direction, "positive")
        self.assertEqual(result.iloc[1].direction_status, "reversed")
        self.assertFalse(any("p_value" in column for column in result.columns))

    def test_hash_snapshot_detects_pre_post_mutation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "immutable.csv"
            path.write_text("a\n1\n", encoding="utf-8")
            before = marker7_common.snapshot_paths([path], Path(temporary_directory))
            marker7_common.assert_snapshots_unchanged(
                before,
                marker7_common.snapshot_paths([path], Path(temporary_directory)),
            )
            path.write_text("a\n2\n", encoding="utf-8")
            with self.assertRaisesRegex(marker7_common.R2IntegrityError, "input changed"):
                marker7_common.assert_snapshots_unchanged(
                    before,
                    marker7_common.snapshot_paths([path], Path(temporary_directory)),
                )

    def test_manifest_excludes_self_and_isolates_volatile_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.csv"
            output = root / "cells.csv"
            source.write_text("x\n1\n", encoding="utf-8")
            output.write_text("x\n2\n", encoding="utf-8")
            snapshots = marker7_common.snapshot_paths([source], root)
            manifest = marker7_common.build_run_manifest(
                root=root,
                input_before=snapshots,
                input_after=snapshots,
                input_roles={source: "source_meta"},
                output_paths=[output],
                manifest_path=root / marker7_common.MANIFEST_NAME,
                controller_probe={"python": "3.11.2"},
                worker_probe={"python": "3.11.2"},
                generated_at_utc="2026-08-06T12:00:00Z",
                elapsed_seconds=1.25,
            )
            self_row = manifest.loc[manifest.artifact_path.eq(marker7_common.MANIFEST_NAME)].iloc[0]
            self.assertEqual(self_row.sha256_after, "")
            self.assertFalse(bool(self_row.included_in_output_hashes))
            self.assertEqual(self_row.hash_exclusion_reason, "self_referential_manifest")
            self.assertEqual(self_row.generated_at_utc, "2026-08-06T12:00:00Z")
            self.assertEqual(float(self_row.elapsed_seconds), 1.25)
            other = manifest.loc[manifest.index != self_row.name]
            self.assertTrue((other.generated_at_utc == "").all())
            self.assertTrue((other.elapsed_seconds == "").all())

    def test_worker_probe_is_fail_closed_on_path_or_version(self):
        expected = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python"
        probe = {
            "executable": str(expected),
            "python": "3.11.2",
            "numpy": "2.4.6",
            "pandas": "2.3.3",
            "scipy": "1.17.1",
            "sklearn": "1.9.0",
            "sksurv": "0.28.0",
        }
        marker7_common.validate_worker_probe(probe, expected)
        for key, value in (("pandas", "3.0.3"), ("executable", "/usr/bin/python")):
            broken = {**probe, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(
                marker7_common.R2IntegrityError, "worker"
            ):
                marker7_common.validate_worker_probe(broken, expected)

        same_binary_wrong_venv = {**probe, "executable": str(ROOT / ".venv/bin/python")}
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "worker executable"):
            marker7_common.validate_worker_probe(same_binary_wrong_venv, expected)

    def test_controller_probe_requires_exact_workspace_venv_path(self):
        expected = ROOT / ".venv/bin/python"
        probe = marker7_common.controller_probe()
        marker7_common.validate_controller_probe(probe, expected)
        wrong = {**probe, "executable": str(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python")}
        with self.assertRaisesRegex(marker7_common.R2IntegrityError, "controller executable"):
            marker7_common.validate_controller_probe(wrong, expected)

    def test_worker_invocation_uses_only_pinned_interpreter_and_explicit_mode(self):
        expected = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python"
        with tempfile.TemporaryDirectory() as temporary_directory:
            job = Path(temporary_directory) / "job.json"
            output = Path(temporary_directory) / "worker.json"
            job.write_text("{}\n", encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

            def completed_worker(*_args, **_kwargs):
                output.write_text("{}\n", encoding="utf-8")
                return completed

            with patch.object(marker7_common.subprocess, "run", side_effect=completed_worker) as run:
                marker7_common.invoke_worker(job, output, expected)
            command = run.call_args.args[0]
            self.assertEqual(Path(command[0]), expected)
            self.assertEqual(Path(command[1]), SCRIPT)
            self.assertIn("--worker", command)
            self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])
            self.assertEqual(run.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], "")
            with patch.object(marker7_common.subprocess, "run") as wrong_run:
                with self.assertRaisesRegex(marker7_common.R2IntegrityError, "pinned worker"):
                    marker7_common.invoke_worker(job, output, ROOT / ".venv/bin/python")
                wrong_run.assert_not_called()

    def test_publication_failure_rolls_back_the_complete_existing_output_set(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stage = root / "stage"
            output = root / "output"
            stage.mkdir()
            output.mkdir()
            names = ("a.csv", "b.csv", "c.csv")
            staged = {}
            for name in names:
                staged[name] = stage / name
                staged[name].write_text(f"new-{name}\n", encoding="utf-8")
                (output / name).write_text(f"old-{name}\n", encoding="utf-8")

            original_replace = marker7_common.os.replace
            failed = False

            def fail_second_install(source, destination):
                nonlocal failed
                source = Path(source)
                destination = Path(destination)
                if not failed and source.parent == stage and source.name == "b.csv":
                    failed = True
                    raise OSError("injected publication failure")
                return original_replace(source, destination)

            with patch.object(marker7_common.os, "replace", side_effect=fail_second_install):
                with self.assertRaisesRegex(marker7_common.R2IntegrityError, "publication failed"):
                    marker7_common.publish_output_set(staged, output, names)

            for name in names:
                self.assertEqual((output / name).read_text(encoding="utf-8"), f"old-{name}\n")


@unittest.skipIf(marker7_common is None or not HAS_REAL_INPUTS, "real frozen inputs absent")
class Marker7CommonRealIntegrationTests(unittest.TestCase):
    def test_real_input_contract_and_audited_hashes(self):
        audit = marker7_common.audit_inputs(
            root=ROOT,
            run_root=RUN_ROOT,
            spec_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv",
            fold_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
            integrated_cells_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv",
            contrasts_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
            scan_embeddings=True,
        )
        self.assertEqual(len(audit.configs), 20)
        self.assertEqual(len(audit.membership), 10_040)
        self.assertEqual(int(audit.membership.retained_in_config.sum()), 9_992)
        self.assertEqual(int(audit.membership.common_source_member.sum()), 9_960)
        self.assertEqual(len(audit.common_ids), 498)
        self.assertEqual(len(audit.union_ids), 502)
        self.assertEqual(
            marker7_common.id_list_sha256(audit.common_ids),
            "3bf830ff8e7cdc0701c026a4d1425207661ce78e56812f532a5763e4b6eef32a",
        )
        self.assertEqual(
            marker7_common.id_list_sha256(audit.union_ids),
            "d1f366c5cbb682454711ab25743cf8470dc0c17666a737f82bf8a8ac295b43b6",
        )
        self.assertEqual(audit.target_summary["n_target_slides"], 297)
        self.assertEqual(audit.target_summary["n_target_patients"], 270)
        self.assertEqual(audit.target_summary["n_target_events"], 57)
        self.assertEqual(
            audit.target_summary["target_patient_id_sha256"],
            "0a762215700364d916425cee8cd7e977309ea3ff829f1eb49ea9aed7d1c91267",
        )
        self.assertEqual(
            audit.target_summary["target_slide_case_order_sha256"],
            "85626cb673bbbb5e36ee7c8765b2cfca99acf1d4a2c97c15733bd75d4329b72f",
        )
        self.assertEqual(len(audit.integrated_cells), 60)
        self.assertEqual(len(audit.contrasts), 65)

    def test_r1_contrast_and_r2_output_semantics_fail_closed(self):
        audit = marker7_common.audit_inputs(
            root=ROOT,
            run_root=RUN_ROOT,
            spec_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv",
            fold_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
            integrated_cells_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv",
            contrasts_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
            scan_embeddings=False,
        )
        for column, value in (("sampling_seed", 99), ("sampling_seed", 0.5),
                              ("tiles_per_slide_a", 16.5)):
            bad_contrasts = audit.contrasts.copy()
            bad_contrasts[column] = bad_contrasts[column].astype(float)
            bad_contrasts.loc[0, column] = value
            with self.subTest(r1_column=column, r1_value=value), self.assertRaisesRegex(
                marker7_common.R2IntegrityError, "contrast metadata"
            ):
                marker7_common._validate_contrasts(bad_contrasts)

        cells = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace" / marker7_common.CELLS_NAME)
        deltas = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace" / marker7_common.DELTAS_NAME)
        membership = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace" / marker7_common.MEMBERSHIP_NAME)
        marker7_common._validate_outputs(cells, deltas, membership, audit.contrasts)

        mutations = []
        bad_cells = cells.copy(); bad_cells.loc[0, "encoder"] = "BROKEN"
        mutations.append((bad_cells, deltas, membership, "cell semantics"))
        bad_cells = cells.copy(); bad_cells["sampling_seed"] = bad_cells["sampling_seed"].astype(float)
        bad_cells.loc[0, "sampling_seed"] = 0.5
        mutations.append((bad_cells, deltas, membership, "fractional cell axis"))
        bad_cells = cells.copy(); bad_cells.loc[0, "common_minus_saved_raw"] = 999.0
        mutations.append((bad_cells, deltas, membership, "cell arithmetic"))
        bad_deltas = deltas.copy(); bad_deltas.loc[0, "common498_delta_b_minus_a"] = 999.0
        mutations.append((cells, bad_deltas, membership, "delta arithmetic"))
        bad_deltas = deltas.copy()
        bad_deltas["tiles_per_slide_a"] = bad_deltas["tiles_per_slide_a"].astype(float)
        bad_deltas.loc[0, "tiles_per_slide_a"] = 16.5
        mutations.append((cells, bad_deltas, membership, "fractional delta axis"))
        bad_membership = membership.copy()
        bad_membership.loc[bad_membership.common_source_member, "common_row_index"] = 0
        mutations.append((cells, deltas, bad_membership, "membership"))
        for changed_cells, changed_deltas, changed_membership, label in mutations:
            with self.subTest(label=label), self.assertRaises(marker7_common.R2IntegrityError):
                marker7_common._validate_outputs(
                    changed_cells, changed_deltas, changed_membership, audit.contrasts
                )

    def test_staged_readback_rejects_corrupted_csv(self):
        audit = marker7_common.audit_inputs(
            root=ROOT,
            run_root=RUN_ROOT,
            spec_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_grid_spec.csv",
            fold_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_fold_assignments.csv",
            integrated_cells_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_cell_results.csv",
            contrasts_path=ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_contrast_summary.csv",
            scan_embeddings=False,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            stage = Path(temporary_directory)
            staged = {}
            for name in (
                marker7_common.CELLS_NAME, marker7_common.DELTAS_NAME,
                marker7_common.MEMBERSHIP_NAME, marker7_common.CONFIG_NAME,
                marker7_common.MANIFEST_NAME,
            ):
                source = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace" / name
                destination = stage / name
                destination.write_bytes(source.read_bytes())
                staged[name] = destination
            expected_config = json.loads(staged[marker7_common.CONFIG_NAME].read_text())
            cells = pd.read_csv(staged[marker7_common.CELLS_NAME])
            cells.loc[0, "n_target_folds"] = 99
            cells.to_csv(staged[marker7_common.CELLS_NAME], index=False)
            with self.assertRaises(marker7_common.R2IntegrityError):
                marker7_common.validate_staged_artifacts(staged, audit, expected_config)

    def test_real_clean_rerun_is_deterministic_except_documented_volatile_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            first_dir, second_dir = temporary_root / "first", temporary_root / "second"
            marker7_common.run_analysis(root=ROOT, output_dir=first_dir)
            marker7_common.run_analysis(root=ROOT, output_dir=second_dir)
            deterministic = {
                marker7_common.CELLS_NAME,
                marker7_common.DELTAS_NAME,
                marker7_common.MEMBERSHIP_NAME,
                marker7_common.CONFIG_NAME,
            }
            for name in deterministic:
                self.assertEqual((first_dir / name).read_bytes(), (second_dir / name).read_bytes(), name)
            first_manifest = pd.read_csv(
                first_dir / marker7_common.MANIFEST_NAME, dtype=str, keep_default_na=False
            )
            second_manifest = pd.read_csv(
                second_dir / marker7_common.MANIFEST_NAME, dtype=str, keep_default_na=False
            )
            pd.testing.assert_frame_equal(
                marker7_common.normalize_manifest_for_comparison(first_manifest),
                marker7_common.normalize_manifest_for_comparison(second_manifest),
            )


class Marker7CommonRedGateTests(unittest.TestCase):
    def test_required_entry_point_exists(self):
        self.assertTrue(
            SCRIPT.exists(),
            "R2 RED: resources/projects/prostate_biomarker_validation/model_workspace/run_marker7_common_source_sensitivity.py is not implemented",
        )


if __name__ == "__main__":
    unittest.main()
