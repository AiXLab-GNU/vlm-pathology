import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "projects/quantitative_foundation_model_validation/milestones/fm6_site_heldout_functional_validation/run_fm6_site_heldout_functional_xai.py"
)
OUTPUTS = SCRIPT.parent / "outputs"
SPEC = importlib.util.spec_from_file_location("run_fm6_site_heldout_functional_xai", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FM6SiteHeldOutFunctionalXAITest(unittest.TestCase):
    def test_tissue_source_site_parser(self):
        self.assertEqual(MODULE.tissue_source_site("TCGA-HC-7749"), "HC")
        with self.assertRaises(ValueError):
            MODULE.tissue_source_site("not-a-tcga-case")

    def test_locked_site_universe(self):
        subjects = pd.read_csv(MODULE.SOURCE / "development_subjects.csv")
        table = MODULE.source_site_table(subjects)
        sites = tuple(table.loc[table.evaluation_eligible, "tissue_source_site"])
        self.assertEqual(sites, MODULE.EXPECTED_SITES)
        subjects["site"] = subjects.case_id.map(MODULE.tissue_source_site)
        selected = subjects.site.isin(sites)
        self.assertEqual(int(selected.sum()), MODULE.EXPECTED_EVALUATION_SUBJECTS)
        self.assertEqual(int(subjects.loc[selected, "bcr_event"].sum()), MODULE.EXPECTED_EVALUATION_EVENTS)

    def test_stratified_c_index_excludes_cross_site_pairs(self):
        event = np.asarray([1, 0, 1, 0])
        time = np.asarray([1.0, 2.0, 1.0, 2.0])
        site = np.asarray(["A", "A", "B", "B"])
        risk = np.asarray([2.0, 1.0, 20.0, 10.0])
        self.assertEqual(MODULE.stratified_c_index(event, time, risk, site), 1.0)
        shifted = np.asarray([2.0, 1.0, -10.0, -20.0])
        self.assertEqual(MODULE.stratified_c_index(event, time, shifted, site), 1.0)

    def test_input_hash_lock(self):
        self.assertEqual(MODULE.verify_inputs(), MODULE.EXPECTED_INPUT_SHA256)

    def test_saved_outputs_preserve_claim_ceiling(self):
        config_path = OUTPUTS / "fm6_site_heldout_run_config.json"
        if not config_path.exists():
            self.skipTest("analysis outputs not generated yet")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIn(config["overall_status"], {
            "PASS_REPLICATED_SITE_HELDOUT_FUNCTIONAL_TRANSPORT",
            "PARTIAL_ENCODER_SPECIFIC_SITE_HELDOUT_EVIDENCE",
            "FAIL_OR_INCONCLUSIVE_SITE_HELDOUT_EVIDENCE",
        })
        self.assertIn("independent external T and strong H2 prohibited", config["claim_ceiling"])
        for filename, expected in config["output_sha256"].items():
            self.assertEqual(MODULE.sha256_file(OUTPUTS / filename), expected, filename)


if __name__ == "__main__":
    unittest.main()
