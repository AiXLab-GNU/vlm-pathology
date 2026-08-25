"""Focused reproducibility checks for the read-only FM8 entry audit."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "projects/quantitative_foundation_model_validation"
MILESTONE = PROJECT / "milestones/fm8_residual_discovery_entry_audit"
SCRIPT = MILESTONE / "run_fm8_residual_discovery_entry_audit.py"
REFERENCE = MILESTONE / "outputs"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class FM8ResidualDiscoveryEntryAuditTest(unittest.TestCase):
    def test_no_go_bundle_is_exactly_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fm8-entry-audit-test-") as temp:
            output = Path(temp)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output-dir",
                    str(output),
                    "--reference-dir",
                    str(REFERENCE),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("FM8 entry audit: NO-GO", completed.stdout)
            gates = {row["gate_id"]: row for row in read_csv(output / "fm8_gate_decision_matrix.csv")}
            self.assertEqual(9, len(gates))
            self.assertEqual("FAIL", gates["G4"]["status"])
            self.assertEqual("NOT-EVALUABLE", gates["G6"]["status"])
            self.assertEqual("PASS", gates["G7"]["status"])

            availability = read_csv(output / "fm8_artifact_availability_matrix.csv")
            self.assertEqual(10, len(availability))
            self.assertEqual(5, len({row["cohort"] for row in availability}))
            self.assertEqual({"CONCH", "Virchow"}, {row["encoder"] for row in availability})

            source_integrity = read_csv(output / "fm8_source_integrity_audit.csv")
            self.assertEqual(13, len(source_integrity))
            self.assertTrue(all(row["status"] == "PASS" for row in source_integrity))
            self.assertTrue(all(int(row["duplicate_key_rows"]) == 0 for row in source_integrity))
            self.assertTrue(all(int(row["patient_fold_violations"]) == 0 for row in source_integrity))

            comparison = read_csv(output / "fm8_clean_rerun_comparison.csv")
            self.assertEqual(11, len(comparison))
            self.assertTrue(all(row["status"] == "PASS_EXACT_HASH" for row in comparison))

            config = json.loads((output / "fm8_entry_audit_run_config.json").read_text())
            reference_config = json.loads((REFERENCE / "fm8_entry_audit_run_config.json").read_text())
            self.assertEqual("NO-GO", config["decision"])
            self.assertEqual("PASS_EXACT_HASH", config["clean_rerun_status"])
            self.assertTrue(config["source_integrity_all_pass"])
            self.assertEqual(reference_config["output_sha256"], config["output_sha256"])


if __name__ == "__main__":
    unittest.main()
