"""Contract tests for the R4 common-cohort paired survival analysis."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "models/build_marker7_survival_paired_analysis.py"


def _load_module():
    if not SCRIPT.exists():
        return None
    spec = importlib.util.spec_from_file_location("marker7_survival_paired", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


r4 = _load_module()


def _sample_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ids = [f"TCGA-AA-{index:04d}" for index in range(10)]
    event = [1, 0, 0, 1, 0, 1, 0, 0, 1, 0]
    time = [1.0, 2.0, 3.0, 1.5, 4.0, 2.5, 5.0, 6.0, 3.5, 7.0]
    nested = pd.DataFrame(
        {
            "case_id": ids,
            "marker": "marker7_recurrence",
            "analysis": "fully_adjusted",
            "scope": "patient",
            "fold": [4, 3, 2, 1, 0, 4, 3, 2, 1, 0],
            "gleason_sum": [6, 7, 7, 8, 7, 9, 6, 7, 8, 7],
            "marker7_risk": np.linspace(-1.0, 1.0, 10),
            "event": event,
            "follow_up_y": time,
            "age": np.arange(60, 70),
            "t_stage": [2, 2, 3, 3, 2, 4, 2, 3, 3, 2],
            "psa": np.arange(2.0, 12.0),
            "margin_positive": [0, 0, 0, 1, 0, 1, 0, 0, 1, 0],
        }
    )
    hierarchy = pd.concat(
        [
            pd.DataFrame(
                {
                    "case_id": ids,
                    "event": event,
                    "follow_up_y": time,
                    "model": model,
                    "fold": nested["fold"],
                    "prediction": np.linspace(0.0, 1.0, 10),
                }
            )
            for model in ("M3", "M4", "M5")
        ],
        ignore_index=True,
    )
    frozen = pd.DataFrame(
        {
            "marker": "marker7",
            "canonical_cohort": "LEOPARD-to-TCGA-PRAD",
            "case_id": ids,
            "fold": np.repeat(np.arange(5), 2),
        }
    )
    endpoint = pd.DataFrame({"case_id": ids, "event": event, "follow_up_y": time})
    return nested, hierarchy, frozen, endpoint


class Marker7SurvivalPairedContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(r4, "R4 entry point has not been implemented")

    def test_registry_preserves_both_legacy_model_engines(self):
        registry = r4.model_registry()
        self.assertEqual(len(registry), 11)
        self.assertEqual(
            [item.model_id for item in registry[:5]],
            [
                "N_IMAGE",
                "N_GRADE_CLINICAL",
                "N_GRADE_COMBINED",
                "N_FULL_CLINICAL",
                "N_FULL_COMBINED",
            ],
        )
        self.assertTrue(all(item.engine == "lifelines_unpenalized" for item in registry[:5]))
        self.assertEqual([item.model_id for item in registry[5:]], [f"H_M{i}" for i in range(6)])
        self.assertTrue(all(item.engine == "sksurv_coxph_alpha_1" for item in registry[5:]))
        self.assertEqual(registry[7].covariates, ("gleason_sum", "psa", "t_stage"))
        self.assertEqual(registry[-1].covariates[-2:], ("site", "marker7_risk"))

    def test_time_grid_is_exact_half_to_five_years_by_tenth(self):
        np.testing.assert_array_equal(r4.time_grid(), np.arange(5, 51, dtype=float) / 10.0)

    def test_common_cohort_uses_canonical_fold_not_legacy_subset_fold(self):
        nested, hierarchy, frozen, endpoint = _sample_inputs()
        common, diagnostics = r4.reconcile_common_cohort(
            nested,
            hierarchy,
            frozen,
            endpoint,
            expected_n=10,
            expected_events=4,
        )
        self.assertEqual(common["case_id"].tolist(), sorted(common["case_id"]))
        self.assertEqual(common["fold"].tolist(), frozen.sort_values("case_id")["fold"].tolist())
        self.assertEqual(diagnostics["legacy_fold_agreement_n"], 2)
        self.assertEqual(common["site"].unique().tolist(), ["AA"])

    def test_common_cohort_rejects_patient_or_endpoint_mismatch(self):
        nested, hierarchy, frozen, endpoint = _sample_inputs()
        hierarchy = hierarchy.loc[~((hierarchy["model"] == "M5") & (hierarchy["case_id"] == "TCGA-AA-0009"))]
        with self.assertRaisesRegex(r4.R4IntegrityError, "M3.*M4.*M5|patient set"):
            r4.reconcile_common_cohort(
                nested, hierarchy, frozen, endpoint, expected_n=10, expected_events=4
            )

        nested, hierarchy, frozen, endpoint = _sample_inputs()
        endpoint.loc[0, "event"] = 0
        with self.assertRaisesRegex(r4.R4IntegrityError, "endpoint"):
            r4.reconcile_common_cohort(
                nested, hierarchy, frozen, endpoint, expected_n=10, expected_events=4
            )

    def test_endpoint_normalization_keeps_reconstructed_and_pfi_namespaces_separate(self):
        common, _, _, _ = _sample_inputs()
        common = common[["case_id"]].copy()
        source = pd.DataFrame(
            {
                "case_id": common["case_id"],
                "pfi_event": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
                "pfi_time_years": np.arange(1.0, 11.0),
            }
        )
        out = r4.normalize_endpoint(
            common,
            source,
            endpoint_id="E08_official_pfi",
            event_col="pfi_event",
            time_col="pfi_time_years",
            expected_events=2,
        )
        self.assertEqual(set(out["endpoint_id"]), {"E08_official_pfi"})
        self.assertEqual(int(out["event"].sum()), 2)
        self.assertNotIn("follow_up_y", out.columns)

    def test_official_pfi_inputs_use_namespaced_r3_manifest(self):
        predictions, manifest = r4.official_pfi_input_paths(ROOT)
        self.assertEqual(predictions, ROOT / "models/tcga_cdr_pfi_patient_predictions.csv")
        self.assertEqual(manifest, ROOT / "models/tcga_cdr_pfi_run_manifest.csv")
        self.assertNotEqual(manifest.name, "run_manifest.csv")

    def test_ipcw_uses_left_limit_for_event_and_exact_time_for_at_risk(self):
        # Training censoring KM: at t=1, one disease event leaves the risk set before one
        # censoring, so G(1)=2/3 while G(1-)=1.
        train_event = np.array([0, 1, 1, 1, 1, 1], dtype=bool)
        train_time = np.array([1.0, 1.0, 2.0, 3.0, 0.5, 0.5])
        test_event = np.array([1, 0], dtype=bool)
        test_time = np.array([1.0, 2.0])
        survival = np.full((2, 1), 0.5)
        contribution, diagnostics = r4.ipcw_brier_contributions(
            train_event, train_time, test_event, test_time, survival, np.array([1.0])
        )
        np.testing.assert_allclose(contribution[:, 0], [0.25, 0.375], rtol=0, atol=1e-12)
        self.assertAlmostEqual(diagnostics["g_at_grid_min"], 2.0 / 3.0)

    def test_survival_validation_rejects_nonfinite_range_and_increase(self):
        valid = np.array([[0.9, 0.8, 0.8], [1.0, 0.7, 0.2]])
        r4.validate_survival_probabilities(valid)
        for invalid in (
            np.array([[0.9, np.nan, 0.8]]),
            np.array([[0.9, 1.1, 0.8]]),
            np.array([[0.9, 0.8, 0.85]]),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(r4.R4IntegrityError):
                    r4.validate_survival_probabilities(invalid)

    def test_bootstrap_draws_are_deterministic_and_retain_every_id(self):
        case_ids = np.array([f"p{i}" for i in range(6)])
        first, first_meta = r4.make_bootstrap_draws(case_ids, n_boot=4, seed=0)
        second, second_meta = r4.make_bootstrap_draws(case_ids, n_boot=4, seed=0)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first.shape, (4, 6))
        self.assertEqual(first_meta["replicate_id"].tolist(), [0, 1, 2, 3])
        self.assertEqual(first_meta["sample_index_sha256"].tolist(), second_meta["sample_index_sha256"].tolist())
        expected_hash = hashlib.sha256(first[0].astype("<i8").tobytes()).hexdigest()
        self.assertEqual(first_meta.loc[0, "sample_index_sha256"], expected_hash)

    def test_bootstrap_metrics_keep_undefined_draws_without_reindexing(self):
        patients = pd.DataFrame(
            {
                "case_id": ["a", "b", "c"],
                "event": [0, 0, 1],
                "time_years": [2.0, 3.0, 1.0],
                "model_id": "N_IMAGE",
                "linear_predictor": [0.1, 0.2, 0.3],
                "ibs_contribution": [0.1, 0.2, 0.3],
            }
        )
        draws = np.array([[0, 1, 0], [0, 1, 2]], dtype=np.int64)
        metadata = pd.DataFrame(
            {
                "replicate_id": [0, 1],
                "sample_index_sha256": ["x", "y"],
                "n_sampled_patients": [3, 3],
                "n_unique_patients": [2, 3],
            }
        )
        out = r4.bootstrap_model_metrics(
            patients, draws, metadata, endpoint_id="E04_reconstructed"
        )
        c_rows = out[out["metric"] == "c_index"].sort_values("replicate_id")
        self.assertEqual(c_rows["replicate_id"].tolist(), [0, 1])
        self.assertFalse(bool(c_rows.iloc[0]["valid"]))
        self.assertEqual(c_rows.iloc[0]["failure_reason"], "no_comparable_pairs")
        self.assertTrue(pd.isna(c_rows.iloc[0]["estimate"]))
        self.assertTrue(bool(c_rows.iloc[1]["valid"]))

    def test_paired_delta_sign_and_draw_identity_are_enforced(self):
        rows = []
        for replicate, draw_hash, a_c, b_c, a_i, b_i in (
            (0, "h0", 0.60, 0.65, 0.20, 0.18),
            (1, "h1", 0.55, 0.50, 0.19, 0.21),
        ):
            for model, c_value, i_value in (("A", a_c, a_i), ("B", b_c, b_i)):
                rows.extend(
                    [
                        {"endpoint_id": "E04", "replicate_id": replicate, "sample_index_sha256": draw_hash,
                         "model_id": model, "metric": "c_index", "estimate": c_value, "valid": True,
                         "failure_reason": "", "n_sampled_patients": 3,
                         "n_unique_patients": 3, "n_events": 1},
                        {"endpoint_id": "E04", "replicate_id": replicate, "sample_index_sha256": draw_hash,
                         "model_id": model, "metric": "ibs_0.5_5y", "estimate": i_value, "valid": True,
                         "failure_reason": "", "n_sampled_patients": 3,
                         "n_unique_patients": 3, "n_events": 1},
                    ]
                )
        replicates = pd.DataFrame(rows)
        contrast = r4.paired_replicate_deltas(replicates, "A", "B", "A_to_B")
        c = contrast[contrast["metric"] == "c_index"].sort_values("replicate_id")
        ibs = contrast[contrast["metric"] == "ibs_0.5_5y"].sort_values("replicate_id")
        np.testing.assert_allclose(c["improvement_delta"], [0.05, -0.05], atol=1e-12)
        np.testing.assert_allclose(ibs["improvement_delta"], [0.02, -0.02], atol=1e-12)

        broken = replicates.copy()
        broken.loc[(broken.model_id == "B") & (broken.replicate_id == 1), "sample_index_sha256"] = "wrong"
        with self.assertRaisesRegex(r4.R4IntegrityError, "draw"):
            r4.paired_replicate_deltas(broken, "A", "B", "A_to_B")

    def test_manifest_excludes_its_own_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = directory / "input.csv"
            output_path = directory / "output.csv"
            manifest_path = directory / "manifest.csv"
            input_path.write_text("x\n1\n", encoding="utf-8")
            output_path.write_text("y\n2\n", encoding="utf-8")
            before = r4.snapshot_paths([input_path], directory)
            after = r4.snapshot_paths([input_path], directory)
            manifest = r4.build_run_manifest(
                root=directory,
                input_before=before,
                input_after=after,
                input_roles={input_path.resolve(): "fixture"},
                output_paths=[output_path],
                manifest_path=manifest_path,
                software={"python": "fixture"},
                generated_at_utc="2026-08-06T00:00:00Z",
                elapsed_seconds=1.0,
            )
            self_row = manifest[manifest["artifact_kind"] == "manifest"].iloc[0]
            self.assertEqual(self_row["sha256_after"], "")
            self.assertEqual(self_row["hash_exclusion_reason"], "self_referential_manifest")

    def test_run_snapshots_exact_inputs_before_reading_any_analytical_csv(self):
        class StopAfterFirstCsvRead(RuntimeError):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            pfi_path = models / "tcga_cdr_pfi_patient_predictions.csv"
            pfi_manifest = models / "tcga_cdr_pfi_run_manifest.csv"
            pfi_path.write_text("case_id\nfixture\n", encoding="utf-8")
            pfi_manifest.write_text("artifact_kind\nfixture\n", encoding="utf-8")
            events: list[tuple[str, tuple[str, ...] | None]] = []

            def fake_snapshot(paths, snapshot_root):
                self.assertEqual(Path(snapshot_root), root)
                names = tuple(Path(path).name for path in paths)
                events.append(("snapshot", names))
                return {}

            def fake_load(_root):
                events.append(("reconstructed_csv_read", None))
                common = pd.DataFrame(
                    {"case_id": ["fixture"], "event": [1], "follow_up_y": [1.0]}
                )
                return common, {}

            def stop_on_pfi_read(*_args, **_kwargs):
                events.append(("pfi_csv_read", None))
                raise StopAfterFirstCsvRead

            with (
                mock.patch.object(r4, "snapshot_paths", side_effect=fake_snapshot),
                mock.patch.object(r4, "load_reconstructed_common_cohort", side_effect=fake_load),
                mock.patch.object(
                    r4,
                    "normalize_endpoint",
                    return_value=pd.DataFrame(
                        {"case_id": ["fixture"], "endpoint_id": ["E04_reconstructed_with_tumor"]}
                    ),
                ),
                mock.patch.object(r4.pd, "read_csv", side_effect=stop_on_pfi_read),
            ):
                with self.assertRaises(StopAfterFirstCsvRead):
                    r4.run_analysis(root=root, output_dir=root / "outputs")

            self.assertEqual(
                [event for event, _ in events],
                ["snapshot", "reconstructed_csv_read", "pfi_csv_read"],
            )
            snapshotted = set(events[0][1] or ())
            self.assertIn("confounder_nested_predictions.csv", snapshotted)
            self.assertIn("bcr.csv", snapshotted)
            self.assertIn(pfi_path.name, snapshotted)
            self.assertIn(pfi_manifest.name, snapshotted)

    def test_manifest_declares_every_clean_rerun_volatile_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = directory / "input.csv"
            output_path = directory / "output.csv"
            input_path.write_text("x\n1\n", encoding="utf-8")
            output_path.write_text("y\n2\n", encoding="utf-8")
            before = r4.snapshot_paths([input_path], directory)
            after = r4.snapshot_paths([input_path], directory)

            def build(generated_at, elapsed):
                return r4.build_run_manifest(
                    root=directory,
                    input_before=before,
                    input_after=after,
                    input_roles={input_path.resolve(): "fixture"},
                    output_paths=[output_path],
                    manifest_path=directory / "manifest.csv",
                    software={"python": "fixture"},
                    generated_at_utc=generated_at,
                    elapsed_seconds=elapsed,
                )

            first = build("2026-08-06T00:00:00Z", 1.0)
            output_path.touch()
            second = build("2026-08-06T00:00:01Z", 2.0)
            expected = {
                "input": "",
                "output": "mtime_ns",
                "manifest": "generated_at_utc;elapsed_seconds",
            }
            self.assertEqual(
                first.set_index("artifact_kind")["volatile_fields"].to_dict(), expected
            )

            for frame in (first, second):
                for index, row in frame.iterrows():
                    for field in str(row["volatile_fields"]).split(";"):
                        if field:
                            frame.loc[index, field] = ""
            pd.testing.assert_frame_equal(first, second, check_dtype=False)

    def test_publish_replaces_manifest_literal_last(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            stage = base / "stage"
            output_dir = base / "outputs"
            stage.mkdir()
            staged = {}
            for name in r4.OUTPUT_NAMES:
                path = stage / name
                path.write_text(name + "\n", encoding="utf-8")
                staged[name] = path

            replacements = []
            real_replace = r4.os.replace

            def record_replace(source, destination):
                replacements.append((Path(source).name, Path(destination).name))
                return real_replace(source, destination)

            with mock.patch.object(r4.os, "replace", side_effect=record_replace):
                r4._publish(staged, output_dir)

            self.assertEqual(r4.OUTPUT_NAMES[-1], r4.MANIFEST_NAME)
            self.assertEqual(replacements[-1][1], r4.MANIFEST_NAME)


@unittest.skipUnless(r4 is not None, "R4 entry point not implemented yet")
class Marker7SurvivalPairedRealInputTests(unittest.TestCase):
    def test_reconstructed_real_input_reconciles_to_frozen_153(self):
        required = [
            ROOT / "models/confounder_nested_predictions.csv",
            ROOT / "models/marker7_clinical_hierarchy_predictions.csv",
            ROOT / "models/stability_fold_assignments.csv",
            ROOT / "opendataset/TCGA-PRAD-BCR/bcr.csv",
        ]
        if not all(path.exists() for path in required):
            self.skipTest("real R4 inputs unavailable")
        common, diagnostics = r4.load_reconstructed_common_cohort(ROOT)
        self.assertEqual(len(common), 153)
        self.assertEqual(int(common["event"].sum()), 30)
        self.assertEqual(diagnostics["common_patient_id_sha256"],
                         "92a235307c549ecf329eb2450eb31833b4adbb80d130b61c18f32617049b7976")
        self.assertEqual(common["fold"].value_counts().sort_index().to_dict(),
                         {0: 31, 1: 32, 2: 27, 3: 33, 4: 30})

    def test_real_end_to_end_refits_both_endpoints_and_publishes_auditable_outputs(self):
        required = [
            ROOT / "models/confounder_nested_predictions.csv",
            ROOT / "models/marker7_clinical_hierarchy_predictions.csv",
            ROOT / "models/stability_fold_assignments.csv",
            ROOT / "opendataset/TCGA-PRAD-BCR/bcr.csv",
            ROOT / "models/.venv-conch/bin/python",
            ROOT / "models/tcga_cdr_pfi_patient_predictions.csv",
            ROOT / "models/tcga_cdr_pfi_run_manifest.csv",
        ]
        if not all(path.exists() for path in required):
            self.skipTest("real R4 inputs unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            outputs = r4.run_analysis(root=ROOT, output_dir=output_dir)
            self.assertEqual(set(outputs), set(r4.OUTPUT_NAMES))

            oof = pd.read_csv(outputs[r4.OOF_NAME])
            self.assertEqual(len(oof), 2 * 153 * 11 * 46)
            self.assertEqual(
                set(oof["endpoint_id"]),
                {"E04_reconstructed_with_tumor", "E08_official_pfi"},
            )
            self.assertTrue(oof.groupby("endpoint_id")["case_id"].nunique().eq(153).all())
            self.assertTrue(oof.groupby("endpoint_id")["model_id"].nunique().eq(11).all())
            self.assertEqual(
                sorted(oof["evaluation_time_years"].unique()),
                (np.arange(5, 51) / 10.0).tolist(),
            )
            patient_rows = oof.drop_duplicates(["endpoint_id", "model_id", "case_id"])
            event_counts = patient_rows.groupby(["endpoint_id", "model_id"])["event"].sum()
            self.assertTrue(event_counts.loc["E04_reconstructed_with_tumor"].eq(30).all())
            self.assertTrue(event_counts.loc["E08_official_pfi"].eq(15).all())
            frozen = pd.read_csv(ROOT / "models/stability_fold_assignments.csv")
            frozen = frozen[frozen["marker"] == "marker7"].set_index("case_id")["fold"]
            self.assertTrue(
                all(int(row.fold) == int(frozen.loc[row.case_id]) for row in patient_rows.itertuples())
            )
            self.assertTrue(np.isfinite(oof["survival_probability"]).all())
            self.assertTrue(oof["survival_probability"].between(0, 1).all())
            ordered_oof = oof.sort_values(
                ["endpoint_id", "model_id", "case_id", "evaluation_time_years"]
            )
            survival_change = ordered_oof.groupby(
                ["endpoint_id", "model_id", "case_id"]
            )["survival_probability"].diff()
            self.assertTrue((survival_change.dropna() <= 1e-12).all())

            # Canonical-fold refits must not silently copy the legacy 153-patient-fold scores.
            legacy_hierarchy = pd.read_csv(ROOT / "models/marker7_clinical_hierarchy_predictions.csv")
            legacy_hierarchy = legacy_hierarchy[legacy_hierarchy["model"] == "M4"].set_index("case_id")
            current_hierarchy = patient_rows[
                (patient_rows["endpoint_id"] == "E04_reconstructed_with_tumor")
                & (patient_rows["model_id"] == "H_M4")
            ].set_index("case_id")
            self.assertFalse(np.allclose(
                current_hierarchy.loc[legacy_hierarchy.index, "linear_predictor"],
                legacy_hierarchy["prediction"], rtol=0, atol=1e-12,
            ))
            legacy_nested = pd.read_csv(ROOT / "models/confounder_nested_predictions.csv")
            legacy_nested = legacy_nested[
                (legacy_nested["marker"] == "marker7_recurrence")
                & (legacy_nested["analysis"] == "fully_adjusted")
            ].set_index("case_id")
            current_nested = patient_rows[
                (patient_rows["endpoint_id"] == "E04_reconstructed_with_tumor")
                & (patient_rows["model_id"] == "N_FULL_CLINICAL")
            ].set_index("case_id")
            self.assertFalse(np.allclose(
                current_nested.loc[legacy_nested.index, "linear_predictor"],
                legacy_nested["clinical_pred"], rtol=0, atol=1e-12,
            ))

            diagnostics = pd.read_csv(outputs[r4.DIAGNOSTICS_NAME])
            self.assertEqual(len(diagnostics), 110)
            self.assertEqual(set(diagnostics["fold"]), set(range(5)))
            self.assertTrue(diagnostics["status"].eq("ok").all())
            self.assertTrue((diagnostics["n_train"] + diagnostics["n_test"] == 153).all())
            self.assertTrue((diagnostics["n_train_events"] >= 5).all())

            bootstrap = pd.read_csv(
                outputs[r4.BOOTSTRAP_NAME], keep_default_na=False, low_memory=False
            )
            self.assertEqual(len(bootstrap), 2 * 2000 * 2 * (11 + 5))
            self.assertTrue(
                bootstrap.groupby(["replicate_id"])["sample_index_sha256"]
                .nunique().eq(1).all()
            )
            self.assertEqual(sorted(bootstrap["replicate_id"].unique()), list(range(2000)))
            summary = pd.read_csv(outputs[r4.SUMMARY_NAME])
            deltas = pd.read_csv(outputs[r4.DELTAS_NAME])
            self.assertTrue((summary["n_bootstrap_requested"] == 2000).all())
            self.assertTrue((deltas["n_bootstrap_requested"] == 2000).all())
            self.assertTrue(
                (summary["bootstrap_undefined_fraction"] <= r4.MAX_UNDEFINED_FRACTION).all()
            )
            self.assertTrue(
                (deltas["bootstrap_undefined_fraction"] <= r4.MAX_UNDEFINED_FRACTION).all()
            )

            config = json.loads(outputs[r4.CONFIG_NAME].read_text(encoding="utf-8"))
            self.assertEqual(config["bootstrap"], {"n": 2000, "seed": 0, "unit": "patient row"})
            self.assertEqual(len(config["models"]), 11)
            self.assertEqual(
                config["thresholds"],
                {"max_undefined_fraction": 0.01, "min_train_events": 5},
            )
            self.assertEqual(
                config["endpoint_ids"],
                ["E04_reconstructed_with_tumor", "E08_official_pfi"],
            )
            manifest = pd.read_csv(outputs[r4.MANIFEST_NAME], dtype=str, keep_default_na=False)
            input_rows = manifest[manifest["artifact_kind"] == "input"]
            self.assertTrue(input_rows["hash_reconciled"].eq("True").all())
            self.assertTrue((input_rows["sha256_before"] == input_rows["sha256_after"]).all())
            output_rows = manifest[manifest["artifact_kind"] == "output"]
            for row in output_rows.itertuples(index=False):
                path = outputs[f"{row.artifact_role}.csv"] if f"{row.artifact_role}.csv" in outputs else outputs[f"{row.artifact_role}.json"]
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(row.sha256_after, digest)
            self_row = manifest[manifest["artifact_kind"] == "manifest"].iloc[0]
            self.assertEqual(self_row["sha256_after"], "")
            self.assertEqual(self_row["hash_exclusion_reason"], "self_referential_manifest")


if __name__ == "__main__":
    unittest.main()
