"""Behavioral tests for the approved R3 official TCGA-CDR PFI audit."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import openpyxl
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "models/build_tcga_cdr_pfi_evidence.py"
REAL_INPUTS = all(
    (ROOT / path).is_file()
    for path in (
        "local-data/TCGA-CDR/TCGA-CDR-SupplementalTableS1.xlsx",
        "local-data/TCGA-CDR/PanCan-Clinical_Open_GDC-Manifest_1.txt",
        "local-data/TCGA-CDR/source_provenance.json",
        "models/confounder_nested_predictions.csv",
        "models/tcga_prad_clinical_extra/prad_pancan_clinical.json",
        "opendataset/TCGA-PRAD-BCR/bcr_recurrence_only.csv",
    )
)

if SCRIPT.is_file():
    spec = importlib.util.spec_from_file_location("tcga_cdr_pfi_evidence", SCRIPT)
    evidence = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(evidence)
else:
    evidence = None


class R3EntryPointTests(unittest.TestCase):
    def test_approved_r3_entry_point_exists(self):
        self.assertTrue(SCRIPT.is_file(), "approved R3 entry point is missing")


@unittest.skipIf(evidence is None, "R3 entry point not implemented")
class R3UnitTests(unittest.TestCase):
    def test_mapping_preserves_each_invalid_official_outcome_with_a_reason(self):
        risk = pd.DataFrame(
            {
                "case_id": ["TCGA-AA-0001", "TCGA-AA-0002", "TCGA-AA-0003",
                            "TCGA-AA-0004", "TCGA-AA-0005", "TCGA-AA-0006"],
                "marker7_risk": np.arange(6, dtype=float),
            }
        )
        official = pd.DataFrame(
            {
                "bcr_patient_barcode": ["TCGA-AA-0001", "TCGA-AA-0003", "tcga-aa-0003",
                                        "TCGA-AA-0004", "TCGA-AA-0005", "TCGA-AA-0006"],
                "type": ["PRAD"] * 6,
                "PFI": [1.0, 0.0, 1.0, 2.0, 0.0, np.nan],
                "PFI.time": [100.0, 50.0, 60.0, 30.0, 0.0, 90.0],
            }
        )

        mapped = evidence.build_official_mapping(risk, official).set_index("case_id")

        self.assertEqual(mapped.loc["TCGA-AA-0001", "endpoint_status"], "evaluable")
        self.assertEqual(mapped.loc["TCGA-AA-0002", "exclusion_reason"],
                         "official_barcode_not_found")
        self.assertEqual(mapped.loc["TCGA-AA-0003", "exclusion_reason"],
                         "duplicate_official_barcode")
        self.assertEqual(mapped.loc["TCGA-AA-0004", "exclusion_reason"],
                         "nonbinary_official_pfi_event")
        self.assertEqual(mapped.loc["TCGA-AA-0005", "exclusion_reason"],
                         "nonpositive_official_pfi_time")
        self.assertEqual(mapped.loc["TCGA-AA-0006", "exclusion_reason"],
                         "missing_official_pfi_event")
        self.assertTrue(pd.isna(mapped.loc["TCGA-AA-0006", "official_pfi_event"]))
        self.assertFalse((mapped["official_pfi_event"].dropna() == 0).all())

    def test_frozen_risk_requires_unique_grade_rows_and_agreeing_duplicate_risk(self):
        rows = [
            {"case_id": "TCGA-AA-0001", "marker": "marker7_recurrence",
             "analysis": "grade_only", "scope": "patient", "marker7_risk": 0.25,
             "event": 0.0, "follow_up_y": 1.0},
            {"case_id": "TCGA-AA-0002", "marker": "marker7_recurrence",
             "analysis": "grade_only", "scope": "patient", "marker7_risk": 0.75,
             "event": 1.0, "follow_up_y": 2.0},
            {"case_id": "TCGA-AA-0001", "marker": "marker7_recurrence",
             "analysis": "fully_adjusted", "scope": "patient", "marker7_risk": 0.25,
             "event": 0.0, "follow_up_y": 1.0},
        ]
        valid = pd.DataFrame(rows)
        selected = evidence.select_frozen_risk(valid, expected_n=2)
        self.assertEqual(selected.case_id.tolist(), ["TCGA-AA-0001", "TCGA-AA-0002"])

        mismatched = valid.copy()
        mismatched.loc[mismatched.analysis.eq("fully_adjusted"), "marker7_risk"] = 9.0
        with self.assertRaisesRegex(evidence.EvidenceError, "fully_adjusted"):
            evidence.select_frozen_risk(mismatched, expected_n=2)

        duplicated = pd.concat([valid, valid.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(evidence.EvidenceError, "unique"):
            evidence.select_frozen_risk(duplicated, expected_n=2)

    def test_harrell_c_index_and_bootstrap_keep_undefined_draws(self):
        event = np.array([1, 1, 0], dtype=bool)
        time = np.array([1.0, 2.0, 3.0])
        self.assertEqual(evidence.harrell_c_index(event, time, np.array([3.0, 2.0, 1.0]))[0], 1.0)
        self.assertEqual(evidence.harrell_c_index(event, time, np.array([1.0, 2.0, 3.0]))[0], 0.0)

        result = evidence.bootstrap_c_index(
            np.zeros(3, dtype=bool), time, np.array([1.0, 2.0, 3.0]), n_boot=25, seed=11
        )
        self.assertEqual(result["n_bootstrap_requested"], 25)
        self.assertEqual(result["n_bootstrap_valid"], 0)
        self.assertEqual(result["n_bootstrap_undefined"], 25)
        self.assertEqual(result["bootstrap_undefined_fraction"], 1.0)
        self.assertTrue(np.isnan(result["c_index_ci_low"]))
        self.assertEqual(result, evidence.bootstrap_c_index(
            np.zeros(3, dtype=bool), time, np.array([1.0, 2.0, 3.0]), n_boot=25, seed=11
        ))

    def test_concordance_uses_explicit_endpoint_ids_and_literal_confusion_counts(self):
        rows = []
        for endpoint_id, events, times in (
            (evidence.OFFICIAL_ENDPOINT_ID, [0, 0, 1, 1], [1.0, 2.0, 3.0, 4.0]),
            ("comparison", [0, 1, 0, 1], [10.0, 20.0, 30.0, 40.0]),
        ):
            for case_id, event, time in zip(["A", "B", "C", "D"], events, times):
                rows.append({"case_id": case_id, "endpoint_id": endpoint_id,
                             "endpoint_status": "evaluable", "event": event,
                             "time_years": time})
        summary = evidence.build_endpoint_concordance(pd.DataFrame(rows))
        row = summary.iloc[0]
        self.assertEqual(row["reference_endpoint_id"], evidence.OFFICIAL_ENDPOINT_ID)
        self.assertEqual(row["comparison_endpoint_id"], "comparison")
        self.assertEqual(
            [row["n_ref0_cmp0"], row["n_ref0_cmp1"], row["n_ref1_cmp0"], row["n_ref1_cmp1"]],
            [1, 1, 1, 1],
        )
        self.assertEqual(row["event_agreement"], 0.5)
        self.assertEqual(row["cohen_kappa"], 0.0)
        self.assertEqual(row["time_spearman_rho"], 1.0)

    def test_canonical_mapping_rejects_non_one_to_one_but_preserves_endpoint_reason(self):
        self.assertTrue(hasattr(evidence, "validate_canonical_mapping"))
        endpoint_missing = pd.DataFrame({
            "case_id": ["TCGA-AA-0001"],
            "mapping_status": ["one_to_one"],
            "endpoint_status": ["not_evaluable"],
            "exclusion_reason": ["missing_official_pfi_event"],
        })
        evidence.validate_canonical_mapping(endpoint_missing)

        for mapping_status in ("unmapped", "ambiguous"):
            with self.subTest(mapping_status=mapping_status):
                broken = endpoint_missing.copy()
                broken["mapping_status"] = mapping_status
                with self.assertRaisesRegex(evidence.EvidenceError, "one-to-one"):
                    evidence.validate_canonical_mapping(broken)

    def test_publish_rolls_back_every_preexisting_output_after_mid_install_failure(self):
        self.assertTrue(hasattr(evidence, "_publish"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            output = root / "output"
            stage.mkdir()
            output.mkdir()
            staged = {}
            for name in evidence.ALL_OUTPUT_NAMES:
                (stage / name).write_text(f"new:{name}\n", encoding="utf-8")
                (output / name).write_text(f"old:{name}\n", encoding="utf-8")
                staged[name] = stage / name

            real_replace = os.replace
            calls = 0

            def fail_third_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("injected intermediate publication failure")
                return real_replace(source, destination)

            with patch.object(evidence.os, "replace", side_effect=fail_third_replace):
                with self.assertRaisesRegex(evidence.EvidenceError, "restored"):
                    evidence._publish(staged, output)

            for name in evidence.ALL_OUTPUT_NAMES:
                self.assertEqual(
                    (output / name).read_text(encoding="utf-8"), f"old:{name}\n"
                )

    def test_publish_installs_manifest_last_as_completion_marker(self):
        self.assertTrue(hasattr(evidence, "_publish"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            output = root / "output"
            stage.mkdir()
            staged = {}
            for name in evidence.ALL_OUTPUT_NAMES:
                (stage / name).write_text(f"new:{name}\n", encoding="utf-8")
                staged[name] = stage / name

            real_replace = os.replace
            installed_names = []

            def record_replace(source, destination):
                installed_names.append(Path(destination).name)
                return real_replace(source, destination)

            with patch.object(evidence.os, "replace", side_effect=record_replace):
                evidence._publish(staged, output)

            self.assertEqual(installed_names[-1], "tcga_cdr_pfi_run_manifest.csv")

    def test_canonical_output_rejects_nonfrozen_bootstrap_before_reading_inputs(self):
        self.assertTrue(hasattr(evidence, "validate_run_parameters"))
        cases = ((40, evidence.BOOTSTRAP_SEED), (evidence.N_BOOTSTRAP, 19))
        for draws, seed in cases:
            with self.subTest(draws=draws, seed=seed):
                with patch.object(
                    evidence, "_input_contract",
                    side_effect=AssertionError("input read occurred before parameter rejection"),
                ):
                    with self.assertRaisesRegex(evidence.EvidenceError, "canonical"):
                        evidence.run_analysis(
                            ROOT, ROOT / "models", n_boot=draws, seed=seed
                        )


@unittest.skipUnless(REAL_INPUTS and evidence is not None, "official R3 inputs unavailable")
class R3OfficialIntegrationTests(unittest.TestCase):
    def test_run_analysis_rejects_non_one_to_one_mapping_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "outputs"
            real_builder = evidence.build_official_mapping

            def inject_unmapped(risk, official):
                mapping = real_builder(risk, official)
                mapping.loc[0, "mapping_status"] = "unmapped"
                mapping.loc[0, "exclusion_reason"] = "injected_unmapped_barcode"
                return mapping

            with patch.object(evidence, "build_official_mapping", side_effect=inject_unmapped):
                with self.assertRaisesRegex(evidence.EvidenceError, "one-to-one"):
                    evidence.run_analysis(ROOT, output_dir, n_boot=5, seed=7)
            self.assertFalse(any((output_dir / name).exists() for name in evidence.ALL_OUTPUT_NAMES))

    def test_official_run_reconciles_counts_hashes_endpoints_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            outputs = evidence.run_analysis(ROOT, output_dir, n_boot=40, seed=19)
            self.assertEqual(set(outputs), set(evidence.ALL_OUTPUT_NAMES))
            self.assertEqual(evidence.CONFIG_NAME, "tcga_cdr_pfi_run_config.json")
            self.assertEqual(evidence.MANIFEST_NAME, "tcga_cdr_pfi_run_manifest.csv")
            self.assertFalse((output_dir / "run_config.json").exists())
            self.assertFalse((output_dir / "run_manifest.csv").exists())

            mapping = pd.read_csv(outputs[evidence.MAPPING_NAME])
            self.assertEqual(len(mapping), 270)
            self.assertTrue(mapping.mapping_status.eq("one_to_one").all())
            self.assertTrue(mapping.endpoint_status.eq("evaluable").all())
            self.assertEqual(int(mapping.official_pfi_event.sum()), 42)

            table_s1 = pd.read_excel(
                ROOT / "local-data/TCGA-CDR/TCGA-CDR-SupplementalTableS1.xlsx",
                sheet_name="TCGA-CDR",
            )
            direct = table_s1.loc[table_s1.type.eq("PRAD")].set_index(
                "bcr_patient_barcode"
            ).loc[mapping.case_id]
            np.testing.assert_array_equal(mapping.official_pfi_event, direct.PFI)
            np.testing.assert_allclose(mapping.official_pfi_time_days, direct["PFI.time"], rtol=0, atol=0)
            np.testing.assert_allclose(
                mapping.official_pfi_time_years,
                direct["PFI.time"].to_numpy(dtype=float) / 365.25,
                rtol=0,
                atol=2e-15,
            )

            predictions = pd.read_csv(outputs[evidence.PREDICTIONS_NAME])
            self.assertEqual(len(predictions), 270 * 5)
            counts = predictions.loc[predictions.endpoint_status.eq("evaluable")].groupby(
                "endpoint_id"
            ).agg(n=("case_id", "size"), events=("event", "sum"))
            expected = {
                evidence.OFFICIAL_ENDPOINT_ID: (270, 42),
                evidence.RECONSTRUCTED_ENDPOINT_ID: (270, 57),
                evidence.PFS_ENDPOINT_ID: (270, 42),
                evidence.DFS_ENDPOINT_ID: (192, 11),
                evidence.RECURRENCE_ONLY_ENDPOINT_ID: (220, 7),
            }
            self.assertEqual(
                {idx: (int(row.n), int(row.events)) for idx, row in counts.iterrows()}, expected
            )
            official_predictions = predictions.loc[
                predictions.endpoint_id.eq(evidence.OFFICIAL_ENDPOINT_ID)
            ].set_index("case_id").loc[mapping.case_id]
            np.testing.assert_array_equal(
                official_predictions.event, direct.PFI.to_numpy(dtype=float)
            )
            np.testing.assert_allclose(
                official_predictions.time_years,
                direct["PFI.time"].to_numpy(dtype=float) / 365.25,
                rtol=0,
                atol=2e-15,
            )

            performance = pd.read_csv(outputs[evidence.PERFORMANCE_NAME]).set_index("endpoint_id")
            self.assertAlmostEqual(
                performance.loc[evidence.OFFICIAL_ENDPOINT_ID, "c_index"],
                0.5862437090132683,
                places=14,
            )
            self.assertTrue((performance.n_bootstrap_valid + performance.n_bootstrap_undefined == 40).all())

            concordance = pd.read_csv(outputs[evidence.CONCORDANCE_NAME]).set_index(
                "comparison_endpoint_id"
            )
            self.assertEqual(
                set(concordance.index),
                {evidence.RECONSTRUCTED_ENDPOINT_ID, evidence.PFS_ENDPOINT_ID,
                 evidence.DFS_ENDPOINT_ID, evidence.RECURRENCE_ONLY_ENDPOINT_ID},
            )
            self.assertTrue(
                (concordance[["n_ref0_cmp0", "n_ref0_cmp1", "n_ref1_cmp0", "n_ref1_cmp1"]]
                 .sum(axis=1) == concordance.n_common_evaluable).all()
            )
            pfs = concordance.loc[evidence.PFS_ENDPOINT_ID]
            self.assertEqual(int(pfs.n_common_evaluable), 270)
            self.assertEqual(pfs.event_agreement, 1.0)
            self.assertEqual(pfs.cohen_kappa, 1.0)
            self.assertEqual(pfs.time_spearman_rho, 1.0)

            manifest = pd.read_csv(outputs[evidence.MANIFEST_NAME], keep_default_na=False)
            xlsx = manifest.loc[
                manifest.artifact_path.eq(
                    "local-data/TCGA-CDR/TCGA-CDR-SupplementalTableS1.xlsx"
                )
            ].iloc[0]
            self.assertEqual(xlsx.sha256_before, evidence.EXPECTED_OFFICIAL_SHA256)
            self.assertEqual(xlsx.sha256_before, xlsx.sha256_after)
            self.assertEqual(xlsx.source_unchanged_assertion, "True")
            self_row = manifest.loc[manifest.artifact_path.eq(evidence.MANIFEST_NAME)].iloc[0]
            self.assertEqual(self_row.sha256_after, "")
            self.assertEqual(self_row.hash_exclusion_reason, "self_referential_manifest")

            config = json.loads(outputs[evidence.CONFIG_NAME].read_text(encoding="utf-8"))
            self.assertIn("openpyxl", config["runtime"]["versions"])
            self.assertEqual(config["runtime"]["versions"]["openpyxl"], openpyxl.__version__)
            self.assertEqual(
                config["official_source"],
                {
                    "archived_filename": "TCGA-CDR-SupplementalTableS1.xlsx",
                    "download_url": "https://api.gdc.cancer.gov/data/1b5f413e-a8d1-4d10-92eb-7c4ae739ed81",
                    "file_uuid": "1b5f413e-a8d1-4d10-92eb-7c4ae739ed81",
                    "manifest_sha256": evidence.EXPECTED_MANIFEST_SHA256,
                    "publisher": "National Cancer Institute Genomic Data Commons",
                    "sha256": evidence.EXPECTED_OFFICIAL_SHA256,
                    "size_bytes": 2945129,
                    "supplement_sheet": "TCGA-CDR",
                },
            )

            corrupted = mapping.copy()
            corrupted.loc[1, "case_id"] = corrupted.loc[0, "case_id"]
            corrupted.to_csv(outputs[evidence.MAPPING_NAME], index=False)
            self.assertTrue(hasattr(evidence, "_validate_staged_outputs"))
            with self.assertRaises(evidence.EvidenceError):
                evidence._validate_staged_outputs(output_dir, n_risk=270, n_boot=40)


if __name__ == "__main__":
    unittest.main()
