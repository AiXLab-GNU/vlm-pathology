import csv
import hashlib
import json
import unittest
from pathlib import Path

from projects.quantitative_foundation_model_validation.governance_portal.governance import (
    fm4_scope_status,
)
from projects.quantitative_foundation_model_validation.milestones.fm5_cross_model_comparison.run_fm5_comparison import (
    verify_entry,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm5_cross_model_comparison/outputs"


def rows(name):
    with (OUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FM5PreparationTests(unittest.TestCase):
    def test_entry_contract_is_ready_under_existing_approval(self):
        config = json.loads((OUT / "fm5_entry_run_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["status"], "ready_existing_approval_scope_locked")
        self.assertTrue(config["execution_authorized"])
        self.assertEqual(config["counts"]["paired_tiles"], 1218)
        self.assertEqual(config["counts"]["subjects"], 25)
        self.assertEqual(config["claim_ceiling"], "internal_descriptive_cross_encoder_consistency_only")

    def test_source_manifest_hashes_are_current(self):
        for row in rows("fm5_source_manifest.csv"):
            path = ROOT / row["canonical_path"]
            self.assertTrue(path.is_file(), row["canonical_path"])
            self.assertEqual(sha256(path), row["sha256"], row["canonical_path"])

    def test_analysis_family_is_paired_and_descriptive_only(self):
        family = rows("fm5_analysis_family.csv")
        primary = [row for row in family if row["family_id"] == "FM5-PRIMARY-DESCRIPTIVE"]
        self.assertEqual(len(primary), 4)
        self.assertTrue(all(row["replicates"] == "2000" for row in primary))
        self.assertTrue(all(row["multiplicity"] == "descriptive_only_no_p_or_q_values" for row in primary))
        self.assertTrue(all(row["claim_ceiling"] == "internal_descriptive_cross_encoder_consistency_only" for row in primary))

    def test_discordance_is_a_four_stratum_technical_definition(self):
        discordance = rows("fm5_discordance_definition.csv")
        self.assertEqual(
            {row["class"] for row in discordance},
            {"concordant_high", "concordant_low", "conch_only", "virchow_only"},
        )
        self.assertTrue(all("not" in row["interpretation"] for row in discordance))

    def test_fm4_approval_exists(self):
        self.assertTrue(fm4_scope_status()["finalized"])

    def test_analysis_entry_point_uses_existing_approval_basis(self):
        approval = verify_entry()
        self.assertEqual(
            set(approval),
            {"g8_manifest_sha256", "g9_manifest_sha256", "fm4_scope_approval_manifest_sha256"},
        )


if __name__ == "__main__":
    unittest.main()
