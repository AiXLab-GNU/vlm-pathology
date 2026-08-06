import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from models.build_precise_pni_morphology_review import (
    RESPONSE_COLUMNS,
    assign_blinded_ids,
    build_html,
    centered_crop_origins,
    crop_with_padding,
    derive_fixed_set,
    finalize_package,
    validate_completed_review,
)


def fixture_rows():
    review = pd.DataFrame(
        {
            "candidate_id": ["C-1", "C-2", "C-3"],
            "review_order": [1, 2, 3],
            "image_id": ["sub-1_ses-1", "sub-2_ses-1", "sub-3_ses-1"],
            "x0": [10, 20, 30],
            "y0": [11, 21, 31],
            "window_px": [100, 100, 100],
            "window_um": [300, 300, 300],
            "nerve_present": ["yes", "no", "yes"],
            "pni_present": ["yes", "no", "no"],
            "tumor_nerve_relation": ["touching", "none", "adjacent"],
        }
    )
    audit = review.drop(columns=["nerve_present", "pni_present", "tumor_nerve_relation"]).copy()
    audit["subject_id"] = ["sub-1", "sub-2", "sub-3"]
    audit["combined_score"] = [0.9, 0.8, 0.7]
    return review, audit


class FixedSetTests(unittest.TestCase):
    def test_fixed_set_uses_only_yes_and_reconciles_geometry(self):
        review, audit = fixture_rows()
        got = derive_fixed_set(review, audit, expected_count=2)
        self.assertEqual(got.candidate_id.tolist(), ["C-1", "C-3"])
        self.assertEqual(got.subject_id.tolist(), ["sub-1", "sub-3"])

    def test_fixed_set_uses_review_labels_when_audit_repeats_label_columns(self):
        review, audit = fixture_rows()
        audit["pni_present"] = ["yes", "no", "no"]
        audit["tumor_nerve_relation"] = ["touching", "none", "adjacent"]
        got = derive_fixed_set(review, audit, expected_count=2)
        self.assertEqual(got.previous_pni_status.tolist(), ["definite", "absent"])
        self.assertEqual(got.previous_relation.tolist(), ["touching", "adjacent"])

    def test_fixed_set_rejects_count_duplicate_and_geometry_mismatch(self):
        review, audit = fixture_rows()
        with self.assertRaisesRegex(ValueError, "expected 14"):
            derive_fixed_set(review, audit, expected_count=14)
        duplicate = pd.concat([review, review.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            derive_fixed_set(duplicate, audit, expected_count=3)
        audit.loc[0, "x0"] = 999
        with self.assertRaisesRegex(ValueError, "geometry"):
            derive_fixed_set(review, audit, expected_count=2)

    def test_blinded_ids_are_deterministic_and_public_records_are_blind(self):
        review, audit = fixture_rows()
        fixed = derive_fixed_set(review, audit, expected_count=2)
        first = assign_blinded_ids(fixed, seed=17)
        second = assign_blinded_ids(fixed, seed=17)
        self.assertEqual(first[["temporary_id", "candidate_id"]].to_dict("records"),
                         second[["temporary_id", "candidate_id"]].to_dict("records"))
        self.assertEqual(set(first.temporary_id), {"MORPH-001", "MORPH-002"})


class ImageTests(unittest.TestCase):
    def test_centered_origins_preserve_candidate_center(self):
        self.assertEqual(centered_crop_origins(100, 200, 120, [120, 240, 480]),
                         [(100, 200), (40, 140), (-80, 20)])

    def test_crop_padding_is_white_and_source_is_centered(self):
        arr = np.zeros((3, 3, 3), dtype=np.uint8)
        arr[:, :, 0] = 7
        got = np.asarray(crop_with_padding(arr, -1, -1, 4))
        self.assertEqual(tuple(got[0, 0]), (255, 255, 255))
        self.assertEqual(tuple(got[1, 1]), (7, 0, 0))

    def test_html_contains_only_blinded_case_metadata(self):
        cases = [{"temporary_id": "MORPH-001", "review_order": 1,
                  "field_300_uri": "data:image/jpeg;base64,AAA",
                  "field_600_uri": "data:image/jpeg;base64,BBB",
                  "field_1200_uri": "data:image/jpeg;base64,CCC"}]
        html = build_html(cases)
        self.assertIn("MORPH-001", html)
        self.assertIn("intraneural_component", html)
        self.assertIn("CSV 다운로드", html)
        for leaked in ["candidate_id", "image_id", "subject_id", "combined_score",
                       "selection_stratum", "x0", "PRECISE-PNI-"]:
            self.assertNotIn(leaked, html)


class FinalizeTests(unittest.TestCase):
    def template(self):
        row = {column: "" for column in RESPONSE_COLUMNS}
        row.update({
            "temporary_id": "MORPH-001", "reviewer_id": "Song",
            "nerve_present": "yes", "pni_status": "definite",
            "overall_relation": "touching", "touching_component": "yes",
            "surrounding_component": "no", "intraneural_component": "no",
            "section_orientation": "transverse", "longitudinal_tracking": "no",
            "branch_point_involvement": "no", "nerve_multiplicity": "single",
            "field_adequacy": "adequate", "overall_confidence": "high",
        })
        return pd.DataFrame([row])

    def test_finalize_preserves_blank_and_reports_logical_conflict(self):
        frame = self.template()
        frame.loc[0, "reviewer_notes"] = ""
        frame.loc[0, "nerve_present"] = "no"
        normalized, issues = validate_completed_review(frame, ["MORPH-001"])
        self.assertTrue(pd.isna(normalized.loc[0, "reviewer_notes"]))
        self.assertIn("nerve_no_with_positive_pni", issues.issue_code.tolist())
        self.assertEqual(normalized.loc[0, "pni_status"], "definite")

    def test_finalize_reports_missing_fields_without_coercing_them_to_no(self):
        frame = self.template()
        frame.loc[0, "longitudinal_tracking"] = ""
        normalized, issues = validate_completed_review(frame, ["MORPH-001"])
        self.assertTrue(pd.isna(normalized.loc[0, "longitudinal_tracking"]))
        missing = issues.loc[issues.issue_code.eq("missing_value"), "detail"].tolist()
        self.assertEqual(missing, ["Missing longitudinal_tracking; not interpreted as no"])

    def test_finalize_rejects_invalid_unknown_missing_and_duplicate_ids(self):
        frame = self.template()
        frame.loc[0, "pni_status"] = "yes"
        with self.assertRaisesRegex(ValueError, "pni_status"):
            validate_completed_review(frame, ["MORPH-001"])
        frame = self.template()
        frame.loc[0, "temporary_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "ID set"):
            validate_completed_review(frame, ["MORPH-001"])
        frame = pd.concat([self.template(), self.template()], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_completed_review(frame, ["MORPH-001"])

    def test_finalize_writes_provenance_and_separates_missing_from_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = root / "completed.csv"
            mapping = root / "mapping.csv"
            output = root / "locked"
            frame = self.template()
            frame.loc[0, "reviewer_notes"] = ""
            frame.to_csv(completed, index=False)
            pd.DataFrame({
                "temporary_id": ["MORPH-001"], "candidate_id": ["C-1"],
                "previous_pni_status": ["definite"], "previous_relation": ["touching"],
            }).to_csv(mapping, index=False)
            finalize_package(completed, mapping, output)
            config = json.loads((output / "run_config.json").read_text())
            self.assertEqual(config["stage"], "finalize")
            self.assertEqual(config["missing_value_count"], 0)
            self.assertEqual(config["logical_conflict_count"], 0)
            self.assertIn("normalized_morphology_review.csv", config["outputs"])
            self.assertEqual(len(config["inputs"]), 2)


if __name__ == "__main__":
    unittest.main()
