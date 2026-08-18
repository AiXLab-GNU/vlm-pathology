import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FM5ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((OUT / "fm5_run_config.json").read_text(encoding="utf-8"))
        cls.summary = pd.read_csv(OUT / "fm5_agreement_summary.csv")
        cls.subject = pd.read_csv(OUT / "fm5_subject_comparison.csv")

    def test_existing_approval_basis_and_clean_rerun_passed(self):
        self.assertTrue(self.config["execution_authorized"])
        self.assertEqual(self.config["status"], "complete_approved_amber_scope_descriptive_fm5")
        self.assertEqual(self.config["claim_ceiling"], "internal_descriptive_cross_encoder_consistency_only")
        self.assertEqual(
            set(self.config["approval_basis"]),
            {"g8_manifest_sha256", "g9_manifest_sha256", "fm4_scope_approval_manifest_sha256"},
        )
        self.assertEqual(self.config["clean_rerun"]["status"], "pass")
        self.assertEqual(self.config["clean_rerun"]["mismatch_count"], 0)
        self.assertEqual(self.config["clean_rerun"]["deterministic_outputs_compared"], 9)

    def test_subject_prediction_and_residual_agreement_regenerate(self):
        prediction = stats.spearmanr(
            self.subject.conch_prediction, self.subject.virchow_prediction
        ).statistic
        residual = stats.spearmanr(
            self.subject.conch_residual, self.subject.virchow_residual
        ).statistic
        saved = self.summary.set_index("metric")
        self.assertAlmostEqual(prediction, saved.loc["subject_prediction_spearman", "estimate"], places=12)
        self.assertAlmostEqual(residual, saved.loc["subject_residual_spearman", "estimate"], places=12)
        self.assertTrue((saved.loc[["subject_prediction_spearman", "subject_residual_spearman"], "n_undefined_bootstrap"] == 0).all())

    def test_paired_error_interval_does_not_support_superiority(self):
        row = self.summary[self.summary.metric.eq("subject_mean_absolute_error_delta")].iloc[0]
        estimate = self.subject.absolute_error_delta_conch_minus_virchow.mean()
        self.assertAlmostEqual(estimate, row.estimate, places=12)
        self.assertLessEqual(row.ci_low, 0)
        self.assertGreaterEqual(row.ci_high, 0)
        self.assertEqual(row.interpretation, "paired_descriptive_not_encoder_superiority")

    def test_discordance_is_complete_and_technical_only(self):
        self.assertEqual(len(self.subject), 25)
        self.assertEqual(
            self.subject.discordance_class.value_counts().to_dict(),
            {"concordant_high": 12, "concordant_low": 11, "conch_only": 1, "virchow_only": 1},
        )
        self.assertEqual(
            set(self.subject.discordance_interpretation),
            {"technical_rank_stratum_not_model_specific_biology_or_superiority"},
        )

    def test_p0_representation_similarity_is_reproduced(self):
        audit = pd.read_csv(OUT / "fm5_reproducibility_audit.csv")
        self.assertTrue(audit.within_tolerance_1e_12.all())
        self.assertTrue(np.all(audit.absolute_difference <= 1e-12))

    def test_all_registered_output_hashes_match(self):
        for name, expected in self.config["output_hashes_excluding_run_config"].items():
            self.assertEqual(sha256(OUT / name), expected, name)


if __name__ == "__main__":
    unittest.main()
