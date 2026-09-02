from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from projects.quantitative_foundation_model_validation.code.lib import fm8_tier4
from projects.quantitative_foundation_model_validation.code.entrypoints import (
    run_fm8_bcr_tier4_discovery as fm8_runner,
)


class FM8Tier4CoreTests(unittest.TestCase):
    def test_known_projection_removes_fitted_direction_without_using_test_panel(self) -> None:
        rng = np.random.default_rng(7)
        panel = rng.normal(size=(80, 2))
        x = np.column_stack(
            [panel[:, 0] + 0.02 * rng.normal(size=80), panel[:, 1], rng.normal(size=(80, 4))]
        )
        projector = fm8_tier4.fit_known_projector(x[:60], panel[:60], alpha=1.0)
        residual = fm8_tier4.apply_known_projector(projector, x[60:])
        raw = projector.x_scaler.transform(x[60:])
        self.assertLess(np.linalg.norm(residual @ projector.directions), 1e-8)
        self.assertGreater(np.linalg.norm(raw @ projector.directions), 1.0)

    def test_oof_coverage_requires_each_patient_exactly_once(self) -> None:
        frame = pd.DataFrame(
            {"subject_id": ["a", "b", "c"], "prediction_count": [1, 1, 1]}
        )
        fm8_tier4.validate_oof_coverage(frame, {"a", "b", "c"})
        frame.loc[2, "prediction_count"] = 2
        with self.assertRaises(RuntimeError):
            fm8_tier4.validate_oof_coverage(frame, {"a", "b", "c"})

    def test_patient_bootstrap_preserves_undefined_draws(self) -> None:
        frame = pd.DataFrame(
            {
                "event": [1, 0, 0, 0],
                "time": [1.0, 2.0, 3.0, 4.0],
                "baseline_risk": [4.0, 3.0, 2.0, 1.0],
                "latent_risk": [4.0, 3.0, 2.0, 1.0],
                "additive_risk": [4.0, 3.0, 2.0, 1.0],
                "interaction_risk": [4.0, 3.0, 2.0, 1.0],
            }
        )
        summary, draws = fm8_tier4.patient_bootstrap_performance(
            frame, cohort="toy", encoder="toy", draws=200, seed=13
        )
        self.assertEqual(len(draws), 200)
        self.assertGreater(int(summary.n_undefined.max()), 0)
        self.assertTrue((summary.n_valid + summary.n_undefined == 200).all())

    def test_functional_roles_are_multilabel_and_shortcut_caps_qualification(self) -> None:
        status = fm8_tier4.assign_functional_roles(
            source={
                "latent_only": 0.61,
                "delta_additive": 0.005,
                "delta_interaction": 0.02,
                "interaction_coefficient": 0.4,
                "positive_fold_count": 5,
            },
            external={
                "latent_only": 0.58,
                "delta_additive": 0.004,
                "delta_interaction": 0.01,
            },
            shortcut_status="PARTIAL_NOT_EVALUABLE",
        )
        self.assertEqual(status["standalone_status"], "supported")
        self.assertEqual(status["complementary_status"], "supported")
        self.assertEqual(status["interaction_status"], "supported")
        self.assertEqual(status["redundancy_status"], "supported")
        self.assertEqual(
            status["external_reproduction_status"],
            "not_qualified_shortcut_unresolved",
        )

    def test_endpoint_lane_readiness_keeps_cancer_and_grading_separate(self) -> None:
        readiness = fm8_tier4.endpoint_lane_readiness()
        self.assertEqual(set(readiness.endpoint), {"bcr", "cancer_presence", "grading"})
        self.assertEqual(
            readiness.set_index("endpoint").loc["bcr", "status"], "READY"
        )
        self.assertTrue(
            (readiness.set_index("endpoint").loc[["cancer_presence", "grading"], "status"] == "NOT_READY").all()
        )
        self.assertNotEqual(
            readiness.set_index("endpoint").loc["cancer_presence", "label_contract"],
            readiness.set_index("endpoint").loc["grading", "label_contract"],
        )

    def test_one_standard_error_prefers_smaller_rank_and_stronger_alpha(self) -> None:
        table = pd.DataFrame(
            [
                {"rank": 16, "alpha": 1.0, "mean_score": 0.65, "score_se": 0.03},
                {"rank": 4, "alpha": 100.0, "mean_score": 0.63, "score_se": 0.02},
                {"rank": 8, "alpha": 10.0, "mean_score": 0.64, "score_se": 0.02},
            ]
        )
        selected = fm8_tier4.select_one_se(table)
        self.assertEqual(int(selected["rank"]), 4)
        self.assertEqual(float(selected["alpha"]), 100.0)

    def test_evaluable_acquisition_domain_alert_fails_shortcut_gate(self) -> None:
        base = {
            name: np.linspace(0.0, 1.0, 12)
            for name in [
                "isup", "mean_tissue_fraction", "mean_mpp", "log1p_n_slides",
                "rgb_r_mean", "rgb_g_mean", "rgb_b_mean", "rgb_r_std", "rgb_g_std",
                "rgb_b_std", "brightness_mean", "saturation_mean", "od_r_mean",
                "od_g_mean", "od_b_mean",
            ]
        }
        source = pd.DataFrame(base)
        source["latent_risk"] = np.r_[np.zeros(6), np.ones(6)]
        source["site"] = ["a"] * 6 + ["b"] * 6
        source["scanner_group"] = "single"
        source["compression_group"] = "single"
        external = pd.DataFrame(base)
        external["latent_risk"] = np.linspace(1.0, 0.0, 12)
        external["site"] = "not_available"
        external["scanner_group"] = "not_available"
        external["compression_group"] = "not_available"
        _, status = fm8_runner.shortcut_audit(source, external, "toy")
        self.assertEqual(status, "FAIL_MATERIAL_ASSOCIATION")


if __name__ == "__main__":
    unittest.main()
