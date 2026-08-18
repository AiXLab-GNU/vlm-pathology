import importlib.util
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_tumor_region_detector_audit/run_fm6_tumor_region_detector_audit.py"
SPEC = importlib.util.spec_from_file_location("fm6_detector", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TumorDetectorAuditTest(unittest.TestCase):
    def test_threshold_is_deterministic(self):
        y = np.array([0, 0, 1, 1])
        score = np.array([0.1, 0.3, 0.7, 0.9])
        self.assertEqual(MODULE.choose_threshold(y, score), MODULE.choose_threshold(y, score))
        self.assertAlmostEqual(MODULE.choose_threshold(y, score)[0], 0.7)

    def test_integral_fraction(self):
        mask = np.zeros((10, 10), dtype=bool)
        mask[4:6, 4:6] = True
        result = MODULE.integral_fraction(mask, np.array([[5, 5]]), 2)
        self.assertAlmostEqual(float(result[0]), 0.25)

    def test_slide_id_removes_patch_suffix(self):
        self.assertEqual(MODULE.slide_id("16B0001_Block_Region_1.jpg"), "16B0001")


if __name__ == "__main__":
    unittest.main()
