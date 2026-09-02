import unittest
from pathlib import Path
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
LIB = PROJECT / "code/lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from fm9_anchor import (  # noqa: E402
    build_preflight,
    parse_sha256sums,
    select_model,
    unpinned_requirements,
    validate_model_contract,
)


class FM9ProstateDiagnosticAnchorAndDiscoveryTests(unittest.TestCase):
    def setUp(self):
        registry_path = PROJECT / "manifests/prostate_diagnostic_cohort_portfolio.yaml"
        self.registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        self.cohorts = {row["dataset_id"]: row for row in self.registry["cohorts"]}
        model_registry_path = PROJECT / "manifests/fm9_diagnostic_model_registry.yaml"
        self.model_registry = yaml.safe_load(model_registry_path.read_text(encoding="utf-8"))
        self.anchor_model = select_model(self.model_registry)

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

    def test_reproducible_anchor_contract_is_task_and_claim_separated(self):
        self.assertEqual(validate_model_contract(self.anchor_model), [])
        self.assertEqual(self.anchor_model["mode"], "off_the_shelf_locked_inference")
        self.assertEqual(self.anchor_model["geometry"]["spacing_microns_per_pixel"], 0.5)
        self.assertEqual(self.anchor_model["ensemble"]["concatenated_latent_dimension"], 960)
        self.assertIn("primary_binary_cancer_probability", self.anchor_model["prohibited_uses"])
        self.assertIn("panda_independent_external_validation", self.anchor_model["prohibited_uses"])

    def test_checksum_parser_and_dependency_pin_audit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sums = root / "SHA256SUMS"
            sums.write_text(f"{'a' * 64}  model.pt\n", encoding="utf-8")
            self.assertEqual(parse_sha256sums(sums), {"model.pt": "a" * 64})
            requirements = root / "requirements.txt"
            requirements.write_text("numpy<2\nseaborn==0.12.0\n", encoding="utf-8")
            self.assertEqual(unpinned_requirements(requirements), ["numpy<2"])

    def test_preflight_fails_closed_when_source_and_d0_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload = build_preflight(
                registry_path=PROJECT / "manifests/fm9_diagnostic_model_registry.yaml",
                cohort_registry_path=PROJECT / "manifests/prostate_diagnostic_cohort_portfolio.yaml",
                source_root=Path(temporary_directory) / "missing-source",
            )
        self.assertEqual(payload["readiness"], "NOT_READY")
        self.assertFalse(payload["prediction_permitted"])
        self.assertIn("source_root", payload["blockers"])
        self.assertIn("fm9_d0_dataset_gate", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
