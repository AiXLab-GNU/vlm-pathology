from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

from projects.quantitative_foundation_model_validation.preexperiment import (
    run_preexperiment as p0,
)


class QuantitativeFoundationModelPreexperimentTests(unittest.TestCase):
    def test_membership_truth_and_exclusion_snapshot(self) -> None:
        common, mismatch, truth, leakage, exclusions = p0.build_membership_tables()

        counts = common.groupby(["cohort_id", "endpoint_id"]).size().to_dict()
        self.assertEqual(counts[("NADT-Prostate", "gleason_total")], 334)
        self.assertEqual(counts[("NADT-Prostate", "tumor_vs_benign")], 463)
        self.assertEqual(counts[("PANDA", "isup_grade")], 1123)
        self.assertEqual(counts[("TCGA-PRAD", "pten")], 300)
        self.assertEqual(counts[("TCGA-PRAD", "spop")], 300)
        self.assertEqual(counts[("TCGA-PRAD", "ar")], 300)
        self.assertEqual(counts[("LEOPARD", "recurrence")], 508)

        mismatch_counts = mismatch["membership_status"].value_counts().to_dict()
        self.assertEqual(mismatch_counts["conch_only"], 14)
        self.assertEqual(mismatch_counts["virchow_only"], 46)
        self.assertEqual(mismatch_counts["neither_model"], 17)
        self.assertTrue(truth.empty)

        panda = common.loc[common["cohort_id"] == "PANDA"]
        self.assertEqual(
            int(panda["notes"].eq("tile-count mismatch between encoders").sum()), 525
        )
        self.assertTrue(panda["subject_id"].eq("").all())
        self.assertTrue(
            leakage.loc[leakage["cohort_id"] == "PANDA", "assessment_status"]
            .eq("incomplete_subject_leakage_not_assessable")
            .all()
        )
        self.assertGreater(len(exclusions), 0)

    def test_metric_roles_remain_conservative(self) -> None:
        eligibility, provenance = p0.metric_tables(["0" * 64])
        by_id = eligibility.set_index("metric_id")

        self.assertEqual(
            by_id.loc["p0.precise.tumor_fraction", "allowed_role"],
            "descriptive_primary_candidate_not_confirmatory",
        )
        self.assertEqual(
            by_id.loc["p0.precise.nuclear_density_mm2", "measurement_status"],
            "deferred",
        )
        self.assertEqual(
            by_id.loc["p0.precise.gland_lumen_fraction", "measurement_status"],
            "deferred",
        )
        self.assertEqual(
            by_id.loc["p0.precise.tissue_valid_fraction", "allowed_role"], "QC_only"
        )
        self.assertEqual(len(eligibility), len(provenance))

    def test_immutable_clinician_source_hash(self) -> None:
        source = p0.ROOT / "resources/data/precise_pni_candidate_triage/pathologist_reviews/candidate_review/precise_pni_review (1).csv"
        self.assertEqual(p0.sha256_file(source), p0.EXPECTED_CLINICIAN_SHA256)

    def test_all_required_tables_have_nonempty_schemas(self) -> None:
        self.assertEqual(len(p0.TABLE_SCHEMAS), 12)
        for name, columns in p0.TABLE_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M3_SCHEMAS), 5)
        for name, columns in p0.M3_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M4_SCHEMAS), 6)
        for name, columns in p0.M4_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M5_SCHEMAS), 3)
        for name, columns in p0.M5_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M6_SCHEMAS), 6)
        for name, columns in p0.M6_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M7_SCHEMAS), 10)
        for name, columns in p0.M7_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(len(p0.M8_SCHEMAS), 4)
        for name, columns in p0.M8_SCHEMAS.items():
            with self.subTest(name=name):
                self.assertTrue(columns)
                self.assertEqual(len(columns), len(set(columns)))

    def test_m8_locked_decision_rule_does_not_imply_approval(self) -> None:
        conditional = {
            "P0-G0": "pass",
            "P0-G1": "conditional_pass_descriptive_tumor_only",
            "P0-G2": "conditional_pass_verified_linkage_only",
            "P0-G3": "pass_saved_outputs_reverified",
            "P0-G4": "conditional_pass_descriptive_tumor_only",
            "P0-G5": "pass_technical_paired_embeddings",
            "P0-G6": "conditional_pass_descriptive_tumor_conch_and_virchow",
            "P0-G7": "amber_defined_shared_fov_descriptive_scope",
        }
        self.assertEqual(p0.m8_draft_decision(conditional), "Conditional Go")
        conditional["P0-G7"] = "red_robustness_or_paired_premise_failure"
        self.assertEqual(p0.m8_draft_decision(conditional), "Revise/Stop")

    def test_m5_tiled_region_reader_preserves_locked_pixels(self) -> None:
        y, x = np.indices((47, 61))
        rgb = np.stack([(x + y) % 256, (2 * x) % 256, (3 * y) % 256], axis=-1).astype(np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tif"
            tifffile.imwrite(path, rgb, tile=(16, 16), photometric="rgb")
            with tifffile.TiffFile(path) as tif:
                observed = p0.read_tiled_rgb_region(tif.pages[0], 7, 5, 55, 42)
        np.testing.assert_array_equal(observed, rgb[5:42, 7:55])

    def test_m5_determinism_sample_is_fixed_and_unique(self) -> None:
        first = p0.m5_audit_indices(1218)
        second = p0.m5_audit_indices(1218)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(len(np.unique(first)), 8)

    def test_m6_subject_mean_uses_one_row_per_subject(self) -> None:
        import pandas as pd

        analysis = pd.DataFrame({
            "subject_id": ["a", "a", "b"],
            "truth": [0.0, 1.0, 0.25],
        })
        frame = p0.m6_analysis_frame(analysis, np.array([0.2, 0.8, 0.4]), "subject_mean")
        self.assertEqual(frame.group_id.tolist(), ["a", "b"])
        np.testing.assert_allclose(frame.truth, [0.5, 0.25])
        np.testing.assert_allclose(frame.prediction, [0.5, 0.4])


if __name__ == "__main__":
    unittest.main()
