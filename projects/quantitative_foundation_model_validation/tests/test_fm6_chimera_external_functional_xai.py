from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "projects/quantitative_foundation_model_validation/milestones"
    / "fm6_chimera_external_functional_validation"
    / "run_fm6_chimera_external_functional_xai.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_fm6_chimera_external_functional_xai", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FM6ChimeraExternalFunctionalXAITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.slides, cls.clinical = MODULE.source_membership(full_hash=False)

    def test_input_manifest_and_hash_lock(self) -> None:
        self.assertEqual(MODULE.verify_locked_inputs(), MODULE.EXPECTED_INPUT_SHA256)
        self.assertEqual(
            MODULE.sha256_file(MODULE.SOURCE_INVENTORY),
            MODULE.EXPECTED_INPUT_SHA256["source_inventory.csv"],
        )
        self.assertEqual(
            MODULE.sha256_file(MODULE.CLINICAL),
            MODULE.EXPECTED_INPUT_SHA256["normalized_clinical.csv"],
        )

    def test_locked_membership_and_patient_slide_linkage(self) -> None:
        self.assertEqual(len(self.clinical), 95)
        self.assertEqual(self.clinical.subject_id.nunique(), 95)
        self.assertEqual(int(self.clinical.bcr_event.sum()), 27)
        self.assertEqual(len(self.slides), 190)
        self.assertEqual(self.slides.slide_id.nunique(), 190)
        self.assertEqual(self.slides.subject_id.nunique(), 95)
        self.assertFalse(self.slides.duplicated(["subject_id", "slide_id"]).any())
        self.assertEqual(
            set(self.slides.subject_id.astype(str)),
            set(self.clinical.subject_id.astype(str)),
        )
        self.assertEqual(
            int(self.clinical.isup_gleason_consistency.eq("concordant").sum()), 92
        )

    def test_stable_rng_is_slide_specific_and_repeatable(self) -> None:
        first = MODULE.stable_rng("1003_1").integers(0, 1_000_000, 12)
        second = MODULE.stable_rng("1003_1").integers(0, 1_000_000, 12)
        other = MODULE.stable_rng("1010_1").integers(0, 1_000_000, 12)
        np.testing.assert_array_equal(first, second)
        self.assertFalse(np.array_equal(first, other))

    def test_crop_candidate_identity_has_no_duplicate_coordinates(self) -> None:
        mask = np.ones((100, 100), dtype=np.uint8)
        first = MODULE.candidate_coordinates(mask, 400, 400, 40, 0.35, 1)
        second = MODULE.candidate_coordinates(mask, 400, 400, 40, 0.35, 1)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len({(x, y) for x, y, _ in first}))

    def test_multi_slide_patient_aggregation_is_equal_weight(self) -> None:
        rows = []
        values = []
        embedding_row = 0
        for subject in range(95):
            slide_values = [1.0, 3.0] if subject == 0 else [float(subject)]
            for slide_number, slide_value in enumerate(slide_values):
                slide_id = f"{subject:04d}_{slide_number}"
                for tile_rank in range(MODULE.MAX_TILES):
                    rows.append(
                        {
                            "embedding_row": embedding_row,
                            "subject_id": f"{subject:04d}",
                            "slide_id": slide_id,
                            "tile_id": f"{slide_id}:{tile_rank:03d}",
                        }
                    )
                    values.append([slide_value, slide_value * 2])
                    embedding_row += 1
        patient, aggregated = MODULE.aggregate_patient_embeddings(
            pd.DataFrame(rows), np.asarray(values, dtype=float)
        )
        index = patient.index[patient.subject_id.eq("0000")][0]
        np.testing.assert_allclose(aggregated[index], [2.0, 4.0])
        self.assertEqual(int(patient.loc[index, "n_slides"]), 2)

    def test_censoring_c_index_convention(self) -> None:
        event = np.asarray([1, 1, 0, 0])
        follow_up = np.asarray([1.0, 2.0, 3.0, 4.0])
        perfect_risk = np.asarray([4.0, 3.0, 2.0, 1.0])
        reversed_risk = perfect_risk[::-1]
        self.assertEqual(
            MODULE.SITE_ANALYSIS.ordinary_c_index(event, follow_up, perfect_risk), 1.0
        )
        self.assertEqual(
            MODULE.SITE_ANALYSIS.ordinary_c_index(event, follow_up, reversed_risk), 0.0
        )

    def test_cause_state_requires_full_head_before_erasure(self) -> None:
        row = {
            "isup_spearman_all95": 0.5,
            "isup_spearman_all95_ci_low": 0.2,
            "full_c_index": 0.49,
            "full_c_index_ci_low": 0.4,
            "target_delta_use": 0.2,
            "target_delta_use_ci_low": 0.1,
            "functional_erasure_gate_pass": False,
        }
        self.assertEqual(
            MODULE.classify_cause(row),
            "ISUP_RECOVERABLE_BCR_HEAD_NOT_TRANSPORTED",
        )

    def test_prepared_crop_membership_and_encoder_pairing_if_present(self) -> None:
        lock = MODULE.ARTIFACTS / "fm6_chimera_preparation_lock.json"
        if not lock.exists():
            self.skipTest("outcome-blind crop preparation not generated yet")
        manifest, _ = MODULE.verify_preparation()
        self.assertEqual(len(manifest), 190 * 64)
        self.assertTrue(manifest.tile_id.is_unique)
        self.assertTrue(manifest.groupby("slide_id").size().eq(64).all())
        self.assertEqual(manifest.subject_id.nunique(), 95)
        arrays = [
            MODULE.ARTIFACTS / "fm6_chimera_conch_tile_embeddings.npy",
            MODULE.ARTIFACTS / "fm6_chimera_virchow_tile_embeddings.npy",
        ]
        if not all(path.exists() for path in arrays):
            self.skipTest("paired encoder arrays not generated yet")
        audit = MODULE.paired_embedding_audit()
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["decoded_crop_hashes_identical_across_encoders"])
        self.assertTrue(audit["row_order_locked"])

    def test_saved_output_claim_boundary_and_clean_rerun_if_present(self) -> None:
        primary = (
            MODULE.ARTIFACTS
            / "analysis_runs/primary/fm6_chimera_external_run_config.json"
        )
        rerun = (
            MODULE.ARTIFACTS
            / "analysis_runs/clean_rerun/fm6_chimera_external_run_config.json"
        )
        if not primary.exists():
            self.skipTest("embargo-controlled analysis not generated yet")
        config = json.loads(primary.read_text(encoding="utf-8"))
        if config["runner_sha256"] != MODULE.sha256_file(SCRIPT):
            self.skipTest("saved analysis predates the current committed provenance-only runner")
        self.assertEqual(config["publication_status"], MODULE.EMBARGO_STATUS)
        self.assertEqual(
            config["result_visibility"],
            "internal_embargo_controlled_local_artifact_only",
        )
        self.assertIn("publication", config["claim_ceiling"])
        self.assertEqual(set(config["model_provenance"]), {"conch", "virchow"})
        for encoder, provenance in config["model_provenance"].items():
            self.assertEqual(provenance["dimension"], MODULE.DIMENSION[encoder])
            self.assertEqual(len(provenance["weights_sha256"]), 64)
            self.assertEqual(len(provenance["tile_embedding_sha256"]), 64)
        self.assertFalse((SCRIPT.parent / "outputs").exists())
        for filename, expected in config["nonvolatile_output_sha256"].items():
            self.assertEqual(MODULE.sha256_file(primary.parent / filename), expected)
        if rerun.exists():
            rerun_config = json.loads(rerun.read_text(encoding="utf-8"))
            self.assertEqual(
                config["nonvolatile_output_sha256"],
                rerun_config["nonvolatile_output_sha256"],
            )

    def test_publication_gate_and_output_route_are_locked(self) -> None:
        self.assertEqual(MODULE.EMBARGO_STATUS, "EMBARGO_ACTIVE_NO_WRITTEN_CLEARANCE")
        self.assertEqual(MODULE.PUBLICATION_GATE_CHECKED_ON, "2026-08-21")
        self.assertTrue(all("chimera.grand-challenge.org" in url for url in MODULE.PUBLICATION_GATE_URLS))
        self.assertTrue(str(MODULE.ARTIFACTS).startswith(str(ROOT / "resources/artifacts")))
        self.assertNotIn("paper", str(MODULE.ARTIFACTS.relative_to(ROOT)))


if __name__ == "__main__":
    unittest.main()
