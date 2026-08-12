import csv
import json
import tempfile
import unittest
from pathlib import Path

from projects.quantitative_foundation_model_validation.governance_portal.governance import (
    append_fm4_scope_approval,
    finalize_fm4_scope,
    fm4_scope_status,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm4_concept_benchmark/outputs"


def rows(name):
    with (OUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FM4PreparationTests(unittest.TestCase):
    def test_execution_is_not_authorized(self):
        config = json.loads((OUT / "run_config.json").read_text())
        self.assertEqual(config["status"], "prepared_pending_research_lead_scope_approval")
        self.assertFalse(config["execution_authorized"])

    def test_shared_folds_are_subject_grouped(self):
        manifest = rows("fm4_shared_fold_manifest.csv")
        self.assertEqual(len(manifest), 25)
        self.assertEqual({int(row["outer_fold"]) for row in manifest}, set(range(5)))
        self.assertEqual(sum(int(row["paired_tiles"]) for row in manifest), 1218)
        self.assertTrue(all(row["shared_by_encoders"] == "True" for row in manifest))

    def test_primary_family_is_scope_capped(self):
        primary = [row for row in rows("analysis_family.csv") if row["outcome_role"] == "primary_exploratory"]
        self.assertEqual({row["encoder"] for row in primary}, {"CONCH", "Virchow"})
        self.assertEqual({row["target"] for row in primary}, {"tumor_fraction"})
        self.assertTrue(all(row["claim_ceiling"] == "internal_descriptive_recoverability_only" for row in primary))

    def test_power_plan_flags_available_cohort_as_feasibility(self):
        available = next(row for row in rows("power_precision_plan.csv") if row["scenario"] == "available")
        self.assertEqual(available["n_subjects"], "25")
        self.assertGreater(float(available["minimum_detectable_abs_rho_80pct_power"]), 0.55)
        self.assertEqual(available["interpretation"], "feasibility_only_large_effects")

    def test_scientific_gates_remain_closed(self):
        checklist = {row["requirement"]: row["status"] for row in rows("fm4_entry_checklist.csv")}
        self.assertEqual(checklist["measurement repeatability"], "not_met")
        self.assertEqual(checklist["independent metric-endpoint pair for H2"], "not_met")
        self.assertEqual(checklist["research-lead FM4 scope approval"], "pending")

    def test_scope_approval_is_append_only_and_finalizable(self):
        payload = {
            "reviewer_name": "Jin Hyun Kim",
            "signature": "Jin Hyun Kim",
            "decision": "approve",
            "reviewed_fm4_packet": True,
            "accept_exploratory_scope": True,
            "accept_power_limit": True,
            "accept_fm4_prohibitions": True,
            "fm4_identity_attested": True,
            "notes": "test-only approval in a temporary ledger",
        }
        with tempfile.TemporaryDirectory() as directory:
            records_dir = Path(directory)
            record = append_fm4_scope_approval(payload, records_dir=records_dir)
            self.assertEqual(record["decision"], "approve")
            self.assertTrue(fm4_scope_status(records_dir)["ready_to_finalize"])
            manifest = finalize_fm4_scope(records_dir=records_dir)
            self.assertEqual(manifest["status"], "approved_exploratory_descriptive_fm4")
            with self.assertRaises(Exception):
                append_fm4_scope_approval(payload, records_dir=records_dir)


if __name__ == "__main__":
    unittest.main()
