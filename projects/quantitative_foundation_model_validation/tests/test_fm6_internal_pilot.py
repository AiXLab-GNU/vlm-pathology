from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot/outputs"
SOURCE = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/tcga_prad_current_gdc_bcr"
SECONDARY = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/prad_pancan_clinical.json"


class FM6InternalPilotTest(unittest.TestCase):
    def test_locked_source_universe(self) -> None:
        subjects = pd.read_csv(SOURCE / "development_subjects.csv")
        slides = pd.read_csv(SOURCE / "development_slides.csv")
        folds = pd.read_csv(SOURCE / "development_outer_folds.csv")
        self.assertEqual(len(subjects), 392)
        self.assertEqual(int(subjects.bcr_event.sum()), 80)
        self.assertEqual(len(slides), 437)
        self.assertTrue(slides.local_complete.all())
        self.assertEqual(folds.case_id.nunique(), 392)
        self.assertEqual(sorted(folds.outer_fold.unique().tolist()), [0, 1, 2, 3, 4])

    def test_outcome_blind_tile_manifest(self) -> None:
        manifest = pd.read_csv(OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv")
        self.assertEqual(len(manifest), 27_968)
        self.assertEqual(manifest.file_id.nunique(), 437)
        self.assertEqual(manifest.case_id.nunique(), 392)
        self.assertTrue(manifest.tile_id.is_unique)
        self.assertTrue((manifest.groupby("file_id").size() == 64).all())
        self.assertTrue((manifest.physical_fov_um == 394.24).all())
        self.assertFalse({"bcr_event", "bcr_time_days", "isup_grade_group"} & set(manifest.columns))

    def test_secondary_clinical_source_hash(self) -> None:
        observed = hashlib.sha256(SECONDARY.read_bytes()).hexdigest()
        self.assertEqual(observed, "3e2ec994c7ca87638d99ccc5a2287430613a749143d01a3a36ae36191bbc4241")


if __name__ == "__main__":
    unittest.main()
