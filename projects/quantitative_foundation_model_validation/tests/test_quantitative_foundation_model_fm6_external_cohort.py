import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "milestones"
    / "fm6_external_cohort_acquisition"
    / "run_fm6_external_cohort_acquisition.py"
)
OUTPUTS = SCRIPT.parent / "outputs"
SPEC = importlib.util.spec_from_file_location("run_fm6_external_cohort_acquisition", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Fm6ExternalCohortAcquisitionTests(unittest.TestCase):
    def test_saved_handoff_keeps_semantic_qc_and_h2_locked(self):
        config = json.loads(
            (OUTPUTS / "fm6_external_cohort_run_config.json").read_text(
                encoding="utf-8"
            )
        )
        summary = config["summary"]
        self.assertEqual(config["bcr_time_unit"], "months")
        self.assertFalse(config["claim_ceiling_changed"])
        self.assertFalse(config["h2_unlocked"])
        self.assertEqual(summary["n_subjects"], 95)
        self.assertEqual(summary["n_events"], 27)
        self.assertEqual(summary["n_isup_gleason_concordant"], 92)
        self.assertEqual(summary["n_isup_gleason_discordant"], 3)
        self.assertEqual(summary["min_wsi_per_subject"], 1)
        self.assertEqual(summary["max_wsi_per_subject"], 12)
        for filename, expected_sha256 in config["output_sha256"].items():
            self.assertEqual(
                MODULE.sha256_file(OUTPUTS / filename),
                expected_sha256,
                filename,
            )

    def test_standard_grade_group_derivation_preserves_source_discordance(self):
        self.assertEqual(MODULE.derive_isup_grade_group(3, 2), 1)
        self.assertEqual(MODULE.derive_isup_grade_group(3, 4), 2)
        self.assertEqual(MODULE.derive_isup_grade_group(4, 3), 3)
        self.assertEqual(MODULE.derive_isup_grade_group(4, 4), 4)
        self.assertEqual(MODULE.derive_isup_grade_group(5, 4), 5)

    def test_clinical_normalization_uses_months_and_preserves_source_states(self):
        payload = {
            "age_at_prostatectomy": 65,
            "primary_gleason": 3,
            "secondary_gleason": 3,
            "ISUP": 2,
            "pre_operative_PSA": 7.0,
            "BCR": "0.0",
            "time_to_follow-up/BCR": 65.0,
            "pT_stage": "2c",
            "positive_lymph_nodes": "x",
            "capsular_penetration": "0",
            "positive_surgical_margins": 1,
            "invasion_seminal_vesicles": "0",
            "lymphovascular_invasion": "0.0",
            "earlier_therapy": "unknown",
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "1003.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            rows = MODULE.parse_clinical(
                [
                    {
                        "key": "v2/task1/clinical_data/1003.json",
                        "path": source,
                    }
                ]
            )
        self.assertEqual(rows[0]["time_to_follow_up_or_bcr_months"], 65.0)
        self.assertNotIn("time_to_follow_up_or_bcr_years", rows[0])
        self.assertEqual(rows[0]["bcr_time_unit"], "months")
        self.assertEqual(rows[0]["isup_gleason_consistency"], "source_discordant")
        self.assertEqual(rows[0]["bcr_psa_source_state"], "missing_key")
        self.assertEqual(rows[0]["tertiary_gleason_source_state"], "missing_key")
        self.assertEqual(rows[0]["positive_lymph_nodes"], "x")
        self.assertEqual(rows[0]["earlier_therapy_state"], "unknown")

    def test_offline_inventory_verifier_detects_post_acquisition_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "local-data" / "1003.json"
            source.parent.mkdir()
            source.write_bytes(b"locked-source")
            inventory = root / "source_inventory.csv"
            MODULE.write_csv(
                inventory,
                [
                    {
                        "remote_key": "v2/task1/clinical_data/1003.json",
                        "role": "clinical_json",
                        "remote_size": source.stat().st_size,
                        "etag": "etag",
                        "last_modified": "2025-01-01T00:00:00Z",
                        "local_relative_path": "local-data/1003.json",
                        "local_complete": True,
                        "sha256": MODULE.sha256_file(source),
                    }
                ],
                [
                    "remote_key",
                    "role",
                    "remote_size",
                    "etag",
                    "last_modified",
                    "local_relative_path",
                    "local_complete",
                    "sha256",
                ],
            )
            passed = MODULE.verify_local_inventory_hashes(inventory, root)
            source.write_bytes(b"changed-source")
            failed = MODULE.verify_local_inventory_hashes(inventory, root)
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(failed["status"], "FAIL")
        self.assertEqual(failed["failures"][0]["reason"], "size_mismatch")

    def test_object_roles_exclude_non_source_embeddings(self):
        self.assertEqual(
            MODULE.object_role("v2/task1/clinical_data/1003.json"), "clinical_json"
        )
        self.assertEqual(
            MODULE.object_role("v2/task1/pathology/images/1003/1003_1.tif"),
            "prostatectomy_wsi",
        )
        self.assertEqual(
            MODULE.object_role("v2/task1/pathology/images/1003/1003_1_tissue.tif"),
            "tissue_mask",
        )
        self.assertIsNone(
            MODULE.object_role("v2/task1/pathology/features/embeddings/1003_1.pt")
        )

    def test_local_path_rejects_cross_prefix_key(self):
        with self.assertRaises(ValueError):
            MODULE.local_path_for_key("v2/task2/clinical_data/1003.json")

    def test_build_local_inventory_preserves_remote_lock(self):
        original_root = MODULE.LOCAL_ROOT
        original_inventory = MODULE.LOCAL_INVENTORY
        original_repository_root = MODULE.REPOSITORY_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                MODULE.REPOSITORY_ROOT = Path(directory)
                MODULE.LOCAL_ROOT = Path(directory) / "local-data"
                MODULE.LOCAL_INVENTORY = Path(directory) / "source_inventory.csv"
                rows = MODULE.build_local_inventory(
                    [
                        {
                            "key": "v2/task1/clinical_data/1003.json",
                            "size": 432,
                            "etag": "abc",
                            "last_modified": "2025-01-01T00:00:00Z",
                        }
                    ],
                    [],
                )
                self.assertEqual(rows[0]["remote_size"], 432)
                self.assertFalse(rows[0]["local_complete"])
        finally:
            MODULE.LOCAL_ROOT = original_root
            MODULE.LOCAL_INVENTORY = original_inventory
            MODULE.REPOSITORY_ROOT = original_repository_root


if __name__ == "__main__":
    unittest.main()
