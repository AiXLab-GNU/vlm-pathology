"""Saved-source and manifest contracts for active submission figures."""
from __future__ import annotations

import tempfile
import unittest
import hashlib
from pathlib import Path

import pandas as pd

from paper.figures import fig7_marker7_transfer as fig7
from paper.figures import fig8_marker7_survival_curves as fig8
from paper.submission_config import MAIN_FIGURES, SUPPLEMENT_FIGURES


ROOT = Path(__file__).resolve().parents[1]


class Marker7FinalFigureTests(unittest.TestCase):
    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_fig7_loads_complete_r4_saved_sources(self):
        summary, deltas = fig7.load_sources(
            ROOT / "models/marker7_survival_common_cohort_summary.csv",
            ROOT / "models/marker7_survival_paired_deltas.csv",
        )
        self.assertEqual(len(summary), 44)
        self.assertEqual(len(deltas), 20)
        self.assertEqual(set(summary["endpoint_id"]), {
            "E04_reconstructed_with_tumor", "E08_official_pfi",
        })
        self.assertTrue((deltas["n_patients"] == 153).all())

    def test_fig7_rejects_missing_contrast(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deltas.csv"
            pd.read_csv(ROOT / "models/marker7_survival_paired_deltas.csv").iloc[:-1].to_csv(
                path, index=False
            )
            with self.assertRaisesRegex(ValueError, "20 rows"):
                fig7.load_sources(
                    ROOT / "models/marker7_survival_common_cohort_summary.csv", path
                )

    def test_fig8_loads_saved_auc_and_calibration_sources(self):
        auc, calibration = fig8.load_sources(
            ROOT / "models/marker7_td_auc_curve.csv",
            ROOT / "models/marker7_calibration_3y_5y.csv",
        )
        self.assertEqual(len(auc), 17)
        self.assertEqual(len(calibration), 10)
        self.assertEqual(set(calibration["horizon_years"]), {3.0, 5.0})

    def test_fig8_rejects_duplicate_calibration_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.csv"
            frame = pd.read_csv(ROOT / "models/marker7_calibration_3y_5y.csv")
            pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "10 rows"):
                fig8.load_sources(ROOT / "models/marker7_td_auc_curve.csv", path)

    def test_final_marker7_pdf_renderers_are_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, renderer, sources in (
                ("fig7", fig7.render, (
                    ROOT / "models/marker7_survival_common_cohort_summary.csv",
                    ROOT / "models/marker7_survival_paired_deltas.csv",
                )),
                ("fig8", fig8.render, (
                    ROOT / "models/marker7_td_auc_curve.csv",
                    ROOT / "models/marker7_calibration_3y_5y.csv",
                )),
            ):
                first, second = root / f"{name}-1.pdf", root / f"{name}-2.pdf"
                renderer(*sources, first)
                renderer(*sources, second)
                self.assertEqual(self._sha(first), self._sha(second))

    def test_submission_configuration_has_six_main_and_four_supplementary_figures(self):
        self.assertEqual([item.figure_id for item in MAIN_FIGURES], [
            "F1", "F2", "F3", "F4", "F5", "F6",
        ])
        self.assertEqual([item.figure_id for item in SUPPLEMENT_FIGURES], [
            "SF1", "SF2", "SF3", "SF4",
        ])
        for item in (*MAIN_FIGURES, *SUPPLEMENT_FIGURES):
            self.assertTrue((ROOT / item.script).is_file())
            self.assertTrue(all((ROOT / source).is_file() for source in item.sources))
            self.assertTrue((ROOT / item.manuscript).is_file())


if __name__ == "__main__":
    unittest.main()
