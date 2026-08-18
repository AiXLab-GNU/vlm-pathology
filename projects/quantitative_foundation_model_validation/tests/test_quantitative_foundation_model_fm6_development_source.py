import csv
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MILESTONE = PROJECT_ROOT / "milestones" / "fm6_development_source_package"
OUTPUTS = MILESTONE / "outputs"
PREPROCESSING_PROTOCOL = (
    PROJECT_ROOT
    / "docs"
    / "protocols"
    / "fm6-tcga-wsi-preprocessing-and-aggregation-protocol-ko.md"
)
HEADER_SCRIPT = MILESTONE / "audit_fm6_tcga_wsi_headers.py"
HEADER_SPEC = importlib.util.spec_from_file_location("audit_fm6_tcga_wsi_headers", HEADER_SCRIPT)
HEADER_MODULE = importlib.util.module_from_spec(HEADER_SPEC)
assert HEADER_SPEC.loader is not None
HEADER_SPEC.loader.exec_module(HEADER_MODULE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class Fm6DevelopmentSourcePackageTests(unittest.TestCase):
    def test_source_package_is_locked_but_h2_remains_closed(self):
        config = json.loads(
            (OUTPUTS / "fm6_development_source_run_config.json").read_text()
        )
        summary = config["summary"]
        self.assertIn(
            config["status"],
            {
                "DEVELOPMENT_SOURCE_HASH_LOCKED_ACQUISITION_AND_HARMONIZATION_HOLD_H2_LOCKED",
                "DEVELOPMENT_SOURCE_PAYLOAD_VERIFIED_PREPROCESSING_GATE_H2_LOCKED",
            },
        )
        self.assertFalse(config["development_analysis_ready"])
        self.assertFalse(config["h2_unlocked"])
        self.assertFalse(config["claim_ceiling_changed"])
        self.assertEqual((summary["n_subjects"], summary["n_events"]), (392, 80))
        self.assertEqual(
            (summary["n_treatment_documented"], summary["n_treatment_documented_events"]),
            (308, 64),
        )
        self.assertGreaterEqual(summary["missing_local_slide_bytes"], 0)
        if config["status"].startswith("DEVELOPMENT_SOURCE_PAYLOAD_VERIFIED"):
            self.assertEqual(summary["n_local_slides"], 437)
            self.assertEqual(summary["n_content_verified_slides"], 437)
            eligibility = read_csv(OUTPUTS / "fm6_tcga_development_eligibility.csv")[0]
            self.assertNotIn("remaining WSI payload", eligibility["blocking_reason"])

    def test_aperio_header_fields_are_parsed_without_outcome_input(self):
        description = (
            "Aperio Image Library v12|AppMag = 40|ScanScope ID = SS123|MPP = 0.2527"
        )
        self.assertEqual(HEADER_MODULE.aperio_value(description, "AppMag"), "40")
        self.assertEqual(HEADER_MODULE.aperio_value(description, "ScanScope ID"), "SS123")
        self.assertEqual(HEADER_MODULE.aperio_value(description, "MPP"), "0.2527")

    def test_harmonization_forbids_patient_level_pooling(self):
        rows = read_csv(OUTPUTS / "fm6_tcga_chimera_endpoint_harmonization.csv")
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["primary_pooling"] == "prohibited" for row in rows))
        event = next(row for row in rows if row["field"] == "bcr_event_definition")
        self.assertEqual(event["status"], "not_proven_threshold_equivalent")

    def test_preprocessing_protocol_prevents_slide_count_and_tumor_truth_leakage(self):
        text = PREPROCESSING_PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("환자마다 총 가중치 1", text)
        self.assertIn("동일 가중 mean", text)
        self.assertIn("weakly supervised attention", text)
        self.assertIn("독립 tumor truth", text)
        self.assertIn("394.24 micrometre", text)

    def test_tracked_output_hashes_match_run_config(self):
        config = json.loads(
            (OUTPUTS / "fm6_development_source_run_config.json").read_text()
        )
        for filename, expected in config["output_sha256"].items():
            self.assertEqual(sha256_file(OUTPUTS / filename), expected, filename)

    def test_outer_folds_balance_event_grade_and_treatment_at_subject_level(self):
        rows = read_csv(OUTPUTS / "fm6_tcga_outer_fold_balance.csv")
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(int(row["n_subjects"]) for row in rows), 392)
        self.assertEqual({int(row["n_events"]) for row in rows}, {16})
        treatment = [int(row["n_treatment_documented"]) for row in rows]
        self.assertLessEqual(max(treatment) - min(treatment), 1)
        for grade in range(1, 6):
            counts = [int(row[f"n_isup_{grade}"]) for row in rows]
            self.assertLessEqual(max(counts) - min(counts), 2)

    def test_all_locked_wsi_pass_outcome_blind_header_thumbnail_and_mpp_qc(self):
        rows = read_csv(OUTPUTS / "fm6_tcga_wsi_header_qc_summary.csv")
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["status"] == "PASS" for row in rows))
        self.assertTrue(all(int(row["value"]) == 437 for row in rows))
        self.assertTrue(all(int(row["denominator"]) == 437 for row in rows))


if __name__ == "__main__":
    unittest.main()
