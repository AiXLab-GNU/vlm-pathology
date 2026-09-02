import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"


class FM9ProstateDiagnosticAnchorAndDiscoveryTests(unittest.TestCase):
    def setUp(self):
        registry_path = PROJECT / "manifests/prostate_diagnostic_cohort_portfolio.yaml"
        self.registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        self.cohorts = {row["dataset_id"]: row for row in self.registry["cohorts"]}

    def test_endpoint_and_model_paths_are_separated(self):
        rules = self.registry["rules"]
        self.assertEqual(
            rules["endpoint_separation"],
            "cancer_presence_and_cancer_only_grading_are_distinct",
        )
        self.assertEqual(
            rules["diagnostic_anchor_separation"],
            "task_specific_anchor_cannot_establish_frozen_fm_feature_use",
        )
        self.assertEqual(rules["external_tuning"], "prohibited")

    def test_selected_cohorts_have_non_interchangeable_roles(self):
        self.assertIn("multi_reader_qualification", self.cohorts["DiagSet"]["roles"])
        self.assertEqual(
            self.cohorts["PBGG-1-2"]["endpoints"], ["cancer_only_grading"]
        )
        self.assertIn(
            "paired_ihc_spatial_criterion_anchor", self.cohorts["PRECISE"]["roles"]
        )
        self.assertEqual(
            self.cohorts["PRECISE"]["access_state"],
            "local_he_only_legacy_failed_paired_ihc_target_not_acquired",
        )
        self.assertIn("fm9_primary_gate", self.cohorts["PAR-S-BIAD2323"]["prohibited_uses"])

    def test_protocol_retires_primary_random_64_tile_and_ordinal_cancer_proxy(self):
        protocol = (
            PROJECT
            / "docs/protocols/fm9-prostate-diagnostic-anchor-and-discovery-protocol-ko.md"
        ).read_text(encoding="utf-8")
        self.assertIn("random maximum-64 tissue tile bag을 primary coverage로 사용하지 않음", protocol)
        self.assertIn("전용 cancer head", protocol)
        self.assertIn("common physical-FOV branch", protocol)
        self.assertIn("model-card native-scale branch", protocol)


if __name__ == "__main__":
    unittest.main()
