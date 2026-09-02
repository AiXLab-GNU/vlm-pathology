"""Focused tests for the grading-criterion entry audit."""

from __future__ import annotations

import csv
import importlib.util
import inspect
import json
import numpy as np
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / (
    "projects/quantitative_foundation_model_validation/milestones/"
    "fm8_grading_criterion_qualification/audit_fm8_grading_criterion_qualification.py"
)
REFERENCE = SCRIPT.parent / "outputs"
ACQUISITION_SCRIPT = SCRIPT.parent / "acquire_fm8_par_source.py"
RUNNER = SCRIPT.parent / "run_fm8_grading_criterion_qualification.py"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class GradingCriterionQualificationAuditTest(unittest.TestCase):
    def test_panda_runner_locks_outcome_blind_sampling_and_provider_truth(self) -> None:
        spec = importlib.util.spec_from_file_location("fm8_grading_runner", RUNNER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(10616, len(module.panda_labels()))
        self.assertEqual((3, 4), module.parse_gleason("3+4"))
        self.assertEqual((0, 0), module.parse_gleason("negative"))
        self.assertEqual(4, module.isup_from_patterns(3, 5))
        self.assertEqual(5, module.isup_from_patterns(5, 4))
        sicap = module.sicap_test_manifest()
        self.assertEqual((2122, 31, 21), (len(sicap), sicap.slide_id.nunique(), sicap.patient_id.nunique()))
        par = module.par_labels()
        self.assertEqual((339, 185), (len(par), par.patient_id.nunique()))
        self.assertEqual("c001a_hamamatsu.ndpi", par.loc[par.slide_id.eq("C001A"), "file_name"].iloc[0])
        par_loader_source = inspect.getsource(module.load_par_slide)
        self.assertIn("openslide.OpenSlide", par_loader_source)
        self.assertNotIn("read_tiled_rgb_region", par_loader_source)
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("Sampling is completed from RGB tissue before labels or masks are attached", source)
        self.assertIn('if provider == "radboud"', source)
        self.assertIn('elif provider == "karolinska"', source)
        self.assertIn('fields["gp3_fraction"].append(np.nan)', source)

        probabilities = module.ordinal_probabilities(np.zeros((2, 5)))
        self.assertEqual((2, 6), probabilities.shape)
        np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
        metrics = module.grading_metrics(
            np.asarray([0, 1, 2, 3, 4, 5]),
            np.asarray([0, 1, 2, 3, 4, 5]),
            np.eye(6),
        )
        self.assertEqual(1.0, metrics["cancer_only_qwk"])
        self.assertEqual(1.0, metrics["cancer_only_exact"])
        self.assertEqual(0.0, metrics["ordinal_multiclass_brier"])
        self.assertEqual(0.0, metrics["ordinal_log_loss"])
        self.assertEqual(0.0, metrics["ordinal_expected_grade_mae"])
        confusion = module.confusion_rows(
            np.arange(6), np.arange(6), "unit_test", "conch", "truth"
        )
        self.assertEqual(36, len(confusion))
        self.assertEqual(6, sum(row["n"] for row in confusion))
        mean_bag, mean_mask = module.mean_linear_inputs(np.ones((2, 4), dtype=np.float32))
        self.assertEqual((2, 1, 4), mean_bag.shape)
        self.assertEqual((2, 1), mean_mask.shape)
        self.assertTrue(mean_mask.all())
        self.assertEqual(
            "fm8_panda_conch_ordinal_mil_head.pt",
            module.head_checkpoint_path("conch", "gated_mil").name,
        )
        self.assertEqual(
            "fm8_panda_conch_mean_linear_ordinal_head.pt",
            module.head_checkpoint_path("conch", "mean_linear").name,
        )

    def test_par_primary_scanner_identity_contract(self) -> None:
        spec = importlib.util.spec_from_file_location("fm8_par_acquisition", ACQUISITION_SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paths = module.read_source_paths()
        self.assertEqual(339, len(paths))
        self.assertEqual(185, len({module.patient_id(path) for path in paths}))
        self.assertTrue(all(path.endswith("_hamamatsu.ndpi") for path in paths))

    def test_audit_preserves_source_and_confirmatory_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fm8-grading-audit-") as temp:
            output = Path(temp)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--output-dir", str(output)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("NO_GO_FUNCTIONAL_INTERPRETATION_NO_GO_RESIDUAL", completed.stdout)

            cohort = {row["cohort"]: row for row in rows(output / "fm8_grading_cohort_readiness.csv")}
            self.assertEqual("development_only", cohort["PANDA_PUBLIC_DEVELOPMENT"]["role"])
            self.assertEqual("FAIL_NOT_PROVIDED", cohort["PANDA_PUBLIC_DEVELOPMENT"]["patient_identity"])
            self.assertEqual("21", cohort["SICAPV2_OFFICIAL_TEST"]["patients"])
            self.assertEqual("READY", cohort["PAR_S_BIAD2323"]["readiness"])

            criterion = {row["criterion_id"]: row for row in rows(output / "fm8_grading_criterion_registry.csv")}
            self.assertEqual("excluded_not_grading_criteria", criterion["PROGNOSTIC_COVARIATES"]["grading_role"])
            self.assertEqual("result label", criterion["ISUP_RESULT"]["grading_role"])
            self.assertEqual("specimen_specific_rule", criterion["BIOPSY_SECONDARY_RULE"]["grading_role"])
            self.assertEqual("not separately evaluable", criterion["GP4_FUSED"]["analysis"])
            self.assertEqual("qualified GP4 subtype", criterion["G4_CRIBRIFORM"]["grading_role"])

            gates = {row["gate_id"]: row for row in rows(output / "fm8_grading_gate_matrix.csv")}
            self.assertEqual("PASS", gates["G4"]["status"])
            self.assertEqual("FAIL", gates["G8"]["status"])
            self.assertEqual("FAIL", gates["G10"]["status"])

            config = json.loads((output / "fm8_grading_entry_audit_run_config.json").read_text())
            reference_config = json.loads((REFERENCE / "fm8_grading_entry_audit_run_config.json").read_text())
            self.assertEqual(10616, config["panda"]["label_rows"])
            self.assertEqual(0, config["sicap"]["patient_overlap"])
            self.assertEqual(185, config["par"]["unique_patients"])
            self.assertEqual(339, config["par"]["local_wsi"])
            self.assertEqual("PASS_HASHED_OPENABLE", config["par"]["local_wsi_audit_status"])
            self.assertGreater(config["par"]["r1_r2_qwk"], 0.8)
            self.assertEqual(3, config["chimera"]["mapping_discordant"])
            self.assertTrue(config["confirmatory_modeling_allowed"])
            self.assertFalse(config["residual_allowed"])
            self.assertEqual(reference_config["output_sha256"], config["output_sha256"])


if __name__ == "__main__":
    unittest.main()
