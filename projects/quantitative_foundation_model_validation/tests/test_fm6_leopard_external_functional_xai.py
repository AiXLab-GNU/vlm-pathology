import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "projects/quantitative_foundation_model_validation/milestones/fm6_external_functional_validation/run_fm6_leopard_external_functional_xai.py"
)
OUTPUTS = SCRIPT.parent / "outputs"
SPEC = importlib.util.spec_from_file_location("run_fm6_leopard_external_functional_xai", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FM6LeopardExternalFunctionalXAITest(unittest.TestCase):
    def test_locked_source_membership(self):
        inventory = MODULE.verify_source_membership()
        self.assertEqual(len(inventory), MODULE.EXPECTED_SUBJECTS)
        self.assertEqual(inventory.case_id.nunique(), MODULE.EXPECTED_SUBJECTS)
        self.assertTrue(inventory.wsi_bytes.gt(0).all())
        self.assertTrue(inventory.mask_bytes.gt(0).all())

    def test_stable_rng_is_case_specific_and_repeatable(self):
        first = MODULE.stable_rng("case_radboud_0000.tif").integers(0, 100000, 10)
        second = MODULE.stable_rng("case_radboud_0000.tif").integers(0, 100000, 10)
        other = MODULE.stable_rng("case_radboud_0001.tif").integers(0, 100000, 10)
        self.assertTrue((first == second).all())
        self.assertFalse((first == other).all())

    def test_source_paths_reject_unexpected_id(self):
        image, mask = MODULE.expected_source_paths("case_radboud_0000.tif")
        self.assertTrue(image.name.endswith("0000.tif"))
        self.assertTrue(mask.name.endswith("0000_tissue.tif"))
        with self.assertRaises(ValueError):
            MODULE.expected_source_paths("TCGA-HC-0000")

    def test_preparation_lock_if_present(self):
        lock_path = OUTPUTS / "fm6_leopard_preparation_lock.json"
        if not lock_path.exists():
            self.skipTest("preparation not generated yet")
        _, lock = MODULE.verify_preparation()
        self.assertEqual(lock["source_subjects"], MODULE.EXPECTED_SUBJECTS)
        self.assertEqual(lock["source_events"], MODULE.EXPECTED_EVENTS)
        self.assertGreaterEqual(lock["evaluable_events"], MODULE.MIN_EVALUABLE_EVENTS)
        self.assertEqual(lock["external_clearance_document"], "unrecorded")

    def test_saved_outputs_preserve_claim_boundary(self):
        config_path = OUTPUTS / "fm6_leopard_external_run_config.json"
        if not config_path.exists():
            self.skipTest("external analysis not generated yet")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIn(config["overall_status"], {
            "PASS_REPLICATED_EXTERNAL_WHOLE_TISSUE_FUNCTIONAL_TRANSPORT",
            "PARTIAL_ENCODER_SPECIFIC_EXTERNAL_FUNCTIONAL_TRANSPORT",
            "FAIL_OR_INCONCLUSIVE_EXTERNAL_FUNCTIONAL_TRANSPORT",
        })
        self.assertIn("strong H2 prohibited", config["claim_ceiling"])
        for filename, expected in config["output_sha256"].items():
            self.assertEqual(MODULE.sha256_file(OUTPUTS / filename), expected, filename)


if __name__ == "__main__":
    unittest.main()
