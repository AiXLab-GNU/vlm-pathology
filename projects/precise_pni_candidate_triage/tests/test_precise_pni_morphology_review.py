import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from projects.precise_pni_candidate_triage.code.morphology_rereview.build_precise_pni_morphology_review import (
    RESPONSE_COLUMNS,
    assign_blinded_ids,
    build_html,
    centered_crop_origins,
    crop_with_padding,
    derive_fixed_set,
    finalize_package,
    sha256_file,
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

    def test_finalize_writes_case_level_transitions_summaries_and_contour_reasons(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = root / "completed.csv"
            mapping = root / "mapping.csv"
            output = root / "locked"
            first = self.template().iloc[0].to_dict()
            first["pni_status"] = "probable"
            second = self.template().iloc[0].to_dict()
            second.update({
                "temporary_id": "MORPH-002",
                "pni_status": "absent",
                "overall_relation": "not_evaluable",
                "touching_component": "not_evaluable",
                "surrounding_component": "not_evaluable",
                "intraneural_component": "not_evaluable",
                "section_orientation": "not_evaluable",
                "longitudinal_tracking": "not_evaluable",
                "branch_point_involvement": "not_evaluable",
            })
            pd.DataFrame([first, second], columns=RESPONSE_COLUMNS).to_csv(completed, index=False)
            pd.DataFrame({
                "temporary_id": ["MORPH-001", "MORPH-002"],
                "candidate_id": ["C-1", "C-2"],
                "previous_pni_status": ["definite", "absent"],
                "previous_relation": ["touching", "none"],
            }).to_csv(mapping, index=False)

            finalize_package(completed, mapping, output)

            integrity = pd.read_csv(output / "morphology_data_integrity_report.csv")
            self.assertEqual(len(integrity), 2)
            self.assertEqual(integrity.form_complete.tolist(), [True, True])
            self.assertEqual(integrity.evaluable_pni_status.tolist(), [True, True])
            self.assertEqual(integrity.strict_all_core_morphology_evaluable.tolist(), [True, False])

            transitions = pd.read_csv(output / "morphology_transition_table.csv")
            self.assertEqual(len(transitions), 2)
            self.assertEqual(transitions.pni_transition_class.tolist(), ["downgraded", "unchanged"])
            self.assertEqual(transitions.relation_transition_class.tolist(), ["unchanged", "changed_category"])
            transition_summary = pd.read_csv(output / "morphology_transition_summary.csv")
            self.assertEqual(int(transition_summary["count"].sum()), 4)

            contour = pd.read_csv(output / "contour_eligibility_table.csv")
            self.assertEqual(contour.contour_disposition.tolist(),
                             ["adjudication_required", "eligible_for_contouring"])
            self.assertTrue(contour.contour_disposition_reason.str.len().gt(0).all())
            self.assertIn("overall_relation", contour.loc[1, "unresolved_morphology_fields"])

            summary = pd.read_csv(output / "morphology_summary.csv")
            metrics = summary.loc[summary.summary_group.eq("completion")].set_index("value")["count"]
            self.assertEqual(int(metrics["form_complete"]), 2)
            self.assertEqual(int(metrics["evaluable_pni_status"]), 2)
            self.assertEqual(int(metrics["strict_all_core_morphology_evaluable"]), 1)

    def test_finalize_records_official_source_provenance_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = root / "completed.csv"
            clinician = root / "clinician.csv"
            mapping = root / "mapping.csv"
            immutable = root / "immutable.csv"
            output_a = root / "locked-a"
            output_b = root / "locked-b"
            normalized = self.template()
            original = normalized.copy()
            original["reviewer_id"] = ""
            normalized.to_csv(completed, index=False)
            original.to_csv(clinician, index=False)
            immutable.write_text("candidate_id\nC-1\n", encoding="utf-8")
            pd.DataFrame({
                "temporary_id": ["MORPH-001"], "candidate_id": ["C-1"],
                "previous_pni_status": ["definite"], "previous_relation": ["touching"],
            }).to_csv(mapping, index=False)

            kwargs = {
                "completed_path": completed,
                "mapping_path": mapping,
                "clinician_completed_path": clinician,
                "immutable_review_path": immutable,
                "expected_reviewer_id": "Song",
                "command": ".venv/bin/python projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py finalize",
            }
            finalize_package(output_dir=output_a, **kwargs)
            finalize_package(output_dir=output_b, **kwargs)

            config_a = json.loads((output_a / "run_config.json").read_text())
            config_b = json.loads((output_b / "run_config.json").read_text())
            self.assertTrue(config_a["locked"])
            self.assertEqual(config_a["random_seed"], "not_applicable")
            self.assertEqual(config_a["immutable_source_sha256_before"], sha256_file(immutable))
            self.assertEqual(config_a["immutable_source_sha256_after"], sha256_file(immutable))
            self.assertIn("clinician_completed_original", config_a["inputs"])
            self.assertEqual(
                config_a["command"],
                ".venv/bin/python projects/precise_pni_candidate_triage/code/morphology_rereview/build_precise_pni_morphology_review.py finalize",
            )
            for name in config_a["outputs"]:
                self.assertEqual(sha256_file(output_a / name), sha256_file(output_b / name))
            config_a.pop("execution_timestamp_utc")
            config_b.pop("execution_timestamp_utc")
            self.assertEqual(config_a, config_b)

    def test_finalize_rejects_source_drift_mapping_duplicates_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = root / "completed.csv"
            clinician = root / "clinician.csv"
            mapping = root / "mapping.csv"
            normalized = self.template()
            original = normalized.copy()
            original["reviewer_id"] = ""
            normalized.to_csv(completed, index=False)
            original.to_csv(clinician, index=False)
            pd.DataFrame({
                "temporary_id": ["MORPH-001"], "candidate_id": ["C-1"],
                "previous_pni_status": ["definite"], "previous_relation": ["touching"],
            }).to_csv(mapping, index=False)

            drifted = original.copy()
            drifted.loc[0, "pni_status"] = "absent"
            drifted.to_csv(clinician, index=False)
            with self.assertRaisesRegex(ValueError, "outside reviewer_id"):
                finalize_package(completed, mapping, root / "drift", clinician_completed_path=clinician)

            original.to_csv(clinician, index=False)
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                finalize_package(
                    completed, mapping, root / "hash",
                    expected_input_hashes={"completed_review_normalized": "0" * 64},
                )
            with self.assertRaisesRegex(ValueError, "exact expected temporary ID set"):
                finalize_package(completed, mapping, root / "count", expected_case_count=14)

            second = normalized.copy()
            second.loc[0, "temporary_id"] = "MORPH-002"
            pd.concat([normalized, second], ignore_index=True).to_csv(completed, index=False)
            pd.DataFrame({
                "temporary_id": ["MORPH-001", "MORPH-002"],
                "candidate_id": ["C-1", "C-1"],
                "previous_pni_status": ["definite", "definite"],
                "previous_relation": ["touching", "touching"],
            }).to_csv(mapping, index=False)
            with self.assertRaisesRegex(ValueError, "duplicate candidate ID"):
                finalize_package(completed, mapping, root / "duplicate")


if __name__ == "__main__":
    unittest.main()
