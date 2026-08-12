import csv
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm1_metric_eligibility/outputs"


def rows(name, delimiter="\t"):
    with (OUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FM1MetricEligibilityTests(unittest.TestCase):
    def test_full_registry_boundary(self):
        medical = rows("medical_metric_eligibility.tsv")
        analysis = rows("analysis_measure_boundary.tsv")
        self.assertEqual(len(medical), 58)
        self.assertEqual(len({row["metric_id"] for row in medical}), 58)
        self.assertEqual(len(analysis), 73)
        self.assertTrue(all(row["eligible_as_patient_feature"] == "False" for row in analysis))

    def test_current_H1_scope_is_conservative(self):
        medical = rows("medical_metric_eligibility.tsv")
        immediate = [row["metric_id"] for row in medical if row["h1_recoverability_status"] == "eligible_descriptive_now"]
        self.assertEqual(immediate, ["candidate.tumor_fraction"])
        self.assertTrue(all(row["h1_recoverability_status"] == "prohibited_as_independent_concept_target" for row in medical if row["tier"] == "T4"))

    def test_H2_pairs_preserve_circular_exclusions_and_no_execution(self):
        pairs = rows("metric_endpoint_independence.tsv")
        self.assertEqual(len(pairs), 11)
        circular = {row["pair_id"] for row in pairs if row["circularity"] == "endpoint_defined_by_metric"}
        self.assertEqual(circular, {"H2-005", "H2-006"})
        self.assertNotIn("eligible_for_execution", {row["fm1_status"] for row in pairs})

    def test_output_hash_manifest(self):
        config = json.loads((OUT / "run_config.json").read_text(encoding="utf-8"))
        for name, expected in config["output_hashes_excluding_run_config"].items():
            self.assertEqual(sha(OUT / name), expected)

    def test_non_config_outputs_are_byte_stable_on_clean_rerun(self):
        before = {path.name: sha(path) for path in OUT.iterdir() if path.is_file() and path.name != "run_config.json"}
        script = OUT.parent / "run_fm1.py"
        subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True, capture_output=True, text=True)
        after = {path.name: sha(path) for path in OUT.iterdir() if path.is_file() and path.name != "run_config.json"}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
