import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm4_concept_benchmark/outputs"
RECORDS = ROOT / "projects/quantitative_foundation_model_validation/preexperiment/governance_records"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FM4BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((OUT / "benchmark_run_config.json").read_text())
        cls.oof = pd.read_csv(OUT / "fm4_oof_predictions.csv")
        cls.subject = pd.read_csv(OUT / "fm4_subject_predictions.csv")
        cls.summary = pd.read_csv(OUT / "fm4_summary.csv")

    def test_execution_was_approved_and_clean_rerun_passed(self):
        self.assertTrue(self.config["execution_authorized"])
        self.assertEqual(
            self.config["status"], "complete_approved_exploratory_descriptive_h1"
        )
        self.assertEqual(self.config["claim_ceiling"], "internal_descriptive_recoverability_only")
        self.assertEqual(self.config["clean_rerun"]["status"], "pass")
        self.assertEqual(self.config["clean_rerun"]["mismatch_count"], 0)
        self.assertEqual(self.config["passing_encoders"], ["CONCH", "Virchow"])
        self.assertEqual(
            self.config["source_hashes"]["fm4_scope_approval_manifest.json"],
            sha256(RECORDS / "fm4_scope_approval_manifest.json"),
        )

    def test_oof_predictions_are_complete_and_subject_grouped(self):
        self.assertEqual(len(self.oof), 2 * 1218)
        self.assertEqual(set(self.oof.encoder), {"CONCH", "Virchow"})
        self.assertEqual(self.oof.groupby("encoder").sample_id.nunique().to_dict(), {"CONCH": 1218, "Virchow": 1218})
        self.assertEqual(int(self.oof.groupby(["encoder", "subject_id"]).outer_fold.nunique().max()), 1)
        self.assertTrue(np.isfinite(self.oof.truth).all())
        self.assertTrue(np.isfinite(self.oof.prediction).all())

    def test_subject_predictions_regenerate_primary_results(self):
        self.assertEqual(len(self.subject), 50)
        primary = self.summary[
            self.summary.family_id.eq("FM4-H1-TUMOR-SHARED")
            & self.summary.metric_name.eq("spearman")
        ].set_index("encoder")
        self.assertEqual(set(primary.index), {"CONCH", "Virchow"})
        for encoder in ("CONCH", "Virchow"):
            rows = self.subject[self.subject.encoder.eq(encoder)]
            estimate = stats.spearmanr(
                rows.truth_subject_mean, rows.prediction_subject_mean
            ).statistic
            self.assertAlmostEqual(float(primary.loc[encoder, "estimate"]), float(estimate), places=12)
            self.assertEqual(int(primary.loc[encoder, "n_subjects"]), 25)
            self.assertEqual(int(primary.loc[encoder, "n_valid_bootstrap"]), 2000)
            self.assertEqual(int(primary.loc[encoder, "n_undefined_bootstrap"]), 0)
            self.assertLess(float(primary.loc[encoder, "empirical_q"]), 0.05)
            self.assertTrue(bool(primary.loc[encoder, "gate_exceedance"]))

    def test_cross_encoder_delta_is_descriptive_not_superiority(self):
        deltas = pd.read_csv(OUT / "fm4_paired_deltas.csv")
        row = deltas[
            deltas.analysis_unit.eq("subject_mean")
            & deltas.metric_name.eq("spearman")
        ].iloc[0]
        self.assertLessEqual(float(row.ci_low), 0)
        self.assertGreaterEqual(float(row.ci_high), 0)
        self.assertEqual(row.interpretation, "descriptive_paired_delta_not_encoder_superiority")

    def test_capacity_sensitivity_is_secondary_and_reproducible(self):
        capacity = pd.read_csv(OUT / "fm4_capacity_sensitivity.csv")
        predictions = pd.read_csv(OUT / "fm4_capacity_oof_predictions.csv")
        self.assertEqual(set(capacity.sensitivity_rank), {64})
        self.assertEqual(set(capacity.outcome_role), {"secondary_capacity_sensitivity_not_gate"})
        self.assertEqual(len(predictions), 2 * 1218)
        for encoder in ("CONCH", "Virchow"):
            rows = predictions[predictions.encoder.eq(encoder)]
            aggregated = rows.groupby("subject_id", as_index=False).agg(
                truth=("truth", "mean"), prediction=("prediction", "mean")
            )
            estimate = stats.spearmanr(aggregated.truth, aggregated.prediction).statistic
            saved = capacity[
                capacity.encoder.eq(encoder)
                & capacity.analysis_unit.eq("subject_mean")
                & capacity.metric_name.eq("spearman")
            ].iloc[0]
            self.assertAlmostEqual(float(saved.sensitivity_estimate), float(estimate), places=12)

    def test_all_registered_output_hashes_match(self):
        for name, expected in self.config["output_hashes_excluding_run_config"].items():
            self.assertEqual(sha256(OUT / name), expected, name)


if __name__ == "__main__":
    unittest.main()
